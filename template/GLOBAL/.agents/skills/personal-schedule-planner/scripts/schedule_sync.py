#!/usr/bin/env python3
"""Execute confirmed personal schedule calendar changes from a guarded manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import locale
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import planner_guard as guard


PUBLIC_DESCRIPTION = "已确认的个人时间安排。"
WRITE_ACTIONS = {"create", "update", "delete"}


class SyncError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SyncError(message)


def load(path: Path) -> dict[str, Any]:
    return guard.load_manifest(path)


def save(path: Path, manifest: dict[str, Any]) -> None:
    guard.atomic_write(path, manifest)


def pairs(items: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    return {(str(item["profile"]), str(item["block_key"])): item for item in items}


def marker(manifest: dict[str, Any], block_key: str, match: dict[str, Any] | None = None) -> str:
    if match:
        existing = guard.retain_match_marker(match)
        if existing:
            guard.validate_retain_marker(manifest, block_key, existing)
            return existing
    return guard.expected_marker(manifest, block_key)


def find_marker(description: Any, schedule_key: str, block_key: str) -> str:
    for item in guard.MARKER_RE.finditer(str(description or "")):
        parsed = item.groupdict()
        if parsed["schedule"] == schedule_key and parsed["block"] == block_key:
            return item.group(0)
    return ""


def unix_seconds(value: str) -> str:
    return str(int(datetime.fromisoformat(value).timestamp()))


def iso_seconds(value: dict[str, Any], timezone_name: str) -> str:
    try:
        timezone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise SyncError(f"IANA timezone is unavailable: {timezone_name}") from exc
    return datetime.fromtimestamp(int(value["timestamp"]), timezone).isoformat(timespec="seconds")


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def request_filename(profile_index: int, block_index: int) -> str:
    return f"p{profile_index:02d}-b{block_index:03d}.json"


def event_body(manifest: dict[str, Any], block: dict[str, Any]) -> dict[str, Any]:
    public_description = str(block.get("public_description") or PUBLIC_DESCRIPTION).strip()
    return {
        "summary": block["public_title"],
        "description": f"{public_description}\n\n{marker(manifest, block['block_key'])}",
        "start_time": {"timestamp": unix_seconds(block["start"]), "timezone": manifest["timezone"]},
        "end_time": {"timestamp": unix_seconds(block["end"]), "timezone": manifest["timezone"]},
        "visibility": "public",
        "free_busy_status": "busy",
        "vchat": {"vc_type": "no_meeting"},
    }


def build_request(
    manifest: dict[str, Any], profile: dict[str, Any], block: dict[str, Any], match: dict[str, Any]
) -> dict[str, Any]:
    action = block["action"]
    request: dict[str, Any] = {
        "schema_version": 1,
        "profile": profile["name"],
        "block_key": block["block_key"],
        "action": action,
        "calendar_id": profile["calendar_id"],
    }
    if action == "create":
        request["idempotency_key"] = guard.idempotency_key(
            profile["app_id"], profile["calendar_id"], manifest["schedule_key"], block["block_key"]
        )
        request["body"] = event_body(manifest, block)
    elif action == "update":
        request["event_id"] = match["event_id"]
        request["body"] = event_body(manifest, block)
    elif action == "delete":
        request["event_id"] = match["event_id"]
    else:
        raise SyncError(f"cannot build write request for action: {action}")
    return request


def write_request(path: Path, request: dict[str, Any]) -> None:
    guard.atomic_write(path, request)


def prepare_requests(manifest_path: Path, request_root: Path) -> list[dict[str, Any]]:
    manifest = load(manifest_path)
    require(manifest["state"] == "preflight", f"prepare requires preflight state, got {manifest['state']}")
    guard.validate_preflight(manifest)
    request_root.mkdir(parents=True, exist_ok=True)
    match_map = pairs(manifest["matches"])
    index: list[dict[str, Any]] = []
    expected_names: set[str] = set()
    for profile_index, profile in enumerate(manifest["profiles"]):
        for block_index, block in enumerate(manifest["blocks"]):
            if block["action"] not in WRITE_ACTIONS:
                continue
            pair = (profile["name"], block["block_key"])
            name = request_filename(profile_index, block_index)
            expected_names.add(name)
            path = request_root / name
            write_request(path, build_request(manifest, profile, block, match_map[pair]))
            index.append({"profile": pair[0], "block_key": pair[1], "path": str(path)})
    unexpected = [path for path in request_root.iterdir() if path.is_file() and path.name not in expected_names]
    require(not unexpected, "request directory contains unexpected files; use an empty dedicated directory")
    return index


def decode_output(raw: bytes) -> str:
    candidates = ("utf-8", locale.getpreferredencoding(False), "gb18030")
    for encoding in dict.fromkeys(candidates):
        try:
            return raw.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", errors="replace")


def parse_json_output(raw: bytes, *, dry_run: bool = False) -> dict[str, Any]:
    text = decode_output(raw).strip()
    if dry_run:
        require(text.startswith("=== Dry Run ==="), "dry-run output is missing the expected banner")
        text = text[len("=== Dry Run ==="):].lstrip()
    start = text.find("{")
    require(start >= 0, "CLI output does not contain JSON")
    try:
        value, _ = json.JSONDecoder().raw_decode(text[start:])
    except json.JSONDecodeError as exc:
        raise SyncError(f"cannot parse CLI JSON output: {exc}") from exc
    require(isinstance(value, dict), "CLI JSON output must be an object")
    if dry_run:
        require(isinstance(value.get("api"), list) and value["api"], "dry-run output lacks an API request")
    else:
        require(value.get("ok") is True, f"CLI returned non-success: {json.dumps(value, ensure_ascii=False)}")
    return value


def discover_lark_cli(explicit: str | None) -> str:
    if explicit:
        return explicit
    configured = os.environ.get("LARK_CLI")
    if configured:
        return configured
    found = shutil.which("lark-cli")
    if found:
        return found
    if os.name == "nt" and os.environ.get("APPDATA"):
        for name in ("lark-cli.cmd", "lark-cli.exe"):
            candidate = Path(os.environ["APPDATA"]) / "npm" / name
            if candidate.is_file():
                return str(candidate)
    raise SyncError("lark-cli was not found; restore it with feishu-profile before syncing")


def command_for(request: dict[str, Any], *, dry_run: bool) -> tuple[list[str], bytes | None]:
    argv = ["calendar", "events"]
    action = request["action"]
    if action == "create":
        argv.extend(["create", "--calendar-id", request["calendar_id"], "--idempotency-key", request["idempotency_key"]])
    elif action == "update":
        argv.extend(["patch", "--calendar-id", request["calendar_id"], "--event-id", request["event_id"]])
    elif action == "delete":
        argv.extend(["delete", "--calendar-id", request["calendar_id"], "--event-id", request["event_id"], "--need-notification", "false"])
    else:
        raise SyncError(f"unsupported action: {action}")
    stdin: bytes | None = None
    if "body" in request:
        argv.extend(["--data", "-"])
        stdin = json.dumps(request["body"], ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    argv.extend(["--profile", request["profile"], "--as", "user", "--format", "json"])
    if dry_run:
        argv.append("--dry-run")
    return argv, stdin


def run_cli(executable: str, argv: list[str], stdin: bytes | None = None) -> subprocess.CompletedProcess[bytes]:
    env = os.environ.copy()
    env["LARKSUITE_CLI_NO_UPDATE_NOTIFIER"] = "1"
    env["LARKSUITE_CLI_NO_SKILLS_NOTIFIER"] = "1"
    return subprocess.run([executable, *argv], input=stdin, capture_output=True, env=env, check=False)


def invoke(executable: str, request: dict[str, Any], *, dry_run: bool) -> dict[str, Any]:
    argv, stdin = command_for(request, dry_run=dry_run)
    completed = run_cli(executable, argv, stdin)
    if completed.returncode != 0:
        detail = decode_output(completed.stderr or completed.stdout).strip()
        raise SyncError(f"lark-cli failed ({completed.returncode}) for {request['profile']} / {request['block_key']}: {detail}")
    return parse_json_output(completed.stdout, dry_run=dry_run)


def request_map(request_root: Path, manifest: dict[str, Any]) -> dict[tuple[str, str], Path]:
    mapped: dict[tuple[str, str], Path] = {}
    for profile_index, profile in enumerate(manifest["profiles"]):
        for block_index, block in enumerate(manifest["blocks"]):
            if block["action"] in WRITE_ACTIONS:
                mapped[(profile["name"], block["block_key"])] = request_root / request_filename(profile_index, block_index)
    return mapped


def dry_run(manifest_path: Path, request_root: Path, executable: str) -> None:
    manifest = load(manifest_path)
    require(manifest["state"] == "preflight", f"dry-run requires preflight state, got {manifest['state']}")
    prepare_requests(manifest_path, request_root)
    requests = request_map(request_root, manifest)
    results = []
    for pair in sorted(requests):
        path = requests[pair]
        request = json.loads(path.read_text(encoding="utf-8-sig"))
        invoke(executable, request, dry_run=True)
        results.append({"profile": pair[0], "block_key": pair[1], "ok": True, "request_sha256": file_sha256(path)})
    manifest["dry_runs"] = results
    guard.transition(manifest, "dry-run", False)
    save(manifest_path, manifest)


def verify_exact_request(manifest: dict[str, Any], pair: tuple[str, str], path: Path) -> str:
    try:
        return guard.validate_write_payload(manifest, pair[0], pair[1], path)
    except guard.GuardError as exc:
        raise SyncError(str(exc)) from exc


def write(manifest_path: Path, request_root: Path, executable: str) -> None:
    manifest = load(manifest_path)
    if manifest["state"] == "dry-run":
        guard.transition(manifest, "write", False)
        save(manifest_path, manifest)
    require(manifest["state"] == "write", f"write requires dry-run or write state, got {manifest['state']}")
    requests = request_map(request_root, manifest)
    existing = list(manifest.get("writes", []))
    done = {pair for pair, result in pairs(existing).items() if result.get("ok") is True}
    for pair in sorted(requests):
        if pair in done:
            continue
        path = requests[pair]
        request_hash = verify_exact_request(manifest, pair, path)
        request = json.loads(path.read_text(encoding="utf-8-sig"))
        response = invoke(executable, request, dry_run=False)
        event = response.get("data", {}).get("event", {})
        event_id = event.get("event_id") or request.get("event_id")
        require(request["action"] == "delete" or event_id, f"write response lacks event_id for {pair[0]} / {pair[1]}")
        existing.append({
            "profile": pair[0],
            "block_key": pair[1],
            "ok": True,
            "request_sha256": request_hash,
            "event_id": event_id,
            "app_link": event.get("app_link", ""),
        })
        manifest["writes"] = existing
        save(manifest_path, manifest)
    guard.transition(manifest, "readback", False)
    save(manifest_path, manifest)


def get_event(executable: str, profile: str, calendar_id: str, event_id: str) -> dict[str, Any]:
    completed = run_cli(executable, [
        "calendar", "events", "get", "--calendar-id", calendar_id, "--event-id", event_id,
        "--need-attendee", "--max-attendee-num", "100", "--profile", profile, "--as", "user", "--format", "json",
    ])
    if completed.returncode != 0:
        detail = decode_output(completed.stderr or completed.stdout).strip()
        raise SyncError(f"readback failed ({completed.returncode}) for {profile} / {event_id}: {detail}")
    response = parse_json_output(completed.stdout)
    event = response.get("data", {}).get("event")
    require(isinstance(event, dict), f"readback lacks event for {profile} / {event_id}")
    return event


def readback(manifest_path: Path, executable: str) -> None:
    manifest = load(manifest_path)
    require(manifest["state"] == "readback", f"readback requires readback state, got {manifest['state']}")
    match_map = pairs(manifest["matches"])
    write_map = pairs(manifest["writes"])
    results = []
    for profile in manifest["profiles"]:
        for block in manifest["blocks"]:
            if block["action"] == "none":
                continue
            pair = (profile["name"], block["block_key"])
            if block["action"] == "retain":
                event_id = match_map[pair]["event_id"]
            else:
                event_id = write_map[pair].get("event_id")
            require(event_id, f"missing event_id for readback: {pair[0]} / {pair[1]}")
            event = get_event(executable, profile["name"], profile["calendar_id"], event_id)
            if block["action"] == "delete":
                require(event.get("status") == "cancelled", f"deleted event is not cancelled: {pair[0]} / {pair[1]}")
                results.append({"profile": pair[0], "block_key": pair[1], "ok": True, "absent": True})
                continue
            attendees = event.get("attendees") or []
            rooms = [item.get("room_id") or item.get("user_id") for item in attendees if item.get("type") == "resource"]
            match = match_map.get(pair, {})
            expected_marker = marker(manifest, block["block_key"], match if block["action"] == "retain" else None)
            actual_marker = find_marker(event.get("description"), manifest["schedule_key"], block["block_key"])
            if block["action"] == "retain" and not guard.retain_match_marker(match):
                require(actual_marker, f"retain event lacks stable marker: {pair[0]} / {pair[1]}")
                parsed = guard.validate_retain_marker(manifest, block["block_key"], actual_marker)
                match["existing_marker"] = actual_marker
                match["existing_revision"] = parsed["revision"]
                expected_marker = actual_marker
            results.append({
                "profile": pair[0], "block_key": pair[1], "ok": True,
                "calendar_id": profile["calendar_id"], "event_id": event_id,
                "app_link": event.get("app_link", write_map.get(pair, {}).get("app_link", "")),
                "summary": event.get("summary"), "start": iso_seconds(event["start_time"], manifest["timezone"]),
                "end": iso_seconds(event["end_time"], manifest["timezone"]), "timezone": event.get("start_time", {}).get("timezone"),
                "visibility": event.get("visibility"), "free_busy_status": event.get("free_busy_status"),
                "vc_type": event.get("vchat", {}).get("vc_type"), "attendees": attendees, "room_ids": rooms,
                "marker": actual_marker if actual_marker == expected_marker else "",
            })
    manifest["readbacks"] = results
    guard.transition(manifest, "complete", False)
    save(manifest_path, manifest)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "dry-run", "write", "readback"))
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--request-root", type=Path)
    parser.add_argument("--lark-cli")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.command in {"prepare", "dry-run", "write"}:
            require(args.request_root is not None, f"{args.command} requires --request-root")
        if args.command == "prepare":
            prepare_requests(args.manifest, args.request_root)
        else:
            executable = discover_lark_cli(args.lark_cli)
            if args.command == "dry-run":
                dry_run(args.manifest, args.request_root, executable)
            elif args.command == "write":
                write(args.manifest, args.request_root, executable)
            else:
                readback(args.manifest, executable)
        print(json.dumps({"ok": True, "command": args.command, "state": load(args.manifest)["state"]}, ensure_ascii=False))
        return 0
    except (SyncError, guard.GuardError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
