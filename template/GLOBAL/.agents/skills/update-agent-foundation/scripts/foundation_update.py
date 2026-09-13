from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from typing import Iterable


class UpdateError(RuntimeError):
    pass


USER_STATE_FILES = {
    "PROJECTS.md", "OBSIDIAN_LINK.md", "LARK_PROFILES.md", "GITHUB_ACCOUNTS.md",
    "ALIYUN_PROFILES.md", "SERVER_PROFILES.md", "SCHEDULE_PREFERENCES.md",
    "FOUNDATION_STATE.json",
}
PLACEHOLDER = re.compile(r"\{\{[A-Z0-9_]+\}\}")
AGENT_ROOT_TOKEN = chr(123) * 2 + "AGENT_ROOT" + chr(125) * 2


def abs_path(path: Path) -> Path:
    return Path(os.path.abspath(path))


def is_within(path: Path, parent: Path) -> bool:
    try:
        abs_path(path).relative_to(abs_path(parent))
        return True
    except ValueError:
        return False


def is_link_like(path: Path) -> bool:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return False
    return path.is_symlink() or bool(
        getattr(metadata, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
    )


def ensure_plain_tree(path: Path, stop: Path) -> None:
    current, stop = abs_path(path), abs_path(stop)
    while is_within(current, stop):
        if is_link_like(current):
            raise UpdateError(f"linked path is not allowed: {current}")
        if current == stop:
            break
        current = current.parent


def safe_relative(value: str) -> Path:
    relative = Path(value)
    if relative.is_absolute() or not relative.parts or ".." in relative.parts:
        raise UpdateError(f"unsafe relative path: {value}")
    return relative


def file_hash(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_text(path: Path) -> str:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise UpdateError(f"UTF-8 BOM is not allowed: {path}")
    return raw.decode("utf-8")


def rendered_bytes(path: Path, root: Path) -> bytes:
    text = read_text(path).replace(AGENT_ROOT_TOKEN, str(root))
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def bytes_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def iter_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for current, dirs, names in os.walk(root, followlinks=False):
        current_path = Path(current)
        for name in list(dirs):
            if is_link_like(current_path / name):
                raise UpdateError(f"linked source directory is not allowed: {current_path / name}")
        for name in names:
            candidate = current_path / name
            if is_link_like(candidate):
                raise UpdateError(f"linked source file is not allowed: {candidate}")
            files.append(candidate)
    return sorted(files)


def source_commit(source: Path) -> str | None:
    result = subprocess.run(
        ["git", "-C", str(source), "rev-parse", "HEAD"], capture_output=True,
        text=True, check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def classify(relative: Path, target_exists: bool) -> str:
    posix = relative.as_posix()
    if relative.name in USER_STATE_FILES or posix.startswith("servers/"):
        return "preserve_user_state"
    if posix.startswith(".agents/skills/"):
        return "replace_managed" if target_exists else "add_missing"
    return "review_merge" if target_exists else "add_missing"


def build_report(root: Path, source: Path) -> dict:
    root, source = abs_path(root), abs_path(source)
    global_root, template_root = root / "GLOBAL", source / "template" / "GLOBAL"
    blocking: list[str] = []
    if not global_root.is_dir():
        blocking.append(f"missing installed GLOBAL: {global_root}")
    if not template_root.is_dir() or not (source / "template-manifest.json").is_file():
        blocking.append("source must contain template-manifest.json and template/GLOBAL")
    if blocking:
        return {"root": str(root), "source": str(source), "blocking_issues": blocking, "items": []}
    ensure_plain_tree(template_root, source)
    items = []
    for source_file in iter_files(template_root):
        relative = source_file.relative_to(template_root)
        target = global_root / relative
        kind = classify(relative, target.exists())
        expected = rendered_bytes(source_file, root)
        placeholders = sorted(set(PLACEHOLDER.findall(expected.decode("utf-8"))))
        before, expected_hash = file_hash(target), bytes_hash(expected)
        if before == expected_hash:
            kind = "unchanged"
        if placeholders and kind in {"add_missing", "replace_managed"}:
            blocking.append(
                f"unresolved placeholders in {relative.as_posix()}: {', '.join(placeholders)}"
            )
        items.append({
            "path": relative.as_posix(), "kind": kind, "before_sha256": before,
            "expected_sha256": expected_hash, "placeholders": placeholders,
        })
    return {
        "schema_version": 1, "root": str(root), "source": str(source),
        "source_commit": source_commit(source),
        "blocking_issues": sorted(set(blocking)), "items": items,
    }


def plan_digest(plan: dict) -> str:
    unsigned = {key: value for key, value in plan.items() if key != "plan_sha256"}
    payload = json.dumps(unsigned, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def make_plan(root: Path, source: Path) -> dict:
    plan = build_report(root, source)
    plan["actions"] = [
        item for item in plan.get("items", [])
        if item["kind"] in {"add_missing", "replace_managed"}
    ]
    plan["review_merge"] = [
        item for item in plan.get("items", []) if item["kind"] == "review_merge"
    ]
    plan["preserved"] = [
        item for item in plan.get("items", []) if item["kind"] == "preserve_user_state"
    ]
    plan["plan_sha256"] = plan_digest(plan)
    return plan


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="\n", delete=False, dir=path.parent
    ) as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temp_path = Path(handle.name)
    os.replace(temp_path, path)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", delete=False, dir=path.parent) as handle:
        handle.write(data)
        temp_path = Path(handle.name)
    os.replace(temp_path, path)


def apply_plan(plan_path: Path, confirmation: str) -> dict:
    plan = load_json(plan_path)
    expected = plan_digest(plan)
    if plan.get("plan_sha256") != expected or confirmation != expected:
        raise UpdateError("plan hash mismatch or plan was not confirmed")
    if plan.get("blocking_issues"):
        raise UpdateError("plan contains blocking issues")
    root, source = abs_path(Path(plan["root"])), abs_path(Path(plan["source"]))
    if make_plan(root, source)["plan_sha256"] != expected:
        raise UpdateError("source or target changed after planning")
    run_id = (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        + "-" + expected[:8] + "-" + uuid.uuid4().hex[:8]
    )
    run_root = root / "GLOBAL" / ".foundation-update" / run_id
    records = []
    for action in plan["actions"]:
        relative = safe_relative(action["path"])
        source_file = source / "template" / "GLOBAL" / relative
        target = root / "GLOBAL" / relative
        ensure_plain_tree(target.parent, root / "GLOBAL")
        if file_hash(target) != action["before_sha256"]:
            raise UpdateError(f"target changed after planning: {relative.as_posix()}")
        existed = target.exists()
        if existed:
            backup = run_root / "before" / relative
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, backup)
        atomic_write(target, rendered_bytes(source_file, root))
        records.append({
            "path": relative.as_posix(), "existed": existed,
            "before_sha256": action["before_sha256"], "after_sha256": file_hash(target),
        })
    manifest = {
        "schema_version": 1, "root": str(root), "source": str(source),
        "source_commit": plan.get("source_commit"), "plan_sha256": expected,
        "records": records, "review_merge": plan.get("review_merge", []),
    }
    manifest_path = run_root / "run-manifest.json"
    write_json(manifest_path, manifest)
    return {**manifest, "run_manifest": str(manifest_path)}


def verify(root: Path, source: Path) -> dict:
    report = build_report(root, source)
    pending = [
        item for item in report.get("items", [])
        if item["kind"] in {"add_missing", "replace_managed"}
    ]
    return {
        "root": report.get("root"), "source": report.get("source"),
        "source_commit": report.get("source_commit"),
        "blocking_issues": report.get("blocking_issues", []),
        "managed_pending": pending,
        "review_merge": [
            item for item in report.get("items", []) if item["kind"] == "review_merge"
        ],
        "preserved": [
            item for item in report.get("items", []) if item["kind"] == "preserve_user_state"
        ],
        "deterministic_update_ok": not report.get("blocking_issues") and not pending,
    }


def rollback(manifest_path: Path) -> dict:
    manifest_path = abs_path(manifest_path)
    manifest = load_json(manifest_path)
    root, run_root = abs_path(Path(manifest["root"])), manifest_path.parent
    restored = []
    for record in reversed(manifest["records"]):
        relative = safe_relative(record["path"])
        target = root / "GLOBAL" / relative
        if file_hash(target) != record["after_sha256"]:
            raise UpdateError(f"refusing to overwrite post-update change: {relative.as_posix()}")
        if record["existed"]:
            backup = run_root / "before" / relative
            if file_hash(backup) != record["before_sha256"]:
                raise UpdateError(f"backup mismatch: {relative.as_posix()}")
            atomic_write(target, backup.read_bytes())
        else:
            target.unlink()
        restored.append(relative.as_posix())
    return {"root": str(root), "restored": restored}


def build_parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser()
    sub = root.add_subparsers(dest="command", required=True)
    for name in ("audit", "plan", "verify"):
        command = sub.add_parser(name)
        command.add_argument("--root", required=True, type=Path)
        command.add_argument("--source", required=True, type=Path)
        command.add_argument("--report", type=Path)
    apply_command = sub.add_parser("apply")
    apply_command.add_argument("--plan", required=True, type=Path)
    apply_command.add_argument("--confirm-plan-sha256", required=True)
    rollback_command = sub.add_parser("rollback")
    rollback_command.add_argument("--run-manifest", required=True, type=Path)
    return root


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "audit":
            result = build_report(args.root, args.source)
        elif args.command == "plan":
            result = make_plan(args.root, args.source)
        elif args.command == "verify":
            result = verify(args.root, args.source)
        elif args.command == "apply":
            result = apply_plan(args.plan, args.confirm_plan_sha256)
        else:
            result = rollback(args.run_manifest)
        if getattr(args, "report", None):
            write_json(args.report, result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, UpdateError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
