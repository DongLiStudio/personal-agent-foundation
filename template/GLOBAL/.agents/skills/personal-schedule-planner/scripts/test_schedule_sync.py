#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import tempfile
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("schedule_sync", ROOT / "schedule_sync.py")
assert spec and spec.loader
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)


def block(key: str, action: str, title: str) -> dict:
    return {
        "block_key": key, "title": title,
        "start": "2026-07-16T09:00:00+08:00", "end": "2026-07-16T10:00:00+08:00",
        "action": action, "reason": "fixture", "sources": ["fixture"],
        "visibility": "public", "free_busy_status": "busy", "vc_type": "no_meeting",
        "attendees": [], "room_ids": [],
    }


def blank_block(key: str, title: str) -> dict:
    return {
        "block_key": key, "title": title,
        "start": "2026-07-16T10:00:00+08:00", "end": "2026-07-16T10:30:00+08:00",
        "action": "none", "reason": "保留弹性", "sources": ["planning-policy"],
        "attendees": [], "room_ids": [],
    }


def manifest() -> dict:
    blocks = [
        block("create-block", "create", "创建事项"),
        block("update-block", "update", "更新事项"),
        block("retain-block", "retain", "保留事项"),
        block("delete-block", "delete", "删除事项"),
        blank_block("flex-buffer", "弹性留白"),
    ]
    profile = {
        "name": "fixture-profile", "app_id": "cli_fixture", "user_open_id": "ou_fixture",
        "calendar_id": "fixture@example.invalid", "calendar_write_scope": True,
    }
    matches = []
    for item in blocks:
        if item["action"] == "none":
            continue
        match = {"profile": profile["name"], "block_key": item["block_key"], "calendar_id": profile["calendar_id"]}
        if item["action"] == "create":
            match["count"] = 0
        else:
            match.update({"count": 1, "event_id": f"event-{item['block_key']}"})
            if item["action"] == "retain":
                match["existing_marker"] = "AGENT-SCHEDULE|schedule=2026-07-16|block=retain-block|revision=1"
                match["existing_revision"] = 1
        matches.append(match)
    return {
        "schema_version": 1, "state": "preflight", "schedule_key": "2026-07-16", "revision": 5,
        "timezone": "Asia/Shanghai", "window": {"start": blocks[0]["start"], "end": blocks[0]["end"]},
        "collection": {"mode": "sequential", "cutoff": "2026-07-16T08:00:00+08:00", "branches": [
            {"id": name, "status": "complete", "collected_at": "2026-07-16T08:00:00+08:00", "coverage": {"ok": True}, "errors": []}
            for name in ("feishu", "obsidian", "projects")
        ]},
        "profiles": [profile], "blocks": blocks, "unplanned": [], "risks": [], "matches": matches,
        "confirmation": {"user_confirmed": True, "snapshot_sha256": "pending"},
    }


def response_bytes(value: dict, dry_run: bool = False) -> bytes:
    prefix = "=== Dry Run ===\n" if dry_run else ""
    return (prefix + json.dumps(value, ensure_ascii=False)).encode("utf-8")


def fake_run_factory(fail_once: set[str] | None = None):
    attempts: dict[str, int] = {}
    descriptions: dict[str, str] = {}
    fail_once = fail_once or set()

    def fake_run(_executable: str, argv: list[str], stdin: bytes | None = None):
        dry = "--dry-run" in argv
        profile = argv[argv.index("--profile") + 1]
        if "get" in argv:
            event_id = argv[argv.index("--event-id") + 1]
            key = event_id.removeprefix("event-")
            status = "cancelled" if key == "delete-block" else "confirmed"
            event = {
                "event_id": event_id, "summary": {"create-block": "创建事项", "update-block": "更新事项", "retain-block": "保留事项"}.get(key, "删除事项"),
                "description": descriptions.get(key, f"AGENT-SCHEDULE|schedule=2026-07-16|block={key}|revision=1"),
                "start_time": {"timestamp": "1784163600", "timezone": "Asia/Shanghai"},
                "end_time": {"timestamp": "1784167200", "timezone": "Asia/Shanghai"},
                "visibility": "public", "free_busy_status": "busy", "vchat": {"vc_type": "no_meeting"},
                "attendees": [], "status": status,
            }
            return mock.Mock(returncode=0, stdout=response_bytes({"ok": True, "data": {"event": event}}), stderr=b"")
        action = "create" if "create" in argv else "update" if "patch" in argv else "delete"
        body = json.loads(stdin.decode("utf-8")) if stdin else {}
        key = body.get("description", "").split("block=")[-1].split("|")[0] if body else "delete-block"
        pair = f"{profile}/{key}"
        attempts[pair] = attempts.get(pair, 0) + 1
        if not dry and pair in fail_once and attempts[pair] == 2:
            return mock.Mock(returncode=1, stdout=b"", stderr=b'{"ok":false,"error":{"message":"fixture failure"}}')
        if dry:
            return mock.Mock(returncode=0, stdout=response_bytes({"api": [{"method": "POST"}]}, True), stderr=b"")
        event_id = f"event-{key}"
        if body.get("description"):
            descriptions[key] = body["description"]
        data = {} if action == "delete" else {"event": {"event_id": event_id, "app_link": f"https://example/{key}"}}
        return mock.Mock(returncode=0, stdout=response_bytes({"ok": True, "data": data}), stderr=b"")

    return fake_run, attempts


