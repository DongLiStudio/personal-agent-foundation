#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import planner_guard as guard


def base_manifest() -> dict:
    return {
        "schema_version": 1,
        "state": "collect",
        "schedule_key": "2026-07-16",
        "revision": 1,
        "timezone": "Asia/Shanghai",
        "window": {"start": "2026-07-16T09:00:00+08:00", "end": "2026-07-16T18:00:00+08:00"},
        "collection": {
            "mode": "parallel",
            "cutoff": "2026-07-16T08:55:00+08:00",
            "branches": [
                {"id": "feishu", "status": "complete", "collected_at": "2026-07-16T08:57:00+08:00", "coverage": {"profiles": ["工作"]}, "errors": []},
                {"id": "obsidian", "status": "complete", "collected_at": "2026-07-16T08:56:00+08:00", "coverage": {"canvas": "仪表盘.canvas"}, "errors": []},
                {"id": "projects", "status": "complete", "collected_at": "2026-07-16T08:58:00+08:00", "coverage": {"projects": ["通用助手"]}, "errors": []},
            ],
        },
        "profiles": [{"name": "工作", "app_id": "cli_test", "user_open_id": "ou_test", "calendar_id": "cal_test", "calendar_write_scope": True}],
        "blocks": [{"block_key": "agent-scaffold", "title": "制作 Agent 脚手架", "start": "2026-07-16T09:00:00+08:00", "end": "2026-07-16T11:00:00+08:00", "action": "create", "reason": "今日核心交付", "sources": ["Feishu:task-guid"], "visibility": "public", "free_busy_status": "busy", "vc_type": "no_meeting", "attendees": [], "room_ids": []}],
        "unplanned": [], "risks": [],
        "matches": [{"profile": "工作", "block_key": "agent-scaffold", "calendar_id": "cal_test", "count": 0}],
        "dry_runs": [{"profile": "工作", "block_key": "agent-scaffold", "ok": True, "request_sha256": "a" * 64}],
        "writes": [{"profile": "工作", "block_key": "agent-scaffold", "ok": True, "event_id": "event_test", "request_sha256": "a" * 64}],
        "readbacks": [{"profile": "工作", "block_key": "agent-scaffold", "ok": True, "calendar_id": "cal_test", "summary": "制作 Agent 脚手架", "start": "2026-07-16T09:00:00+08:00", "end": "2026-07-16T11:00:00+08:00", "timezone": "Asia/Shanghai", "visibility": "public", "free_busy_status": "busy", "vc_type": "no_meeting", "attendees": [], "room_ids": [], "marker": "AGENT-SCHEDULE|schedule=2026-07-16|block=agent-scaffold|revision=1"}],
    }


def expect_error(fn, contains: str) -> None:
    try:
        fn()
    except guard.GuardError as exc:
        assert contains in str(exc), (contains, str(exc))
    else:
        raise AssertionError(f"expected GuardError containing {contains!r}")


def advance_to_complete(manifest: dict) -> None:
    for stage in guard.STAGES[1:]:
        guard.transition(manifest, stage, user_confirmed=(stage == "confirm"))


def test_happy_path() -> None:
    manifest = base_manifest()
    advance_to_complete(manifest)
    assert manifest["state"] == "complete"


def test_none_block_stays_out_of_calendar_pipeline() -> None:
    manifest = base_manifest()
    manifest["blocks"].append({
        "block_key": "flex-buffer", "title": "弹性留白",
        "start": "2026-07-16T11:00:00+08:00", "end": "2026-07-16T11:30:00+08:00",
        "action": "none", "reason": "保留切换和延误余量", "sources": ["planning-policy"],
        "attendees": [], "room_ids": [],
    })
    advance_to_complete(manifest)
    assert manifest["state"] == "complete"
    assert ("工作", "flex-buffer") not in guard.expected_pairs(manifest)
    assert ("工作", "flex-buffer") not in guard.expected_pairs(manifest, guard.WRITE_ACTIONS)


def retain_manifest() -> dict:
    manifest = base_manifest()
    manifest["revision"] = 5
    block = manifest["blocks"][0]
    block["action"] = "retain"
    manifest["matches"] = [{
        "profile": "工作", "block_key": "agent-scaffold", "calendar_id": "cal_test",
        "count": 1, "event_id": "event_test",
        "existing_marker": "AGENT-SCHEDULE|schedule=2026-07-16|block=agent-scaffold|revision=1",
        "existing_revision": 1,
    }]
    manifest["dry_runs"] = []
    manifest["writes"] = []
    manifest["readbacks"][0]["marker"] = "AGENT-SCHEDULE|schedule=2026-07-16|block=agent-scaffold|revision=1"
    return manifest


def test_retain_accepts_verified_existing_marker_revision() -> None:
    manifest = retain_manifest()
    advance_to_complete(manifest)
    assert manifest["state"] == "complete"


