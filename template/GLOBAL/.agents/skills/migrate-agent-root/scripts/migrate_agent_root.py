#!/usr/bin/env python3
"""Deterministic Agent root migration planner/executor/verifier."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


TEXT_EXTENSIONS = {
    ".md", ".txt", ".yaml", ".yml", ".json", ".toml", ".ini", ".cfg",
    ".ps1", ".sh", ".py", ".js", ".ts", ".css", ".html", ".xml", ".csv",
    ".env", ".lock", ".gitignore", ".gitattributes",
}
TEXT_NAMES = {"README", "LICENSE", "AGENTS.md", "STATUS.md", "PROJECTS.md", "GLOBAL_CONTEXT.md", "SKILL.md"}
REGENERABLE_DIR_NAMES = {
    "__pycache__": "Python bytecode cache",
    ".pytest_cache": "pytest cache",
    ".mypy_cache": "mypy cache",
    "node_modules": "installed JavaScript dependencies",
    "dist": "generated distribution output",
}
REGENERABLE_PATH_SUFFIXES = {
    ("src-tauri", "target"): "generated Tauri/Rust build output",
    ("src-tauri", "target-next"): "generated Tauri/Rust build output",
}
SECRET_RE = re.compile(r"(?i)(api[_-]?key|secret|token|password|passwd|private[_-]?key)\s*[:=]\s*['\"]?[^'\"\s]{8,}")
ALLOWED_ALIGN_STATUSES = {"aligned", "no_change_needed"}
ATTENTION_ALIGN_STATUSES = {"needs_manual_decision", "blocked"}
MAX_BINARY_SCAN_BYTES = 1024 * 1024


def lexical_abs(path: Path) -> Path:
    return Path(os.path.abspath(path))


@dataclass
class Manifest:
    schema_version: int = 1
    mode: str = ""
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source: str = ""
    destination: str = ""
    dry_run: bool = True
    same_drive: bool | None = None
    status: str = "planned"
    errors: list[str] = field(default_factory=list)
    summary: dict[str, int] = field(default_factory=dict)
    copy_plan: dict[str, list[dict[str, object]]] = field(default_factory=lambda: {
        "directories": [], "files": [], "links": [], "skipped": []
    })
    rewrites: list[dict[str, object]] = field(default_factory=list)
    git_repositories: list[str] = field(default_factory=list)
    verification: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return self.__dict__


def is_link_or_reparse(path: Path) -> bool:
    if path.is_symlink():
        return True
    if os.name == "nt":
        try:
            return bool(path.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)
        except Exception:
            return False
    return False


def is_text_candidate(path: Path) -> bool:
    return path.suffix.lower() in TEXT_EXTENSIONS or path.name in TEXT_NAMES


def link_type(path: Path) -> str:
    if path.is_symlink():
        return "symlink"
    if is_link_or_reparse(path):
        return "reparse"
    return "none"


def existing_path_chain(path: Path) -> list[Path]:
    absolute = lexical_abs(path)
    current = absolute
    while not current.exists() and current != current.parent:
        current = current.parent
    chain: list[Path] = []
    while True:
        chain.append(current)
        if current == current.parent:
            break
        current = current.parent
    return list(reversed(chain))


def has_link_or_reparse_in_existing_chain(path: Path) -> bool:
    return any(is_link_or_reparse(item) for item in existing_path_chain(path))


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def path_variants(old_root: Path, new_root: Path) -> list[tuple[str, str, str]]:
    old_raw = str(old_root)
    new_raw = str(new_root)
    variants = [
        ("native", old_raw, new_raw),
        ("posix", old_raw.replace("\\", "/"), new_raw.replace("\\", "/")),
        ("json-escaped", old_raw.replace("\\", "\\\\"), new_raw.replace("\\", "\\\\")),
    ]
    deduped: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for name, old, new in variants:
        if old and old not in seen:
            deduped.append((name, old, new))
            seen.add(old)
    return deduped


def relative(path: Path, root: Path) -> str:
    return str(path.relative_to(root)).replace("\\", "/")


def regenerable_reason(path: Path, root: Path) -> str | None:
    if path.name in REGENERABLE_DIR_NAMES:
        return REGENERABLE_DIR_NAMES[path.name]
    parts = tuple(path.relative_to(root).parts)
    for suffix, reason in REGENERABLE_PATH_SUFFIXES.items():
        if parts[-len(suffix):] == suffix:
            return reason
    return None


def summarize_skipped_directory(path: Path, root: Path, reason: str) -> dict[str, object]:
    files = 0
    bytes_total = 0
    for dirpath, dirnames, filenames in os.walk(path, topdown=True, followlinks=False):
        current = Path(dirpath)
        dirnames[:] = [name for name in dirnames if not is_link_or_reparse(current / name)]
        for filename in filenames:
            item = current / filename
            if is_link_or_reparse(item):
                continue
            try:
                bytes_total += item.stat().st_size
                files += 1
            except OSError:
                continue
    return {
        "path": relative(path, root),
        "reason": reason,
        "action": "exclude_regenerable_directory",
        "files": files,
        "bytes": bytes_total,
    }


def iter_tree(root: Path, skipped: list[dict[str, object]] | None = None) -> Iterable[Path]:
    for dirpath, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
        current = Path(dirpath)
        kept = []
        for dirname in dirnames:
            child = current / dirname
            reason = regenerable_reason(child, root)
            if reason:
                if skipped is not None:
                    skipped.append(summarize_skipped_directory(child, root, reason))
                continue
            if is_link_or_reparse(child):
                yield child
                continue
            yield child
            kept.append(dirname)
        dirnames[:] = kept
        for filename in filenames:
            yield current / filename


def has_reparse_parent(path: Path, stop: Path) -> bool:
    current = path.parent
    stop = stop.resolve()
    while True:
        if current.exists() and is_link_or_reparse(current):
            return True
        if current == stop or current == current.parent:
            return False
        current = current.parent


def validate_boundaries(source: Path, destination: Path, manifest: Manifest, allow_existing_destination: bool = False) -> bool:
    if not source.exists() or not source.is_dir():
        manifest.errors.append(f"source is not an existing directory: {source}")
    if has_link_or_reparse_in_existing_chain(source):
        manifest.errors.append(f"source path contains a link or reparse point: {source}")
    if has_link_or_reparse_in_existing_chain(destination):
        manifest.errors.append(f"destination path or existing parent contains a link or reparse point: {destination}")
    if (source / "GLOBAL").exists() is False:
        manifest.errors.append("source does not contain expected GLOBAL directory")
    if destination == source or source in destination.parents:
        manifest.errors.append("destination must not equal source or be inside source")
    if destination.exists() and not allow_existing_destination:
        manifest.errors.append(f"destination already exists; refusing overwrite/merge: {destination}")
    if destination.exists() and allow_existing_destination and not destination.is_dir():
        manifest.errors.append(f"destination exists but is not a directory: {destination}")
    return not manifest.errors


def build_plan(source: Path, destination: Path, manifest: Manifest) -> None:
    variants = path_variants(source, destination)
    counts = {"directories": 0, "files": 0, "bytes": 0, "links": 0, "rewrite_files": 0, "rewrite_hits": 0,
              "skipped_directories": 0, "skipped_files": 0, "skipped_bytes": 0}
    for item in iter_tree(source, manifest.copy_plan["skipped"]):
        rel = relative(item, source)
        dest = destination / rel
        if is_link_or_reparse(item):
            target = os.readlink(item) if item.is_symlink() else str(item.resolve())
            target_text = str(target)
            internal = False
            destination_target = target_text
            try:
                resolved_target = (item.parent / target_text).resolve() if item.is_symlink() and not Path(target_text).is_absolute() else Path(target_text).resolve()
                internal = source == resolved_target or source in resolved_target.parents
                if internal:
                    destination_target = str(destination / resolved_target.relative_to(source))
            except Exception:
                resolved_target = None
            manifest.copy_plan["links"].append({
                "path": rel,
                "target": target_text,
                "destination_target": destination_target,
                "link_type": link_type(item),
                "is_dir": item.is_dir(),
                "internal_to_source": internal,
                "target_has_old_root": any(old in target_text for _name, old, _new in variants),
                "action": "rebuild_link_body",
            })
            counts["links"] += 1
            continue
        if item.is_dir():
            manifest.copy_plan["directories"].append({"path": rel})
            counts["directories"] += 1
            if item.name == ".git":
                manifest.git_repositories.append(str(Path(rel).parent).replace("\\", "/") or ".")
                git = subprocess.run(
                    ["git", "-C", str(item.parent), "status", "--short"],
                    text=True,
                    capture_output=True,
                    check=False,
                )
                manifest.verification.setdefault("git_status", []).append({
                    "path": str(Path(rel).parent).replace("\\", "/") or ".",
                    "dirty": bool(git.stdout.strip()),
                    "porcelain": [line for line in git.stdout.splitlines() if line.strip()],
                    "error": git.stderr.strip() if git.returncode else "",
                })
            continue
        if item.is_file():
            size = item.stat().st_size
            record = {"path": rel, "size": size, "sha256": sha256(item)}
            manifest.copy_plan["files"].append(record)
            counts["files"] += 1
            counts["bytes"] += size
            if is_text_candidate(item):
                try:
                    text = read_text(item)
                except UnicodeDecodeError:
                    continue
                hits = [{"variant": name, "count": text.count(old)} for name, old, _new in variants if old in text]
                hits = [hit for hit in hits if hit["count"]]
                if hits:
                    counts["rewrite_files"] += 1
                    counts["rewrite_hits"] += sum(int(hit["count"]) for hit in hits)
                    manifest.rewrites.append({"path": rel, "hits": hits, "destination": str(dest)})
    counts["skipped_directories"] = len(manifest.copy_plan["skipped"])
    counts["skipped_files"] = sum(int(item["files"]) for item in manifest.copy_plan["skipped"])
    counts["skipped_bytes"] = sum(int(item["bytes"]) for item in manifest.copy_plan["skipped"])
    manifest.summary = counts


def remove_migration_tree(path: Path) -> None:
    if not path.exists():
        return
    def make_writable_and_retry(function, target, _exc_info):
        os.chmod(target, stat.S_IWRITE)
        function(target)
    shutil.rmtree(path, onerror=make_writable_and_retry)


def execute_copy_and_rewrite(source: Path, destination: Path, final_destination: Path, manifest: Manifest) -> None:
    for directory in manifest.copy_plan["directories"]:
        (destination / str(directory["path"])).mkdir(parents=True, exist_ok=True)
    for file_record in manifest.copy_plan["files"]:
        rel = str(file_record["path"])
        src = source / rel
        dst = destination / rel
        if is_link_or_reparse(src) or has_reparse_parent(src, source):
            raise RuntimeError(f"source path became a link or reparse point before copy: {src}")
        if has_reparse_parent(dst, destination):
            raise RuntimeError(f"destination parent is a link or reparse point: {dst.parent}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst, follow_symlinks=False)
        if is_link_or_reparse(dst):
            raise RuntimeError(f"destination file became a link or reparse point after copy: {dst}")

    variants = path_variants(source, final_destination)
    rewritten: list[dict[str, object]] = []
    for rewrite in manifest.rewrites:
        dst = destination / str(rewrite["path"])
        text = read_text(dst)
        applied: list[dict[str, object]] = []
        for name, old, new in variants:
            count = text.count(old)
            if count:
                text = text.replace(old, new)
                applied.append({"variant": name, "count": count})
        if applied:
            write_text(dst, text)
            rewritten.append({"path": rewrite["path"], "applied": applied})
    manifest.rewrites = rewritten


def rebuild_links(destination: Path, manifest: Manifest) -> None:
    results = []
    for link in manifest.copy_plan["links"]:
        rel = str(link["path"])
        dst = destination / rel
        target = str(link.get("destination_target") or link.get("target"))
        result = {
            "path": rel,
            "target": target,
            "link_type": link.get("link_type"),
            "internal_to_source": bool(link.get("internal_to_source")),
            "status": "pending",
        }
        try:
            if has_reparse_parent(dst, destination):
                raise RuntimeError(f"destination link parent is a link or reparse point: {dst.parent}")
            dst.parent.mkdir(parents=True, exist_ok=True)
            if os.name == "nt" and link.get("link_type") == "reparse" and bool(link.get("is_dir")):
                command = ["cmd", "/c", "mklink", "/J", str(dst), target]
                completed = subprocess.run(command, text=True, capture_output=True, encoding="utf-8", errors="replace", check=False)
                if completed.returncode:
                    raise RuntimeError((completed.stderr or completed.stdout or "mklink failed").strip())
            else:
                os.symlink(target, dst, target_is_directory=bool(link.get("is_dir")))
            if not is_link_or_reparse(dst):
                raise RuntimeError("created link is not a symlink/reparse point")
            if link.get("link_type") == "reparse":
                actual_target = str(dst.resolve())
            else:
                actual_target = os.readlink(dst)
            result["actual_target"] = actual_target
            result["status"] = "rebuilt"
        except Exception as exc:
            result["status"] = "failed"
            result["error"] = str(exc)
            results.append(result)
            manifest.verification["link_rebuild_results"] = results
            raise
        results.append(result)
    manifest.verification["link_rebuild_results"] = results


def scan_old_root(destination: Path, old_root: Path) -> list[dict[str, object]]:
    variants = path_variants(old_root, old_root)
    old_forms = [old for _name, old, _new in variants]
    hits: list[dict[str, object]] = []
    for item in iter_tree(destination):
        if is_link_or_reparse(item) or not item.is_file() or not is_text_candidate(item):
            continue
        try:
            text = read_text(item)
        except UnicodeDecodeError:
            continue
        found = []
        for old in old_forms:
            count = text.count(old)
            if count:
                found.append({"value": old, "count": count})
        if found:
            hits.append({"path": relative(item, destination), "hits": found})
    return hits


def scan_binary_old_root(destination: Path, old_root: Path) -> list[dict[str, object]]:
    variants = path_variants(old_root, old_root)
    old_forms = []
    for _name, old, _new in variants:
        old_forms.append(("utf-8", old.encode("utf-8")))
        old_forms.append(("utf-16le", old.encode("utf-16le")))
    hits: list[dict[str, object]] = []
    for item in iter_tree(destination):
        if is_link_or_reparse(item) or not item.is_file() or is_text_candidate(item):
            continue
        try:
            if item.stat().st_size > MAX_BINARY_SCAN_BYTES:
                continue
            data = item.read_bytes()
        except OSError:
            continue
        found = []
        for encoding, needle in old_forms:
            count = data.count(needle)
            if count:
                found.append({"encoding": encoding, "count": count})
        if found:
            hits.append({"path": relative(item, destination), "hits": found})
    return hits


def scan_link_targets(root: Path, old_root: Path) -> list[dict[str, object]]:
    variants = path_variants(old_root, old_root)
    old_forms = [old for _name, old, _new in variants]
    hits: list[dict[str, object]] = []
    for item in iter_tree(root):
        if not is_link_or_reparse(item):
            continue
        target = os.readlink(item) if item.is_symlink() else str(item.resolve())
        matched = [{"value": old, "count": str(target).count(old)} for old in old_forms if old in str(target)]
        hits.append({
            "path": relative(item, root),
            "target": str(target),
            "link_type": link_type(item),
            "old_root_hits": matched,
        })
    return hits


def expected_destination_bytes(source_path: Path, source_root: Path, destination_root: Path) -> bytes | None:
    if not is_text_candidate(source_path):
        return source_path.read_bytes()
    try:
        text = read_text(source_path)
    except UnicodeDecodeError:
        return source_path.read_bytes()
    for _name, old, new in path_variants(source_root, destination_root):
        text = text.replace(old, new)
    return text.encode("utf-8")


def is_mutable_git_index(relative_path: str) -> bool:
    parts = Path(relative_path).parts
    return len(parts) >= 2 and parts[-2:] == (".git", "index")


def verify_tree(source: Path, destination: Path, manifest: Manifest, expected_destination: Path | None = None) -> None:
    expected_destination = expected_destination or destination
    old_hits = scan_old_root(destination, source)
    binary_old_hits = scan_binary_old_root(destination, source)
    link_results = scan_link_targets(destination, source)
    secret_hits = []
    encoding_or_lf_issues = []
    hash_mismatches = []
    git_metadata_hash_skips = []
    source_files = {relative(p, source): p for p in iter_tree(source) if p.is_file() and not is_link_or_reparse(p)}
    destination_files = {relative(p, destination): p for p in iter_tree(destination) if p.is_file() and not is_link_or_reparse(p)}
    missing = sorted(set(source_files) - set(destination_files))
    extra = sorted(set(destination_files) - set(source_files))
    for rel, src_path in source_files.items():
        dst_path = destination_files.get(rel)
        if not dst_path:
            continue
        if is_mutable_git_index(rel):
            git_metadata_hash_skips.append({"path": rel, "reason": "git status may refresh index cache metadata"})
            continue
        expected = expected_destination_bytes(src_path, source, expected_destination)
        actual = dst_path.read_bytes()
        if expected is not None and hashlib.sha256(expected).hexdigest() != hashlib.sha256(actual).hexdigest():
            hash_mismatches.append({
                "path": rel,
                "expected_sha256": hashlib.sha256(expected).hexdigest(),
                "actual_sha256": hashlib.sha256(actual).hexdigest(),
            })
    for rel, path in destination_files.items():
        if is_text_candidate(path):
            raw = path.read_bytes()
            if raw.startswith(b"\xef\xbb\xbf") or b"\r\n" in raw:
                encoding_or_lf_issues.append(rel)
            try:
                text = read_text(path)
            except UnicodeDecodeError:
                continue
            if SECRET_RE.search(text):
                secret_hits.append(rel)
    manifest.verification.update({
        "missing_files": missing,
        "extra_files": extra,
        "hash_mismatches": hash_mismatches,
        "git_metadata_hash_skips": git_metadata_hash_skips,
        "old_root_hits": old_hits,
        "binary_old_root_hits": binary_old_hits,
        "link_target_results": link_results,
        "encoding_or_lf_issues": encoding_or_lf_issues,
        "secret_like_hits": secret_hits,
    })
    link_old_hits = [link for link in link_results if link["old_root_hits"]]
    if missing or extra or hash_mismatches or old_hits or binary_old_hits or link_old_hits or secret_hits or encoding_or_lf_issues:
        manifest.errors.append("verification found missing/extra files, hash mismatches, old root hits, link target old root hits, encoding/LF issues, or secret-like text")


def consume_align_report(path: Path, manifest: Manifest, require_pass: bool) -> None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        manifest.verification["alignment_gate"] = {
            "report": str(path),
            "passed": False,
            "error": str(exc),
            "projects": [],
        }
        if require_pass:
            manifest.errors.append("alignment report could not be read or parsed")
        return
    projects = payload.get("projects", [])
    statuses = {project.get("status") for project in projects}
    failing = [project for project in projects if project.get("status") in ATTENTION_ALIGN_STATUSES]
    passed = bool(projects) and not failing and statuses.issubset(ALLOWED_ALIGN_STATUSES)
    manifest.verification["alignment_gate"] = {
        "report": str(path),
        "passed": passed,
        "projects": [{"name": project.get("name"), "status": project.get("status")} for project in projects],
    }
    if require_pass and not passed:
        manifest.errors.append("alignment gate failed; migration must not be announced complete")


def write_reports(report_dir: Path, manifest: Manifest) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "migration-manifest.json").write_text(
        json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    lines = [
        "# Agent 根目录迁移报告",
        "",
        f"- 模式：`{manifest.mode}`",
        f"- 状态：`{manifest.status}`",
        f"- 旧根：`{manifest.source}`",
        f"- 新根：`{manifest.destination}`",
        f"- dry-run：`{manifest.dry_run}`",
        f"- 文件：`{manifest.summary.get('files', 0)}`",
        f"- 链接：`{manifest.summary.get('links', 0)}`",
        f"- 待重写文件：`{manifest.summary.get('rewrite_files', 0)}`",
        f"- 错误：{'; '.join(manifest.errors) if manifest.errors else '无'}",
    ]
    (report_dir / "migration-report.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def command_plan(args: argparse.Namespace) -> int:
    source = lexical_abs(Path(args.source))
    destination = lexical_abs(Path(args.destination))
    manifest = Manifest(mode="plan", source=str(source), destination=str(destination), dry_run=True)
    manifest.same_drive = source.anchor.lower() == destination.anchor.lower()
    validate_boundaries(source, destination, manifest)
    if not manifest.errors:
        build_plan(source, destination, manifest)
        manifest.status = "planned"
    else:
        manifest.status = "blocked"
    write_reports(Path(args.report), manifest)
    print(f"status={manifest.status} report={Path(args.report) / 'migration-manifest.json'}")
    return 1 if manifest.errors else 0


def command_execute(args: argparse.Namespace) -> int:
    source = lexical_abs(Path(args.source))
    destination = lexical_abs(Path(args.destination))
    manifest = Manifest(mode="execute", source=str(source), destination=str(destination), dry_run=bool(args.dry_run))
    manifest.same_drive = source.anchor.lower() == destination.anchor.lower()
    validate_boundaries(source, destination, manifest)
    if not manifest.errors:
        build_plan(source, destination, manifest)
        if args.dry_run:
            manifest.status = "planned"
        else:
            staging = destination.parent / f".{destination.name}.staging-{os.getpid()}"
            if staging.exists():
                manifest.errors.append(f"staging directory already exists: {staging}")
                manifest.status = "blocked"
                write_reports(Path(args.report), manifest)
                print(f"status={manifest.status} report={Path(args.report) / 'migration-manifest.json'}")
                return 1
            try:
                execute_copy_and_rewrite(source, staging, destination, manifest)
                verify_tree(source, staging, manifest, expected_destination=destination)
                if manifest.errors:
                    raise RuntimeError("staging verification failed")
                staging.rename(destination)
                try:
                    rebuild_links(destination, manifest)
                    verify_tree(source, destination, manifest)
                    if manifest.errors:
                        raise RuntimeError("final verification failed")
                except Exception:
                    if destination.exists():
                        remove_migration_tree(destination)
                    raise
                manifest.status = "executed"
            except Exception as exc:
                manifest.status = "blocked"
                manifest.errors.append(str(exc))
                cleanup_errors = []
                for cleanup_path in (staging, destination):
                    if cleanup_path.exists():
                        try:
                            remove_migration_tree(cleanup_path)
                        except Exception as cleanup_exc:
                            cleanup_errors.append(f"failed to clean migration artifact {cleanup_path}: {cleanup_exc}")
                manifest.errors.extend(cleanup_errors)
    else:
        manifest.status = "blocked"
    write_reports(Path(args.report), manifest)
    print(f"status={manifest.status} report={Path(args.report) / 'migration-manifest.json'}")
    return 1 if manifest.errors else 0


def command_verify(args: argparse.Namespace) -> int:
    source = lexical_abs(Path(args.source))
    destination = lexical_abs(Path(args.destination))
    manifest = Manifest(mode="verify", source=str(source), destination=str(destination), dry_run=True)
    validate_boundaries(source, destination, manifest, allow_existing_destination=True)
    if not destination.exists():
        manifest.errors.append(f"destination does not exist: {destination}")
    if not manifest.errors:
        build_plan(source, destination, manifest)
        verify_tree(source, destination, manifest)
        if args.align_report:
            consume_align_report(Path(args.align_report), manifest, args.require_align_pass)
        manifest.status = "verified" if not manifest.errors else "blocked"
    else:
        manifest.status = "blocked"
    write_reports(Path(args.report), manifest)
    print(f"status={manifest.status} report={Path(args.report) / 'migration-manifest.json'}")
    return 1 if manifest.errors else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Plan, execute, and verify an Agent root migration.")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("plan", "execute", "verify"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--source", required=True)
        cmd.add_argument("--destination", required=True)
        cmd.add_argument("--report", required=True)
        if name == "execute":
            cmd.add_argument("--dry-run", action="store_true")
        if name == "verify":
            cmd.add_argument("--align-report")
            cmd.add_argument("--require-align-pass", action="store_true")
        cmd.set_defaults(func={"plan": command_plan, "execute": command_execute, "verify": command_verify}[name])
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
