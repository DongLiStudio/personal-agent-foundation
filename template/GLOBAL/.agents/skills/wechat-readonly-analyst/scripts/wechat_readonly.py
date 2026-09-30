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
from pathlib import Path
from typing import Any

from profile_store import get_key_catalog, resolve, store_key_catalog
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
    parser.add_argument("--confirm-memory-read", action="store_true", help="allow one-time read-only process-memory access when this Profile has no stored key catalog")
    parser.add_argument("--grant-standing-read", action="store_true", help="store the verified key catalog with DPAPI for subsequent offline read-only access")
    parser.add_argument("--refresh-key-catalog", action="store_true", help="replace the stored key catalog by scanning a running WeChat process")
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


def cli_args(args: argparse.Namespace) -> list[str]:
    if args.command == "sessions":
        return ["sessions", "--limit", str(bounded_limit(args.limit)), "--format", "json"]
    if args.command == "history":
        result = ["history", args.chat, "--limit", str(bounded_limit(args.limit)), "--offset", str(max(0, args.offset)), "--format", "json"]
        if args.start_time:
            result += ["--start-time", args.start_time]
        if args.end_time:
            result += ["--end-time", args.end_time]
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
        result += ["--start-time", args.start_time]
    if args.end_time:
        result += ["--end-time", args.end_time]
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
        scratch = Path(tempfile.mkdtemp(prefix="query-", dir=RUNTIME_ROOT))
        env = os.environ.copy()
        env.update({
            "PYTHONUTF8": "1",
            "WECHAT_CLI_STATE_DIR": str(scratch / "state"),
            "WECHAT_CLI_CACHE_DIR": str(scratch / "cache"),
            "WECHAT_CLI_DB_DIR": str(db_dir),
            "WECHAT_CLI_KEYS_STDIN": "1",
        })
        catalog = None if args.refresh_key_catalog else get_key_catalog(args.profile)
        key_source = "dpapi-cache"
        if catalog is None:
            if not args.confirm_memory_read or not args.grant_standing_read:
                result = {
                    "ok": False,
                    "stage": "key_capture_required",
                    "message": "This Profile needs an initial or refreshed key catalog. Process-memory confirmation and standing-read grant are required.",
                }
                code = 2
            else:
                try:
                    with contextlib.redirect_stdout(io.StringIO()):
                        catalog = extract_keys(str(db_dir), None)
                    store_key_catalog(args.profile, catalog)
                    key_source = "process-memory-captured-and-dpapi-stored"
                except Exception:
                    result = {"ok": False, "stage": "init", "message": "One-time read-only key capture failed."}
                    code = 3
        if code == 0:
            queried = invoke(env, cli_args(args), json.dumps(catalog, ensure_ascii=False))
            if queried.returncode != 0:
                result = {"ok": False, "stage": args.command, "message": "The requested read-only query failed; a newly created database may require an authorized key refresh while WeChat is running."}
                code = 4
            else:
                payload = json.loads(queried.stdout)
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
    except (KeyError, FileNotFoundError, ValueError, RuntimeError) as exc:
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