def test_retain_requires_existing_marker_at_preflight() -> None:
    manifest = retain_manifest()
    del manifest["matches"][0]["existing_marker"]
    del manifest["matches"][0]["existing_revision"]
    for stage in ("draft", "confirm"):
        guard.transition(manifest, stage, user_confirmed=(stage == "confirm"))
    expect_error(lambda: guard.transition(manifest, "preflight", False), "retain requires existing_marker")


def test_retain_marker_schedule_or_block_mismatch_fails() -> None:
    manifest = retain_manifest()
    manifest["matches"][0]["existing_marker"] = "AGENT-SCHEDULE|schedule=2026-07-15|block=agent-scaffold|revision=1"
    for stage in ("draft", "confirm"):
        guard.transition(manifest, stage, user_confirmed=(stage == "confirm"))
    expect_error(lambda: guard.transition(manifest, "preflight", False), "schedule mismatch")
    manifest = retain_manifest()
    manifest["matches"][0]["existing_marker"] = "AGENT-SCHEDULE|schedule=2026-07-16|block=other-block|revision=1"
    for stage in ("draft", "confirm"):
        guard.transition(manifest, stage, user_confirmed=(stage == "confirm"))
    expect_error(lambda: guard.transition(manifest, "preflight", False), "block mismatch")


def test_retain_readback_block_schedule_or_plan_mismatch_fails() -> None:
    manifest = retain_manifest()
    manifest["readbacks"][0]["marker"] = "AGENT-SCHEDULE|schedule=2026-07-16|block=other-block|revision=1"
    for stage in guard.STAGES[1:-1]:
        guard.transition(manifest, stage, user_confirmed=(stage == "confirm"))
    expect_error(lambda: guard.transition(manifest, "complete", False), "marker mismatch")
    manifest = retain_manifest()
    manifest["readbacks"][0]["start"] = "2026-07-16T09:30:00+08:00"
    for stage in guard.STAGES[1:-1]:
        guard.transition(manifest, stage, user_confirmed=(stage == "confirm"))
    expect_error(lambda: guard.transition(manifest, "complete", False), "time mismatch")


def test_create_and_update_still_require_current_revision_marker() -> None:
    for action in ("create", "update"):
        manifest = base_manifest()
        manifest["revision"] = 5
        manifest["blocks"][0]["action"] = action
        if action == "update":
            manifest["matches"][0] = {
                "profile": "工作", "block_key": "agent-scaffold", "calendar_id": "cal_test",
                "count": 1, "event_id": "event_test",
            }
        manifest["readbacks"][0]["marker"] = "AGENT-SCHEDULE|schedule=2026-07-16|block=agent-scaffold|revision=1"
        for stage in guard.STAGES[1:-1]:
            guard.transition(manifest, stage, user_confirmed=(stage == "confirm"))
        expect_error(lambda: guard.transition(manifest, "complete", False), "marker mismatch")


def test_none_block_rejects_calendar_metadata() -> None:
    manifest = base_manifest()
    manifest["blocks"].append({
        "block_key": "rest-buffer", "title": "普通休息",
        "description": "休息", "start": "2026-07-16T11:00:00+08:00", "end": "2026-07-16T11:15:00+08:00",
        "action": "none", "reason": "不占用日历", "sources": ["planning-policy"],
    })
    expect_error(lambda: guard.transition(manifest, "draft", False), "must not define calendar field description")


def test_illegal_transition() -> None:
    manifest = base_manifest()
    expect_error(lambda: guard.transition(manifest, "confirm", True), "illegal transition")


def test_incomplete_draft() -> None:
    manifest = base_manifest()
    del manifest["blocks"][0]["reason"]
    expect_error(lambda: guard.transition(manifest, "draft", False), "requires reason")


def test_missing_collection_branch_blocks_draft() -> None:
    manifest = base_manifest()
    manifest["collection"]["branches"].pop()
    expect_error(lambda: guard.transition(manifest, "draft", False), "must cover feishu")


def test_failed_collection_requires_user_waiver() -> None:
    manifest = base_manifest()
    branch = manifest["collection"]["branches"][1]
    branch["status"] = "failed"
    branch["errors"] = ["vault unavailable"]
    expect_error(lambda: guard.transition(manifest, "draft", False), "explicit user waiver")
    branch["user_waived"] = True
    guard.transition(manifest, "draft", False)
    assert manifest["state"] == "draft"


def test_confirmation_invalidated_by_change() -> None:
    manifest = base_manifest()
    guard.transition(manifest, "draft", False)
    guard.transition(manifest, "confirm", True)
    manifest["blocks"][0]["start"] = "2026-07-16T09:30:00+08:00"
    expect_error(lambda: guard.transition(manifest, "preflight", False), "confirmed plan changed")


def test_confirmation_invalidated_by_description_change() -> None:
    manifest = base_manifest()
    manifest["blocks"][0]["description"] = "说明一"
    guard.transition(manifest, "draft", False)
    guard.transition(manifest, "confirm", True)
    manifest["blocks"][0]["description"] = "说明二"
    expect_error(lambda: guard.transition(manifest, "preflight", False), "confirmed plan changed")