def write_manifest(path: Path, data: dict) -> None:
    data["confirmation"]["snapshot_sha256"] = sync.guard.snapshot_sha256(data)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def test_end_to_end() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        manifest_path = root / "manifest.json"
        request_root = root / "requests"
        write_manifest(manifest_path, manifest())
        fake_run, _ = fake_run_factory()
        with mock.patch.object(sync, "run_cli", fake_run):
            sync.dry_run(manifest_path, request_root, "fake")
            assert sync.load(manifest_path)["state"] == "dry-run"
            sync.write(manifest_path, request_root, "fake")
            assert sync.load(manifest_path)["state"] == "readback"
            sync.readback(manifest_path, "fake")
        result = sync.load(manifest_path)
        assert result["state"] == "complete"
        assert len(result["dry_runs"]) == 3
        assert len(result["writes"]) == 3
        assert len(result["readbacks"]) == 4
        assert len(list(request_root.glob("*.json"))) == 3
        assert all("flex-buffer" not in path.name for path in request_root.glob("*.json"))


def test_retain_readback_backfills_legacy_match_marker() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        manifest_path = root / "manifest.json"
        request_root = root / "requests"
        write_manifest(manifest_path, manifest())
        fake_run, _ = fake_run_factory()
        with mock.patch.object(sync, "run_cli", fake_run):
            sync.dry_run(manifest_path, request_root, "fake")
            sync.write(manifest_path, request_root, "fake")
            data = sync.load(manifest_path)
            for match in data["matches"]:
                if match["block_key"] == "retain-block":
                    match.pop("existing_marker")
                    match.pop("existing_revision")
            sync.save(manifest_path, data)
            sync.readback(manifest_path, "fake")
        result = sync.load(manifest_path)
        retain_match = next(item for item in result["matches"] if item["block_key"] == "retain-block")
        assert result["state"] == "complete"
        assert retain_match["existing_revision"] == 1
        assert retain_match["existing_marker"].endswith("revision=1")


def test_retain_existing_marker_mismatch_blocks_readback() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        manifest_path = root / "manifest.json"
        request_root = root / "requests"
        data = manifest()
        for match in data["matches"]:
            if match["block_key"] == "retain-block":
                match["existing_marker"] = "AGENT-SCHEDULE|schedule=2026-07-16|block=other-block|revision=1"
                match["existing_revision"] = 1
        write_manifest(manifest_path, data)
        fake_run, _ = fake_run_factory()
        with mock.patch.object(sync, "run_cli", fake_run):
            try:
                sync.dry_run(manifest_path, request_root, "fake")
            except sync.guard.GuardError as exc:
                assert "block mismatch" in str(exc)
            else:
                raise AssertionError("retain marker mismatch was not blocked")


def test_payload_mutation_is_blocked() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        manifest_path = root / "manifest.json"
        request_root = root / "requests"
        write_manifest(manifest_path, manifest())
        fake_run, _ = fake_run_factory()
        with mock.patch.object(sync, "run_cli", fake_run):
            sync.dry_run(manifest_path, request_root, "fake")
            target = next(request_root.glob("*.json"))
            target.write_text(target.read_text(encoding="utf-8") + " ", encoding="utf-8")
            try:
                sync.write(manifest_path, request_root, "fake")
            except sync.SyncError as exc:
                assert "differs from dry-run" in str(exc)
            else:
                raise AssertionError("mutated request was not blocked")


def test_partial_write_can_resume() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        manifest_path = root / "manifest.json"
        request_root = root / "requests"
        write_manifest(manifest_path, manifest())
        fake_run, attempts = fake_run_factory({"fixture-profile/update-block"})
        with mock.patch.object(sync, "run_cli", fake_run):
            sync.dry_run(manifest_path, request_root, "fake")
            try:
                sync.write(manifest_path, request_root, "fake")
            except sync.SyncError:
                pass
            else:
                raise AssertionError("fixture write should fail once")
            partial = sync.load(manifest_path)
            assert partial["state"] == "write"
            assert len(partial["writes"]) >= 1
            sync.write(manifest_path, request_root, "fake")
        assert sync.load(manifest_path)["state"] == "readback"
        assert attempts["fixture-profile/create-block"] == 2
        assert attempts["fixture-profile/update-block"] == 3


def test_output_parsing() -> None:
    preview = sync.parse_json_output("=== Dry Run ===\n{\"api\":[{\"body\":{\"summary\":\"中文\"}}]}".encode("utf-8"), dry_run=True)
    assert preview["api"][0]["body"]["summary"] == "中文"
    normal = sync.parse_json_output(b'{"ok":true,"data":{}}\ntrailing notice')
    assert normal["ok"] is True
    try:
        sync.parse_json_output(b'{"api":[]}', dry_run=True)
    except sync.SyncError:
        pass
    else:
        raise AssertionError("missing dry-run banner was not rejected")


def main() -> None:
    test_end_to_end()
    test_retain_readback_backfills_legacy_match_marker()
    test_retain_existing_marker_mismatch_blocks_readback()
    test_payload_mutation_is_blocked()
    test_partial_write_can_resume()
    test_output_parsing()
    print("schedule sync fixture tests passed")


if __name__ == "__main__":
    main()
