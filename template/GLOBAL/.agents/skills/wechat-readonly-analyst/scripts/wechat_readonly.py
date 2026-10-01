"""Hardened, Profile-routed, ephemeral wrapper for local WeChat queries."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from profile_store import get_key_catalog, has_standing_read_authorization, resolve, store_key_catalog
from wechat_cli.keys import extract_keys


SKILL_ROOT = Path(__file__).resolve().parents[1]
CLI = SKILL_ROOT / ".runtime" / "Scripts" / "wechat-cli.exe"
RUNTIME_ROOT = Path(os.environ.get("LOCALAPPDATA", tempfile.gettempdir())) / "DongLi" / "AgentFoundation" / "wechat-readonly" / "runtime"
ORPHAN_MAX_AGE_SECONDS = 3600
SENSITIVE_KEYS = {
    "username", "wxid", "db_path", "database_path", "keys", "key", "salt",
    "config", "config_path", "cache_path", "decrypted_path", "wechat_base_dir",
}


def redact_text(value: str, max_chars: int) -> str:
    value = re.sub(r"(?i)wxid_[a-z0-9_-]+", "[微信标识]", value)
    value = re.sub(r"(?i)\b(?:[a-z]:\\|/users/|/home/)\S+", "[路径]", value)
    value = re.sub(r"(?i)\b[0-9a-f]{32,}\b", "[敏感标识]", value)
    value = re.sub(r"(?i)https?://\S+", "[链接]", value)
    value = re.sub(r"\(local_id=\d+\)", "", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value[:max_chars] + "…" if len(value) > max_chars else value


def sanitize(value: Any, max_chars: int) -> Any:
    if isinstance(value, dict):
        return {key: sanitize(item, max_chars) for key, item in value.items() if key.lower() not in SENSITIVE_KEYS}
    if isinstance(value, list):
        return [sanitize(item, max_chars) for item in value]
    if isinstance(value, str):
        return redact_text(value, max_chars)
    return value


def filter_history_payload(payload: dict[str, Any], sender: str = "", summary_only: bool = False) -> dict[str, Any]:
    """Filter formatted history lines without exposing internal sender identifiers."""
    messages = payload.get("messages") or []
    source_count = len(messages)
    if sender:
        marker = re.compile(r"^\[[^\]]+\]\s+" + re.escape(sender) + r":(?:\s|$)")
        messages = [line for line in messages if isinstance(line, str) and marker.search(line)]
    payload["source_count"] = source_count
    payload["count"] = len(messages)
    payload["sender_filter"] = sender or None
    payload["messages"] = [] if summary_only else messages
    payload["summary_only"] = summary_only
    return payload


def clean_orphans() -> int:
    RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)
    removed = 0
    now = time.time()
    for candidate in RUNTIME_ROOT.glob("query-*"):
        try:
            if candidate.is_dir() and now - candidate.stat().st_mtime > ORPHAN_MAX_AGE_SECONDS:
                shutil.rmtree(candidate)
                removed += 1
        except OSError:
            continue
    return removed


def invoke(env: dict[str, str], args: list[str], stdin_data: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(CLI), *args], cwd=SKILL_ROOT, env=env, capture_output=True,
        input=stdin_data, text=True, encoding="utf-8", errors="replace", timeout=300, check=False,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Profile-routed ephemeral WeChat read-only query")
    parser.add_argument("--profile", required=True, help="logical Profile from GLOBAL/WECHAT_PROFILES.md")
    parser.add_argument("--confirm-memory-read", action="store_true", help="legacy compatibility; bound Profile authorization is read from its DPAPI slot")
    parser.add_argument("--grant-standing-read", action="store_true", help="legacy compatibility; cannot grant or change authorization")
    parser.add_argument("--refresh-key-catalog", action="store_true", help="force a verified refresh for the bound Profile without changing its authorization")
    parser.add_argument("--confirm-content-processing", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--max-chars", type=int, default=240)
    sub = parser.add_subparsers(dest="command", required=True)
    sessions = sub.add_parser("sessions")
    sessions.add_argument("--limit", type=int, default=20)
    history = sub.add_parser("history")
    history.add_argument("chat")
    history.add_argument("--limit", type=int, default=30)
    history.add_argument("--offset", type=int, default=0)
    history.add_argument("--start-time", default="")
    history.add_argument("--end-time", default="")
    history.add_argument("--type", dest="message_type", default="")
    history.add_argument("--sender", default="")
    history.add_argument("--summary-only", action="store_true")
    search = sub.add_parser("search")
    search.add_argument("keyword")
    search.add_argument("--chat", default="")
    search.add_argument("--limit", type=int, default=20)
    search.add_argument("--offset", type=int, default=0)
    stats = sub.add_parser("stats")
    stats.add_argument("chat")
    stats.add_argument("--start-time", default="")
    stats.add_argument("--end-time", default="")
    return parser.parse_args()


def bounded_limit(value: int) -> int:
    if value < 1:
        raise ValueError("limit must be a positive integer")
    return value


def normalize_time(value: str) -> str:
    """Convert ISO timestamps to the local-time syntax accepted by the bundled CLI."""
    value = value.strip()
    if not value:
        return value
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            datetime.strptime(value, fmt)
            return value
        except ValueError:
            pass
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError
        return parsed.astimezone().strftime("%Y-%m-%d %H:%M:%S")
    except ValueError as exc:
        raise ValueError("Invalid time; use YYYY-MM-DD, local date-time, or ISO 8601 with timezone") from exc


def key_failure(detail: str) -> bool:
    """Only verified key/decryption diagnostics authorize an automatic refresh."""
    return bool(re.search(r"(?i)(?:密钥|decrypt|decryption|hmac|invalid key|missing key|no key|key mismatch)", detail))


def capture_bound_keys(profile: str, db_dir: Path) -> dict[str, Any]:
    if not has_standing_read_authorization(profile):
        raise PermissionError("Standing read authorization is absent for this Profile")
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            catalog = extract_keys(str(db_dir), None)
    except RuntimeError as exc:
        if "未运行" in str(exc):
            raise RuntimeError("WeChat is not running; cached offline reads remain available") from exc
        if "未能从任何微信进程中提取到密钥" in str(exc):
            raise LookupError("No running WeChat key matched the bound Profile database") from exc
        raise RuntimeError("The read-only key scanner failed; stored keys were not changed") from exc
    if not isinstance(catalog, dict) or not catalog:
        raise LookupError("No running WeChat key matched the bound Profile database")
    return catalog


def cli_args(args: argparse.Namespace) -> list[str]:
    if args.command == "sessions":
        return ["sessions", "--limit", str(bounded_limit(args.limit)), "--format", "json"]
    if args.command == "history":
        result = ["history", args.chat, "--limit", str(bounded_limit(args.limit)), "--offset", str(max(0, args.offset)), "--format", "json"]
        if args.start_time:
            result += ["--start-time", normalize_time(args.start_time)]
        if args.end_time:
            result += ["--end-time", normalize_time(args.end_time)]
        if args.message_type:
            result += ["--type", args.message_type]
        return result
    if args.command == "search":
        result = ["search", args.keyword, "--limit", str(bounded_limit(args.limit)), "--offset", str(max(0, args.offset)), "--format", "json"]
        if args.chat:
            result += ["--chat", args.chat]
        return result
    result = ["stats", args.chat, "--format", "json"]
    if args.start_time:
        result += ["--start-time", normalize_time(args.start_time)]
    if args.end_time:
        result += ["--end-time", normalize_time(args.end_time)]
    return result


def main() -> int:
    args = parse_args()
    result: dict[str, Any]
    scratch: Path | None = None
    code = 0
    removed_orphans = clean_orphans()
    try:
        if platform.system() != "Windows" or not CLI.exists():
            raise RuntimeError("Run scripts/install.ps1 first on Windows")
        db_dir = resolve(args.profile)
        query_args = cli_args(args)  # Reject bad input before any process-memory access.
        scratch = Path(tempfile.mkdtemp(prefix="query-", dir=RUNTIME_ROOT))
        env = os.environ.copy()
        env.update({
            "PYTHONUTF8": "1",
            "WECHAT_CLI_STATE_DIR": str(scratch / "state"),
            "WECHAT_CLI_CACHE_DIR": str(scratch / "cache"),
            "WECHAT_CLI_DB_DIR": str(db_dir),
            "WECHAT_CLI_KEYS_STDIN": "1",
        })
        if not has_standing_read_authorization(args.profile):
            raise PermissionError("This Profile has no standing read authorization; confirm ownership and bind it first")
        cached_catalog = get_key_catalog(args.profile)
        catalog = cached_catalog
        key_source = "dpapi-cache"
        refreshed = args.refresh_key_catalog or catalog is None
        if refreshed:
            catalog = {**(cached_catalog or {}), **capture_bound_keys(args.profile, db_dir)}
            key_source = "process-memory-verified"
        if code == 0:
            queried = invoke(env, query_args, json.dumps(catalog, ensure_ascii=False))
            if queried.returncode != 0 and not refreshed and key_failure(queried.stderr):
                catalog = {**cached_catalog, **capture_bound_keys(args.profile, db_dir)}
                refreshed = True
                key_source = "process-memory-verified"
                queried = invoke(env, query_args, json.dumps(catalog, ensure_ascii=False))
            if queried.returncode != 0:
                result = {"ok": False, "stage": args.command, "message": "The read-only query failed. Check the Profile, chat name, input and local data; no key issue has been established."}
                code = 4
            else:
                payload = json.loads(queried.stdout)
                failures = payload.get("failures") if isinstance(payload, dict) else None
                if failures and key_failure(" ".join(str(item) for item in failures)) and not refreshed:
                    catalog = {**cached_catalog, **capture_bound_keys(args.profile, db_dir)}
                    refreshed = True
                    key_source = "process-memory-verified"
                    queried = invoke(env, query_args, json.dumps(catalog, ensure_ascii=False))
                    if queried.returncode == 0:
                        payload = json.loads(queried.stdout)
                if queried.returncode != 0:
                    result = {"ok": False, "stage": args.command, "message": "The read-only query still failed after a verified key refresh. Stored keys were not changed."}
                    code = 4
                elif refreshed and isinstance(payload, dict) and payload.get("failures") and key_failure(" ".join(str(item) for item in payload["failures"])):
                    result = {"ok": False, "stage": "key_validation", "message": "The refreshed keys did not resolve database decryption errors. Stored keys were not changed."}
                    code = 4
                else:
                    if refreshed:
                        store_key_catalog(args.profile, catalog)
                        key_source = "process-memory-verified-and-dpapi-stored"
                    if args.command == "history":
                        payload = filter_history_payload(payload, args.sender, args.summary_only)
                    result = {
                        "ok": True,
                        "profile": args.profile,
                        "command": args.command,
                        "key_source": key_source,
                        "data": sanitize(payload, max(40, args.max_chars)),
                    }
    except subprocess.TimeoutExpired:
        result = {"ok": False, "stage": "timeout", "message": "The read-only scan timed out."}
        code = 5
    except LookupError:
        result = {"ok": False, "stage": "account_identity_unverified", "message": "The running WeChat account could not be verified against the selected Profile database. Stored keys were not changed; check the signed-in account."}
        code = 8
    except PermissionError:
        result = {"ok": False, "stage": "authorization", "message": "The selected Profile has no standing read authorization. Confirm ownership and bind it before reading."}
        code = 9
    except FileNotFoundError as exc:
        result = {"ok": False, "stage": "profile_or_input", "message": redact_text(str(exc), 240)}
        code = 6
    except OSError:
        result = {"ok": False, "stage": "credential_unavailable", "message": "The bound Profile credential could not be read in this Windows user context. No account mismatch or key expiry has been established; no key scan was attempted."}
        code = 10
    except (KeyError, ValueError, RuntimeError) as exc:
        result = {"ok": False, "stage": "profile_or_input", "message": redact_text(str(exc), 240)}
        code = 6
    except Exception:
        result = {"ok": False, "stage": "internal", "message": "The privacy wrapper could not complete the query."}
        code = 7
    finally:
        if scratch is not None:
            shutil.rmtree(scratch, ignore_errors=True)
    result["cleanup_complete"] = scratch is None or not scratch.exists()
    result["orphan_directories_removed"] = removed_orphans
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