def test_confirmation_invalidated_by_task_handoff_change() -> None:
    manifest = base_manifest()
    manifest["task_handoffs"] = [{"task_guid": "guid-1", "impact": "add"}]
    guard.transition(manifest, "draft", False)
    guard.transition(manifest, "confirm", True)
    manifest["task_handoffs"][0]["impact"] = "remove"
    expect_error(lambda: guard.transition(manifest, "preflight", False), "confirmed plan changed")


def test_actual_calendar_required() -> None:
    manifest = base_manifest()
    manifest["profiles"][0]["calendar_id"] = "primary"
    manifest["matches"][0]["calendar_id"] = "primary"
    guard.transition(manifest, "draft", False)
    guard.transition(manifest, "confirm", True)
    expect_error(lambda: guard.transition(manifest, "preflight", False), "literal primary")


def test_duplicate_match_blocks() -> None:
    manifest = base_manifest()
    manifest["matches"][0]["count"] = 2
    guard.transition(manifest, "draft", False)
    guard.transition(manifest, "confirm", True)
    expect_error(lambda: guard.transition(manifest, "preflight", False), "duplicate or invalid")


def test_all_dry_runs_required() -> None:
    manifest = base_manifest()
    manifest["dry_runs"] = []
    for stage in ("draft", "confirm", "preflight"):
        guard.transition(manifest, stage, user_confirmed=(stage == "confirm"))
    expect_error(lambda: guard.transition(manifest, "dry-run", False), "must cover")


def test_readback_mismatch_blocks_complete() -> None:
    manifest = base_manifest()
    manifest["readbacks"][0]["vc_type"] = "meeting"
    for stage in guard.STAGES[1:-1]:
        guard.transition(manifest, stage, user_confirmed=(stage == "confirm"))
    expect_error(lambda: guard.transition(manifest, "complete", False), "vc_type mismatch")


def test_reset_invalidates_authorization() -> None:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "manifest.json"
        manifest = base_manifest()
        guard.transition(manifest, "draft", False)
        guard.transition(manifest, "confirm", True)
        guard.atomic_write(path, manifest)
        args = type("Args", (), {"manifest": str(path)})()
        guard.command_reset_draft(args)
        reset = guard.load_manifest(path)
        assert reset["state"] == "draft" and reset["revision"] == 2
        for field in ("confirmation", "matches", "dry_runs", "writes", "readbacks"):
            assert field not in reset


def test_write_payload_must_match_dry_run() -> None:
    manifest = base_manifest()
    manifest["writes"][0]["request_sha256"] = "b" * 64
    for stage in guard.STAGES[1:6]:
        guard.transition(manifest, stage, user_confirmed=(stage == "confirm"))
    expect_error(lambda: guard.transition(manifest, "readback", False), "payload changed after dry-run")


def test_check_write_uses_exact_payload_file() -> None:
    with tempfile.TemporaryDirectory() as directory:
        manifest_path = Path(directory) / "manifest.json"
        payload_path = Path(directory) / "request.json"
        payload_path.write_bytes(b'{"summary":"safe"}\n')
        manifest = base_manifest()
        payload_hash = guard.file_sha256(payload_path)
        manifest["dry_runs"][0]["request_sha256"] = payload_hash
        manifest["writes"][0]["request_sha256"] = payload_hash
        for stage in guard.STAGES[1:6]:
            guard.transition(manifest, stage, user_confirmed=(stage == "confirm"))
        guard.atomic_write(manifest_path, manifest)
        args = type("Args", (), {"manifest": str(manifest_path), "profile": "工作", "block_key": "agent-scaffold", "payload": str(payload_path)})()
        assert guard.command_check_write(args) == 0
        payload_path.write_bytes(b'{"summary":"changed"}\n')
        expect_error(lambda: guard.command_check_write(args), "payload differs from dry-run")


def test_uuid_is_stable_and_input_sensitive() -> None:
    first = guard.idempotency_key("app", "cal", "2026-07-16", "delivery")
    second = guard.idempotency_key("app", "cal", "2026-07-16", "delivery")
    changed = guard.idempotency_key("app", "cal", "2026-07-16", "another-delivery")
    assert first == second and first != changed
    assert str(guard.UUID_NAMESPACE) == "6ba7b811-9dad-11d1-80b4-00c04fd430c8"


def test_atomic_roundtrip() -> None:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "manifest.json"
        path.write_text(json.dumps(base_manifest(), ensure_ascii=False), encoding="utf-8")
        manifest = guard.load_manifest(path)
        guard.transition(manifest, "draft", False)
        guard.atomic_write(path, manifest)
        assert guard.load_manifest(path)["state"] == "draft"
        assert not path.read_bytes().startswith(b"\xef\xbb\xbf") and b"\r\n" not in path.read_bytes()


def main() -> None:
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_") and callable(value)]
    for test in tests:
        test()
    print(f"planner guard tests passed: {len(tests)}")


if __name__ == "__main__":
    main()
