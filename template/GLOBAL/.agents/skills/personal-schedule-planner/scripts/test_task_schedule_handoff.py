#!/usr/bin/env python3
from __future__ import annotations

import task_schedule_handoff as handoff


USER = "ou_current"
OTHER = "ou_other"


def state(*, assignees=None, start=None, due=None, status="todo", minutes=60):
    return {
        "assignee_open_ids": assignees if assignees is not None else [USER],
        "start": start,
        "due": due,
        "status": status,
        "estimated_minutes": minutes,
    }


def change(guid: str, before, after, explicit=False, before_managed=False, after_managed=False):
    return {
        "task_guid": guid,
        "profile": "fixture",
        "project_name": "Fixture Project",
        "project_root": "D:\\Fixture Project",
        "current_user_open_id": USER,
        "explicit_schedule_request": explicit,
        "before_target_has_managed_schedule": before_managed,
        "after_target_has_managed_schedule": after_managed,
        "before": before,
        "after": after,
    }


def payload(changes):
    return {
        "schema_version": 3,
        "now": "2026-07-16T10:00:00+08:00",
        "timezone": "Asia/Shanghai",
        "today_window": {"start": "2026-07-16T00:00:00+08:00", "end": "2026-07-17T00:00:00+08:00"},
        "changes": changes,
    }


TODAY_START = "2026-07-16T13:00:00+08:00"
TODAY_DUE = "2026-07-16T18:00:00+08:00"
TOMORROW_START = "2026-07-17T13:00:00+08:00"
TOMORROW_DUE = "2026-07-17T18:00:00+08:00"


def one(item):
    result = handoff.evaluate(payload([item]))
    return result, (result["handoffs"] or result["ignored"])[0]


def test_create_today_for_current_user_triggers():
    result, item = one(change("create-today", None, state(start=TODAY_START, due=TODAY_DUE)))
    assert result["trigger"] and item["impact"] == "add" and "created_in_window" in item["reasons"]


def test_create_for_other_user_is_ignored():
    result, item = one(change("other-user", None, state(assignees=[OTHER], start=TODAY_START, due=TODAY_DUE)))
    assert not result["trigger"] and item["reasons"] == []


def test_today_moved_to_tomorrow_triggers_removal():
    result, item = one(change("move-out", state(start=TODAY_START, due=TODAY_DUE), state(start=TOMORROW_START, due=TOMORROW_DUE)))
    assert result["trigger"] and item["impact"] == "remove" and "leaves_window" in item["reasons"]


def test_tomorrow_moved_to_today_triggers_addition():
    result, item = one(change("move-in", state(start=TOMORROW_START, due=TOMORROW_DUE), state(start=TODAY_START, due=TODAY_DUE)))
    assert result["trigger"] and item["impact"] == "add" and "enters_window" in item["reasons"]


def test_create_tomorrow_without_managed_schedule_is_ignored():
    result, item = one(change("create-unplanned-tomorrow", None, state(start=TOMORROW_START, due=TOMORROW_DUE)))
    assert not result["trigger"] and item["impact"] == "none" and item["reasons"] == []


def test_create_tomorrow_due_only_without_managed_schedule_is_ignored():
    result, item = one(change("create-unplanned-tomorrow-due-only", None, state(start=None, due=TOMORROW_DUE)))
    assert not result["trigger"] and item["impact"] == "none" and item["reasons"] == []


def test_create_tomorrow_with_managed_schedule_triggers():
    result, item = one(change(
        "create-planned-tomorrow",
        None,
        state(start=TOMORROW_START, due=TOMORROW_DUE),
        after_managed=True,
    ))
    assert result["trigger"] and item["impact"] == "add" and "created_in_window" in item["reasons"]


def test_move_within_managed_tomorrow_replans():
    result, item = one(change(
        "move-managed-tomorrow",
        state(start=TOMORROW_START, due=TOMORROW_DUE),
        state(start="2026-07-17T15:00:00+08:00", due="2026-07-17T20:00:00+08:00"),
        before_managed=True,
        after_managed=True,
    ))
    assert result["trigger"] and item["impact"] == "replan" and "moves_within_window" in item["reasons"]


def test_move_within_today_replans():
    result, item = one(change("move-within", state(start=TODAY_START, due=TODAY_DUE), state(start="2026-07-16T15:00:00+08:00", due="2026-07-16T20:00:00+08:00")))
    assert result["trigger"] and item["impact"] == "replan" and "moves_within_window" in item["reasons"]


def test_description_only_change_is_ignored():
    before = state(start=TODAY_START, due=TODAY_DUE)
    after = dict(before)
    after["description"] = "new description"
    result, _ = one(change("description", before, after))
    assert not result["trigger"]


def test_execution_removed_triggers_removal():
    result, item = one(change("ownership-loss", state(start=TODAY_START, due=TODAY_DUE), state(assignees=[OTHER], start=TODAY_START, due=TODAY_DUE)))
    assert result["trigger"] and item["impact"] == "remove" and "execution_removed_from_current_user" in item["reasons"]


def test_completed_task_triggers_removal():
    result, item = one(change("complete", state(start=TODAY_START, due=TODAY_DUE), state(start=TODAY_START, due=TODAY_DUE, status="done")))
    assert result["trigger"] and item["impact"] == "remove" and "task_completed_or_cancelled" in item["reasons"]


def test_workload_change_replans():
    result, item = one(change("workload", state(start=TODAY_START, due=TODAY_DUE, minutes=30), state(start=TODAY_START, due=TODAY_DUE, minutes=120)))
    assert result["trigger"] and item["impact"] == "replan" and "workload_changed" in item["reasons"]


def test_explicit_request_without_date_triggers_for_executor():
    result, item = one(change("explicit", None, state(start=None, due=None), explicit=True))
    assert result["trigger"] and item["impact"] == "add" and "explicit_schedule_request" in item["reasons"]


def test_batch_is_aggregated_once():
    result = handoff.evaluate(payload([
        change("relevant", None, state(start=TODAY_START, due=TODAY_DUE)),
        change("irrelevant", None, state(assignees=[OTHER], start=TODAY_START, due=TODAY_DUE)),
    ]))
    assert result["trigger"] and len(result["handoffs"]) == 1 and len(result["ignored"]) == 1


def test_duplicate_task_change_is_rejected():
    duplicate = change("same", None, state(start=TODAY_START, due=TODAY_DUE))
    try:
        handoff.evaluate(payload([duplicate, duplicate]))
    except handoff.HandoffError as exc:
        assert "duplicate change" in str(exc)
    else:
        raise AssertionError("duplicate change was not rejected")


def test_source_project_is_required_and_preserved():
    item = change("project-source", None, state(start=TODAY_START, due=TODAY_DUE))
    result, classified = one(item)
    assert result["schema_version"] == 3
    assert classified["project_name"] == "Fixture Project"
    assert classified["project_root"] == "D:\\Fixture Project"
    del item["project_root"]
    try:
        one(item)
    except handoff.HandoffError as exc:
        assert "project_root" in str(exc)
    else:
        raise AssertionError("missing project_root was not rejected")


def test_managed_schedule_evidence_is_required():
    item = change("missing-evidence", None, state(start=TOMORROW_START, due=TOMORROW_DUE))
    del item["after_target_has_managed_schedule"]
    try:
        one(item)
    except handoff.HandoffError as exc:
        assert "after_target_has_managed_schedule" in str(exc)
    else:
        raise AssertionError("missing managed schedule evidence was not rejected")


def main():
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_") and callable(value)]
    for test in tests:
        test()
    print(f"task schedule handoff tests passed: {len(tests)}")


if __name__ == "__main__":
    main()
