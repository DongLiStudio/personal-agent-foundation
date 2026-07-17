#!/usr/bin/env python3
"""Programmatic stage guard for personal-schedule-planner manifests."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any


STAGES = ("collect", "draft", "confirm", "preflight", "dry-run", "write", "readback", "complete")
ACTIONS = {"create", "update", "retain", "delete", "none"}
CALENDAR_ACTIONS = {"create", "update", "retain", "delete"}
WRITE_ACTIONS = {"create", "update", "delete"}
UUID_NAMESPACE = uuid.NAMESPACE_URL
COLLECTION_BRANCHES = {"feishu", "obsidian", "projects"}
MARKER_RE = re.compile(
    r"AGENT-SCHEDULE\|schedule=(?P<schedule>[^|\s]+)\|block=(?P<block>[^|\s]+)\|revision=(?P<revision>\d+)"
)


class GuardError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise GuardError(message)


def load_manifest(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GuardError(f"cannot read manifest: {exc}") from exc
    require(isinstance(data, dict), "manifest root must be an object")
    require(data.get("schema_version") == 1, "schema_version must be 1")
    require(data.get("state") in STAGES, f"state must be one of: {', '.join(STAGES)}")
    return data


def atomic_write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def canonical_plan(manifest: dict[str, Any]) -> dict[str, Any]:
    profile_view = [{"name": profile.get("name")} for profile in manifest.get("profiles", [])]
    fields = (
        "block_key", "title", "description", "start", "end", "action", "reason", "sources",
        "visibility", "free_busy_status", "vc_type", "attendees", "room_ids",
    )
    block_view = [{field: block.get(field) for field in fields} for block in manifest.get("blocks", [])]
    return {
        "schedule_key": manifest.get("schedule_key"),
        "revision": manifest.get("revision"),
        "timezone": manifest.get("timezone"),
        "window": manifest.get("window"),
        "collection": manifest.get("collection"),
        "task_handoffs": manifest.get("task_handoffs", []),
        "profiles": profile_view,
        "blocks": block_view,
        "unplanned": manifest.get("unplanned", []),
        "risks": manifest.get("risks", []),
    }


def snapshot_sha256(manifest: dict[str, Any]) -> str:
    payload = json.dumps(canonical_plan(manifest), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def profile_names(manifest: dict[str, Any]) -> list[str]:
    return [str(profile.get("name", "")) for profile in manifest.get("profiles", [])]


def block_keys(manifest: dict[str, Any]) -> list[str]:
    return [str(block.get("block_key", "")) for block in manifest.get("blocks", [])]


def expected_pairs(manifest: dict[str, Any], actions: set[str] | None = None) -> set[tuple[str, str]]:
    selected_actions = CALENDAR_ACTIONS if actions is None else actions
    return {
        (profile["name"], block["block_key"])
        for profile in manifest.get("profiles", [])
        for block in manifest.get("blocks", [])
        if block.get("action") in selected_actions
    }


def result_map(items: Any, label: str) -> dict[tuple[str, str], dict[str, Any]]:
    require(isinstance(items, list), f"{label} must be a list")
    mapped: dict[tuple[str, str], dict[str, Any]] = {}
    for item in items:
        require(isinstance(item, dict), f"each {label} entry must be an object")
        key = (str(item.get("profile", "")), str(item.get("block_key", "")))
        require(all(key), f"each {label} entry needs profile and block_key")
        require(key not in mapped, f"duplicate {label} entry: {key[0]} / {key[1]}")
        mapped[key] = item
    return mapped


def validate_collection(manifest: dict[str, Any]) -> None:
    collection = manifest.get("collection")
    require(isinstance(collection, dict), "draft requires collection record")
    require(collection.get("mode") in {"parallel", "sequential"}, "collection mode must be parallel or sequential")
    require(collection.get("cutoff"), "collection requires a shared cutoff timestamp")
    branches = collection.get("branches")
    require(isinstance(branches, list), "collection branches must be a list")
    mapped: dict[str, dict[str, Any]] = {}
    for branch in branches:
        require(isinstance(branch, dict), "each collection branch must be an object")
        branch_id = str(branch.get("id", ""))
        require(branch_id in COLLECTION_BRANCHES, f"unknown collection branch: {branch_id}")
        require(branch_id not in mapped, f"duplicate collection branch: {branch_id}")
        require(branch.get("status") in {"complete", "failed"}, f"branch {branch_id} has invalid status")
        require(branch.get("collected_at"), f"branch {branch_id} requires collected_at")
        require(branch.get("coverage"), f"branch {branch_id} requires coverage")
        errors = branch.get("errors", [])
        require(isinstance(errors, list), f"branch {branch_id} errors must be a list")
        if branch["status"] == "failed":
            require(errors, f"failed branch {branch_id} requires explicit errors")
            require(branch.get("user_waived") is True, f"failed branch {branch_id} requires explicit user waiver")
        mapped[branch_id] = branch
    require(set(mapped) == COLLECTION_BRANCHES, "collection must cover feishu, obsidian, and projects exactly once")


def validate_draft(manifest: dict[str, Any]) -> None:
    validate_collection(manifest)
    require(isinstance(manifest.get("task_handoffs", []), list), "task_handoffs must be a list")
    for field in ("schedule_key", "timezone", "window"):
        require(manifest.get(field), f"draft requires {field}")
    require(isinstance(manifest.get("revision"), int) and manifest["revision"] >= 1, "revision must be >= 1")
    profiles = manifest.get("profiles")
    require(isinstance(profiles, list) and profiles, "draft requires at least one target profile")
    names = profile_names(manifest)
    require(all(names) and len(names) == len(set(names)), "profile names must be non-empty and unique")
    blocks = manifest.get("blocks")
    require(isinstance(blocks, list) and blocks, "draft requires at least one block")
    keys = block_keys(manifest)
    require(all(keys) and len(keys) == len(set(keys)), "block_key values must be non-empty and unique")
    for key in keys:
        require(not re.fullmatch(r"(?:block[-_ ]?)?\d+", key, re.IGNORECASE), f"unstable block_key: {key}")
        require(not re.fullmatch(r"\d{4}-\d{2}-\d{2}T.*", key), f"block_key must not be a timestamp: {key}")
    required = ("title", "start", "end", "action", "reason", "sources")
    for block in blocks:
        key = block["block_key"]
        for field in required:
            require(block.get(field), f"block {key} requires {field}")
        require(block["action"] in ACTIONS, f"block {key} has invalid action")
        require(block["start"] < block["end"], f"block {key} start must be before end")
        if block["action"] == "none":
            for field in ("description", "visibility", "free_busy_status", "vc_type"):
                require(not block.get(field), f"none block {key} must not define calendar field {field}")
        else:
            require(block.get("visibility", "public") == "public", f"block {key} visibility must be public")
            require(block.get("free_busy_status", "busy") == "busy", f"block {key} must be busy")
            require(block.get("vc_type", "no_meeting") == "no_meeting", f"block {key} must use no_meeting")
        require(block.get("attendees", []) == [], f"block {key} must not add attendees")
        require(block.get("room_ids", []) == [], f"block {key} must not add rooms")


def validate_confirmation(manifest: dict[str, Any]) -> None:
    validate_draft(manifest)
    confirmation = manifest.get("confirmation")
    require(isinstance(confirmation, dict), "confirmation record is missing")
    require(confirmation.get("user_confirmed") is True, "explicit user confirmation is missing")
    require(confirmation.get("snapshot_sha256") == snapshot_sha256(manifest), "confirmed plan changed; return to draft")


def parse_marker(value: Any) -> dict[str, Any]:
    require(isinstance(value, str) and value, "marker must be a non-empty string")
    match = MARKER_RE.fullmatch(value.strip())
    require(match is not None, "marker must be a complete AGENT-SCHEDULE marker")
    parsed = match.groupdict()
    parsed["revision"] = int(parsed["revision"])
    return parsed


def retain_match_marker(match: dict[str, Any]) -> str:
    return str(match.get("existing_marker") or match.get("marker") or "")


def validate_retain_marker(manifest: dict[str, Any], block_key: str, marker: Any) -> dict[str, Any]:
    parsed = parse_marker(marker)
    require(parsed["schedule"] == manifest["schedule_key"], f"retain marker schedule mismatch for {block_key}")
    require(parsed["block"] == block_key, f"retain marker block mismatch for {block_key}")
    require(parsed["revision"] >= 1, f"retain marker revision is invalid for {block_key}")
    return parsed


def validate_preflight(manifest: dict[str, Any], *, allow_retain_without_marker: bool = False) -> None:
    validate_confirmation(manifest)
    for profile in manifest["profiles"]:
        name = profile["name"]
        for field in ("app_id", "user_open_id", "calendar_id"):
            require(profile.get(field), f"profile {name} requires actual {field}")
        require(profile["calendar_id"] != "primary", f"profile {name} calendar_id cannot be the literal primary alias")
        require(profile.get("calendar_write_scope") is True, f"profile {name} lacks verified calendar write scope")
    matches = result_map(manifest.get("matches"), "matches")
    require(set(matches) == expected_pairs(manifest), "preflight matches must cover every profile and calendar block exactly once")
    blocks = {block["block_key"]: block for block in manifest["blocks"]}
    profiles = {profile["name"]: profile for profile in manifest["profiles"]}
    for pair, match in matches.items():
        count = match.get("count")
        require(count in (0, 1), f"duplicate or invalid match count for {pair[0]} / {pair[1]}")
        require(match.get("calendar_id") == profiles[pair[0]]["calendar_id"], f"calendar mismatch for {pair[0]} / {pair[1]}")
        action = blocks[pair[1]]["action"]
        if action == "create":
            require(count == 0, f"create requires zero matches for {pair[0]} / {pair[1]}")
        else:
            require(count == 1 and match.get("event_id"), f"{action} requires one event_id for {pair[0]} / {pair[1]}")
        if action == "retain":
            existing_marker = retain_match_marker(match)
            if existing_marker:
                parsed = validate_retain_marker(manifest, pair[1], existing_marker)
                if "existing_revision" in match:
                    require(match["existing_revision"] == parsed["revision"], f"retain existing_revision mismatch for {pair[0]} / {pair[1]}")
            else:
                require(allow_retain_without_marker, f"retain requires existing_marker for {pair[0]} / {pair[1]}")


def validate_dry_runs(manifest: dict[str, Any], *, allow_retain_without_marker: bool = False) -> None:
    validate_preflight(manifest, allow_retain_without_marker=allow_retain_without_marker)
    dry_runs = result_map(manifest.get("dry_runs"), "dry_runs")
    require(set(dry_runs) == expected_pairs(manifest, WRITE_ACTIONS), "dry_runs must cover every create, update, and delete exactly once")
    for pair, result in dry_runs.items():
        require(result.get("ok") is True, f"dry-run failed for {pair[0]} / {pair[1]}")
        require(re.fullmatch(r"[0-9a-f]{64}", str(result.get("request_sha256", ""))), f"dry-run lacks valid request_sha256 for {pair[0]} / {pair[1]}")


def validate_writes(manifest: dict[str, Any], *, allow_retain_without_marker: bool = False) -> None:
    validate_dry_runs(manifest, allow_retain_without_marker=allow_retain_without_marker)
    dry_runs = result_map(manifest.get("dry_runs"), "dry_runs")
    writes = result_map(manifest.get("writes"), "writes")
    require(set(writes) == expected_pairs(manifest, WRITE_ACTIONS), "writes must cover every create, update, and delete exactly once")
    blocks = {block["block_key"]: block for block in manifest["blocks"]}
    for pair, result in writes.items():
        require(result.get("ok") is True, f"write failed for {pair[0]} / {pair[1]}")
        require(result.get("request_sha256") == dry_runs[pair]["request_sha256"], f"write payload changed after dry-run for {pair[0]} / {pair[1]}")
        if blocks[pair[1]]["action"] != "delete":
            require(result.get("event_id"), f"write lacks event_id for {pair[0]} / {pair[1]}")


def expected_marker(manifest: dict[str, Any], block_key: str) -> str:
    return f"AGENT-SCHEDULE|schedule={manifest['schedule_key']}|block={block_key}|revision={manifest['revision']}"


def validate_readbacks(manifest: dict[str, Any]) -> None:
    validate_writes(manifest, allow_retain_without_marker=True)
    readbacks = result_map(manifest.get("readbacks"), "readbacks")
    require(set(readbacks) == expected_pairs(manifest), "readbacks must cover every profile and calendar block exactly once")
    blocks = {block["block_key"]: block for block in manifest["blocks"]}
    profiles = {profile["name"]: profile for profile in manifest["profiles"]}
    matches = result_map(manifest.get("matches"), "matches")
    for pair, result in readbacks.items():
        block = blocks[pair[1]]
        require(result.get("ok") is True, f"readback failed for {pair[0]} / {pair[1]}")
        if block["action"] == "delete":
            require(result.get("absent") is True, f"deleted event still exists for {pair[0]} / {pair[1]}")
            continue
        require(result.get("calendar_id") == profiles[pair[0]]["calendar_id"], f"readback calendar mismatch for {pair[0]} / {pair[1]}")
        require(result.get("summary") == block["title"], f"readback title mismatch for {pair[0]} / {pair[1]}")
        require(result.get("start") == block["start"] and result.get("end") == block["end"], f"readback time mismatch for {pair[0]} / {pair[1]}")
        require(result.get("timezone") == manifest["timezone"], f"readback timezone mismatch for {pair[0]} / {pair[1]}")
        require(result.get("visibility") == "public", f"readback visibility mismatch for {pair[0]} / {pair[1]}")
        require(result.get("free_busy_status") == "busy", f"readback busy status mismatch for {pair[0]} / {pair[1]}")
        require(result.get("vc_type") == "no_meeting", f"readback vc_type mismatch for {pair[0]} / {pair[1]}")
        require(result.get("attendees", []) == [] and result.get("room_ids", []) == [], f"unexpected attendees or rooms for {pair[0]} / {pair[1]}")
        if block["action"] == "retain":
            match_marker = retain_match_marker(matches[pair])
            actual_marker = str(result.get("marker", ""))
            expected = match_marker or actual_marker
            validate_retain_marker(manifest, pair[1], expected)
            require(actual_marker == expected, f"readback marker mismatch for {pair[0]} / {pair[1]}")
        else:
            require(result.get("marker") == expected_marker(manifest, pair[1]), f"readback marker mismatch for {pair[0]} / {pair[1]}")


VALIDATORS = {
    "collect": lambda manifest: None,
    "draft": validate_draft,
    "confirm": validate_confirmation,
    "preflight": validate_preflight,
    "dry-run": validate_dry_runs,
    "write": validate_dry_runs,
    "readback": validate_writes,
    "complete": validate_readbacks,
}


def transition(manifest: dict[str, Any], target: str, user_confirmed: bool) -> None:
    current_index = STAGES.index(manifest["state"])
    target_index = STAGES.index(target)
    require(target_index == current_index + 1, f"illegal transition: {manifest['state']} -> {target}")
    if target == "confirm":
        require(user_confirmed, "confirm transition requires --user-confirmed")
        validate_draft(manifest)
        manifest["confirmation"] = {"user_confirmed": True, "snapshot_sha256": snapshot_sha256(manifest)}
    VALIDATORS[target](manifest)
    manifest["state"] = target


def idempotency_key(profile_app_id: str, calendar_id: str, schedule_key: str, block_key: str) -> str:
    return str(uuid.uuid5(UUID_NAMESPACE, "|".join((profile_app_id, calendar_id, schedule_key, block_key))))


def command_transition(args: argparse.Namespace) -> int:
    path = Path(args.manifest)
    manifest = load_manifest(path)
    transition(manifest, args.to, args.user_confirmed)
    atomic_write(path, manifest)
    print(json.dumps({"ok": True, "state": manifest["state"], "snapshot_sha256": snapshot_sha256(manifest)}, ensure_ascii=False))
    return 0


def command_check(args: argparse.Namespace) -> int:
    manifest = load_manifest(Path(args.manifest))
    VALIDATORS[args.require_stage](manifest)
    require(STAGES.index(manifest["state"]) >= STAGES.index(args.require_stage), f"manifest state is {manifest['state']}, not {args.require_stage} or later")
    print(json.dumps({"ok": True, "state": manifest["state"], "required_stage": args.require_stage}, ensure_ascii=False))
    return 0


def file_sha256(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise GuardError(f"cannot read payload: {exc}") from exc


def command_check_write(args: argparse.Namespace) -> int:
    manifest = load_manifest(Path(args.manifest))
    payload_hash = validate_write_payload(manifest, args.profile, args.block_key, Path(args.payload))
    print(json.dumps({"ok": True, "profile": args.profile, "block_key": args.block_key, "request_sha256": payload_hash}, ensure_ascii=False))
    return 0


def validate_write_payload(manifest: dict[str, Any], profile: str, block_key: str, payload: Path) -> str:
    require(manifest["state"] == "write", f"manifest state is {manifest['state']}, not write")
    validate_dry_runs(manifest)
    pair = (profile, block_key)
    require(pair in expected_pairs(manifest, WRITE_ACTIONS), f"write is not authorized for {pair[0]} / {pair[1]}")
    dry_run = result_map(manifest.get("dry_runs"), "dry_runs")[pair]
    payload_hash = file_sha256(payload)
    require(payload_hash == dry_run["request_sha256"], f"payload differs from dry-run for {pair[0]} / {pair[1]}")
    return payload_hash


def command_reset_draft(args: argparse.Namespace) -> int:
    path = Path(args.manifest)
    manifest = load_manifest(path)
    require(STAGES.index(manifest["state"]) >= STAGES.index("confirm"), "reset-draft requires a confirmed or later manifest")
    manifest["revision"] = int(manifest.get("revision", 0)) + 1
    for field in ("confirmation", "matches", "dry_runs", "writes", "readbacks"):
        manifest.pop(field, None)
    manifest["state"] = "draft"
    validate_draft(manifest)
    atomic_write(path, manifest)
    print(json.dumps({"ok": True, "state": "draft", "revision": manifest["revision"]}, ensure_ascii=False))
    return 0


def command_key(args: argparse.Namespace) -> int:
    print(idempotency_key(args.profile_app_id, args.calendar_id, args.schedule_key, args.block_key))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    transition_parser = subparsers.add_parser("transition", help="validate and advance one stage atomically")
    transition_parser.add_argument("--manifest", required=True)
    transition_parser.add_argument("--to", required=True, choices=STAGES[1:])
    transition_parser.add_argument("--user-confirmed", action="store_true")
    transition_parser.set_defaults(func=command_transition)
    check_parser = subparsers.add_parser("check", help="assert that a stage gate is satisfied")
    check_parser.add_argument("--manifest", required=True)
    check_parser.add_argument("--require-stage", required=True, choices=STAGES)
    check_parser.set_defaults(func=command_check)
    check_write_parser = subparsers.add_parser("check-write", help="verify that the exact payload was dry-run and is authorized")
    check_write_parser.add_argument("--manifest", required=True)
    check_write_parser.add_argument("--profile", required=True)
    check_write_parser.add_argument("--block-key", required=True)
    check_write_parser.add_argument("--payload", required=True)
    check_write_parser.set_defaults(func=command_check_write)
    reset_parser = subparsers.add_parser("reset-draft", help="invalidate prior authorization and return to a new draft revision")
    reset_parser.add_argument("--manifest", required=True)
    reset_parser.set_defaults(func=command_reset_draft)
    key_parser = subparsers.add_parser("idempotency-key", help="generate the fixed UUIDv5 key")
    key_parser.add_argument("--profile-app-id", required=True)
    key_parser.add_argument("--calendar-id", required=True)
    key_parser.add_argument("--schedule-key", required=True)
    key_parser.add_argument("--block-key", required=True)
    key_parser.set_defaults(func=command_key)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return args.func(args)
    except GuardError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
