#!/usr/bin/env python3
"""Classify Feishu task changes that require personal schedule replanning."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


INACTIVE_STATUSES = {"cancelled", "canceled", "closed", "completed", "done"}
TIME_FIELDS = ("start", "due")


class HandoffError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise HandoffError(message)


def parse_time(value: Any, label: str) -> datetime | None:
    if value in (None, ""):
        return None
    require(isinstance(value, str), f"{label} must be an ISO 8601 string or null")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise HandoffError(f"{label} is not valid ISO 8601: {value}") from exc
    require(parsed.tzinfo is not None, f"{label} must include a timezone offset")
    return parsed


def is_active(state: dict[str, Any] | None) -> bool:
    if not state:
        return False
    return str(state.get("status") or "todo").strip().lower() not in INACTIVE_STATUSES


def is_executor(state: dict[str, Any] | None, current_user: str) -> bool:
    if not state:
        return False
    assignees = state.get("assignee_open_ids", [])
    require(isinstance(assignees, list), "assignee_open_ids must be a list")
    return current_user in {str(value) for value in assignees}


def interval(state: dict[str, Any] | None, prefix: str) -> tuple[datetime | None, datetime | None]:
    if not state:
        return None, None
    start = parse_time(state.get("start"), f"{prefix}.start")
    due = parse_time(state.get("due"), f"{prefix}.due")
    if start and due:
        require(start <= due, f"{prefix}.start must not be after due")
    return start, due


def touches_window(state: dict[str, Any] | None, window_start: datetime, window_end: datetime) -> bool:
    start, due = interval(state, "state")
    if start and due:
        return start < window_end and due >= window_start
    point = start or due
    return bool(point and window_start <= point < window_end)


def changed(before: dict[str, Any] | None, after: dict[str, Any] | None, field: str) -> bool:
    return (before or {}).get(field) != (after or {}).get(field)


def managed_scope(
    state: dict[str, Any] | None,
    today_start: datetime,
    today_end: datetime,
    has_managed_schedule: bool,
) -> bool:
    if not state:
        return False
    return touches_window(state, today_start, today_end) or has_managed_schedule


def classify(change: dict[str, Any], today_start: datetime, today_end: datetime) -> dict[str, Any]:
    for field in ("task_guid", "profile", "project_name", "project_root", "current_user_open_id"):
        require(change.get(field), f"each change requires {field}")
    before = change.get("before")
    after = change.get("after")
    require(before is None or isinstance(before, dict), "before must be an object or null")
    require(after is None or isinstance(after, dict), "after must be an object or null")
    require(after is not None, "after readback state is required")
    for field in ("before_target_has_managed_schedule", "after_target_has_managed_schedule"):
        require(isinstance(change.get(field), bool), f"each change requires boolean {field}")

    current_user = str(change["current_user_open_id"])
    before_executor = is_executor(before, current_user)
    after_executor = is_executor(after, current_user)
    before_active = is_active(before)
    after_active = is_active(after)
    before_window = managed_scope(
        before,
        today_start,
        today_end,
        change["before_target_has_managed_schedule"],
    )
    after_window = managed_scope(
        after,
        today_start,
        today_end,
        change["after_target_has_managed_schedule"],
    )
    explicit = change.get("explicit_schedule_request") is True
    reasons: list[str] = []

    if explicit and after_executor and after_active:
        reasons.append("explicit_schedule_request")
    if before is None and after_executor and after_active and after_window:
        reasons.append("created_in_window")
    if not before_window and after_window and after_executor and after_active:
        reasons.append("enters_window")
    if before_window and not after_window and before_executor and before_active:
        reasons.append("leaves_window")
    time_changed = any(changed(before, after, field) for field in TIME_FIELDS)
    if time_changed and before_window and after_window and (before_executor or after_executor):
        reasons.append("moves_within_window")
    if not before_executor and after_executor and after_active and (after_window or explicit):
        reasons.append("execution_assigned_to_current_user")
    if before_executor and not after_executor and before_window:
        reasons.append("execution_removed_from_current_user")
    status_changed = changed(before, after, "status")
    if status_changed and before_executor and before_active and not after_active and before_window:
        reasons.append("task_completed_or_cancelled")
    if status_changed and after_executor and not before_active and after_active and (after_window or explicit):
        reasons.append("task_reopened")
    workload_changed = changed(before, after, "estimated_minutes")
    if workload_changed and (before_executor or after_executor) and (before_window or after_window):
        reasons.append("workload_changed")

    reasons = list(dict.fromkeys(reasons))
    if not reasons:
        impact = "none"
    elif before_executor and before_active and before_window and not (after_executor and after_active and after_window):
        impact = "remove"
    elif after_executor and after_active and (after_window or explicit) and not (before_executor and before_active and before_window):
        impact = "add"
    else:
        impact = "replan"
    return {
        "task_guid": str(change["task_guid"]),
        "profile": str(change["profile"]),
        "project_name": str(change["project_name"]),
        "project_root": str(change["project_root"]),
        "trigger": bool(reasons),
        "impact": impact,
        "reasons": reasons,
        "before": before,
        "after": after,
    }


def evaluate(payload: dict[str, Any]) -> dict[str, Any]:
    require(payload.get("schema_version") == 3, "schema_version must be 3")
    require(payload.get("timezone"), "timezone is required")
    parse_time(payload.get("now"), "now")
    window = payload.get("today_window")
    require(isinstance(window, dict), "today_window is required")
    window_start = parse_time(window.get("start"), "today_window.start")
    window_end = parse_time(window.get("end"), "today_window.end")
    require(window_start is not None and window_end is not None and window_start < window_end, "today_window must have start < end")
    changes = payload.get("changes")
    require(isinstance(changes, list) and changes, "changes must be a non-empty list")
    task_ids: set[tuple[str, str]] = set()
    handoffs: list[dict[str, Any]] = []
    ignored: list[dict[str, Any]] = []
    for change in changes:
        require(isinstance(change, dict), "each change must be an object")
        key = (str(change.get("profile", "")), str(change.get("task_guid", "")))
        require(key not in task_ids, f"duplicate change: {key[0]} / {key[1]}")
        task_ids.add(key)
        result = classify(change, window_start, window_end)
        (handoffs if result["trigger"] else ignored).append(result)
    return {"schema_version": 3, "trigger": bool(handoffs), "handoffs": handoffs, "ignored": ignored}


def read_input(value: str) -> dict[str, Any]:
    try:
        text = sys.stdin.read() if value == "-" else Path(value).read_text(encoding="utf-8-sig")
        payload = json.loads(text)
    except (OSError, json.JSONDecodeError) as exc:
        raise HandoffError(f"cannot read input: {exc}") from exc
    require(isinstance(payload, dict), "input root must be an object")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="input JSON path or - for stdin")
    args = parser.parse_args()
    try:
        result = evaluate(read_input(args.input))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except HandoffError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
