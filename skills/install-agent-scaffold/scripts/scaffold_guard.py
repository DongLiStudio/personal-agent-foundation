#!/usr/bin/env python3
"""Deterministic safety guard for Personal Agent Foundation templates."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import shutil
import stat
import sys
import tempfile
from typing import Any, Iterable


PLACEHOLDER_RE = re.compile(r"\{\{([A-Z][A-Z0-9_]*)\}\}")
ANY_TEMPLATE_TOKEN_RE = re.compile(r"\{\{[^{}\r\n]+\}\}")

for stream in (sys.stdout, sys.stderr):
    reconfigure = getattr(stream, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8")


class GuardError(RuntimeError):
    """Raised when a template or installation violates the contract."""


@dataclass(frozen=True)
class TemplateFile:
    source: Path
    relative: Path
    raw: bytes
    text: str


def digest(data: bytes) -> str:
    return sha256(data).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GuardError(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise GuardError(f"JSON root must be an object: {path}")
    return value


def is_link(path: Path) -> bool:
    is_junction = getattr(os.path, "isjunction", lambda _: False)
    return path.is_symlink() or bool(is_junction(path))


def walk_files(root: Path) -> list[Path]:
    if not root.is_dir():
        raise GuardError(f"template root does not exist: {root}")
    result: list[Path] = []
    for current, dirs, files in os.walk(root, followlinks=False):
        current_path = Path(current)
        for name in list(dirs):
            child = current_path / name
            if is_link(child):
                raise GuardError(f"template link/reparse point is not allowed: {child}")
        for name in files:
            child = current_path / name
            if is_link(child):
                raise GuardError(f"template link/reparse point is not allowed: {child}")
            result.append(child)
    return sorted(result, key=lambda item: item.relative_to(root).as_posix())


def read_template_file(root: Path, path: Path) -> TemplateFile:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise GuardError(f"UTF-8 BOM is not allowed: {path}")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise GuardError(f"template file is not UTF-8: {path}") from exc
    if "\r" in text:
        raise GuardError(f"template file must use LF line endings: {path}")
    return TemplateFile(path, path.relative_to(root), raw, text)


def manifest_placeholders(manifest: dict[str, Any]) -> set[str]:
    placeholders = manifest.get("placeholders")
    if not isinstance(placeholders, dict) or not placeholders:
        raise GuardError("manifest.placeholders must be a non-empty object")
    invalid = [key for key in placeholders if not re.fullmatch(r"[A-Z][A-Z0-9_]*", key)]
    if invalid:
        raise GuardError(f"invalid manifest placeholder names: {', '.join(invalid)}")
    return set(placeholders)


def audit_template(template: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    template = template.resolve()
    allowed = manifest_placeholders(manifest)
    files = [read_template_file(template, path) for path in walk_files(template)]
    expected_count = manifest.get("source", {}).get("tracked_file_count")
    if expected_count is not None and len(files) != expected_count:
        raise GuardError(
            f"template inventory mismatch: expected {expected_count}, found {len(files)}"
        )

    relative_names = {item.relative.as_posix() for item in files}
    required_paths = manifest.get("required_paths", [])
    if not isinstance(required_paths, list):
        raise GuardError("manifest.required_paths must be an array")
    missing = sorted(str(path) for path in required_paths if path not in relative_names)
    if missing:
        raise GuardError(f"required template paths missing: {', '.join(missing)}")

    used: set[str] = set()
    for item in files:
        raw_tokens = set(ANY_TEMPLATE_TOKEN_RE.findall(item.text))
        malformed = sorted(token for token in raw_tokens if not PLACEHOLDER_RE.fullmatch(token))
        if malformed:
            raise GuardError(
                f"malformed placeholder(s) in {item.relative.as_posix()}: "
                + ", ".join(malformed)
            )
        names = set(PLACEHOLDER_RE.findall(item.text))
        unknown = sorted(names - allowed)
        if unknown:
            raise GuardError(
                f"unknown placeholder(s) in {item.relative.as_posix()}: "
                + ", ".join(unknown)
            )
        used.update(names)

    unused = sorted(allowed - used)
    if unused:
        raise GuardError(f"manifest placeholders not used by template: {', '.join(unused)}")

    return {
        "ok": True,
        "template": str(template),
        "file_count": len(files),
        "placeholders": sorted(used),
        "inventory_sha256": digest(
            "\n".join(
                f"{item.relative.as_posix()} {digest(item.raw)}" for item in files
            ).encode("utf-8")
        ),
    }


def load_values(path: Path, manifest: dict[str, Any], target: Path) -> dict[str, str]:
    raw = load_json(path)
    allowed = manifest_placeholders(manifest)
    unknown = sorted(set(raw) - allowed)
    if unknown:
        raise GuardError(f"unknown configuration keys: {', '.join(unknown)}")

    values: dict[str, str] = {}
    placeholder_spec = manifest["placeholders"]
    for key in sorted(allowed):
        value = raw.get(key)
        required = bool(placeholder_spec.get(key, {}).get("required", False))
        if required and (not isinstance(value, str) or not value.strip()):
            raise GuardError(f"configuration requires non-empty string: {key}")
        if value is not None:
            if not isinstance(value, str):
                raise GuardError(f"configuration value must be a string: {key}")
            if "\x00" in value or "\r" in value or "\n" in value:
                raise GuardError(f"configuration value contains control characters: {key}")
            values[key] = value.strip()

    configured_root = Path(values["AGENT_ROOT"]).expanduser().resolve()
    if configured_root != target:
        raise GuardError(
            f"AGENT_ROOT does not match --target: {configured_root} != {target}"
        )
    values["AGENT_ROOT"] = str(target)
    return values


def render(text: str, values: dict[str, str], relative: Path) -> str:
    result = text
    for key, value in values.items():
        result = result.replace("{{" + key + "}}", value)
    residual = sorted(set(ANY_TEMPLATE_TOKEN_RE.findall(result)))
    if residual:
        raise GuardError(
            f"placeholder residue in {relative.as_posix()}: {', '.join(residual)}"
        )
    return result


def plan_install(
    template: Path, manifest: dict[str, Any], values_path: Path, target: Path
) -> tuple[dict[str, Any], list[tuple[TemplateFile, bytes]]]:
    template = template.resolve()
    target = target.expanduser().resolve()
    if target.exists():
        raise GuardError(f"target already exists; refusing overwrite: {target}")
    audit = audit_template(template, manifest)
    values = load_values(values_path, manifest, target)
    rendered: list[tuple[TemplateFile, bytes]] = []
    plan_files: list[dict[str, Any]] = []
    for path in walk_files(template):
        item = read_template_file(template, path)
        rendered_bytes = render(item.text, values, item.relative).encode("utf-8")
        rendered.append((item, rendered_bytes))
        plan_files.append(
            {
                "path": item.relative.as_posix(),
                "destination": str(target / item.relative),
                "source_sha256": digest(item.raw),
                "rendered_sha256": digest(rendered_bytes),
                "bytes": len(rendered_bytes),
            }
        )
    return (
        {
            "ok": True,
            "mode": "dry-run",
            "target": str(target),
            "template_audit": audit,
            "file_count": len(plan_files),
            "files": plan_files,
        },
        rendered,
    )


def verify_target(target: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    target = target.expanduser().resolve()
    if not target.is_dir():
        raise GuardError(f"installed target does not exist: {target}")
    files = [read_template_file(target, path) for path in walk_files(target)]
    names = {item.relative.as_posix() for item in files}
    missing = sorted(path for path in manifest.get("required_paths", []) if path not in names)
    if missing:
        raise GuardError(f"installed target misses required paths: {', '.join(missing)}")
    residue: list[str] = []
    for item in files:
        if ANY_TEMPLATE_TOKEN_RE.search(item.text):
            residue.append(item.relative.as_posix())
    if residue:
        raise GuardError(f"installed target contains placeholder residue: {', '.join(residue)}")
    return {
        "ok": True,
        "target": str(target),
        "file_count": len(files),
        "inventory_sha256": digest(
            "\n".join(
                f"{item.relative.as_posix()} {digest(item.raw)}" for item in files
            ).encode("utf-8")
        ),
    }


def install(
    template: Path, manifest: dict[str, Any], values_path: Path, target: Path
) -> dict[str, Any]:
    target = target.expanduser().resolve()
    plan, rendered = plan_install(template, manifest, values_path, target)
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".paf-staging-", dir=target.parent))
    try:
        for item, content in rendered:
            destination = staging / item.relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)
            os.chmod(destination, stat.S_IMODE(item.source.stat().st_mode))
        verify_target(staging, manifest)
        if target.exists():
            raise GuardError(f"target appeared during install; refusing overwrite: {target}")
        os.replace(staging, target)
        verification = verify_target(target, manifest)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise
    return {
        "ok": True,
        "mode": "install",
        "target": str(target),
        "planned_file_count": plan["file_count"],
        "verification": verification,
    }


def print_json(value: dict[str, Any], stream: Any = sys.stdout) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2), file=stream)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="scaffold_guard.py")
    sub = result.add_subparsers(dest="command", required=True)
    for name in ("audit-template", "plan", "install", "verify"):
        command = sub.add_parser(name)
        command.add_argument("--manifest", required=True, type=Path)
        if name in ("audit-template", "plan", "install"):
            command.add_argument("--template", required=True, type=Path)
        if name in ("plan", "install"):
            command.add_argument("--values", required=True, type=Path)
            command.add_argument("--target", required=True, type=Path)
        if name == "verify":
            command.add_argument("--target", required=True, type=Path)
    return result


def main(argv: Iterable[str] | None = None) -> int:
    args = parser().parse_args(list(argv) if argv is not None else None)
    try:
        manifest = load_json(args.manifest)
        if args.command == "audit-template":
            output = audit_template(args.template, manifest)
        elif args.command == "plan":
            output, _ = plan_install(args.template, manifest, args.values, args.target)
        elif args.command == "install":
            output = install(args.template, manifest, args.values, args.target)
        else:
            output = verify_target(args.target, manifest)
    except GuardError as exc:
        print_json({"ok": False, "error": str(exc)}, sys.stderr)
        return 2
    print_json(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
