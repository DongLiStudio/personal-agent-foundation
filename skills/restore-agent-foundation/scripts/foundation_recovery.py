#!/usr/bin/env python3
"""Self-contained recovery guard for an existing Personal Agent Foundation."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from typing import Any, Iterable
import uuid


for stream in (sys.stdout, sys.stderr):
    reconfigure = getattr(stream, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8")


STATE_RELATIVE = Path("GLOBAL") / "FOUNDATION_STATE.json"
SKILL_SOURCE_RELATIVE = Path("GLOBAL") / ".agents" / "skills"
CORE_GLOBAL_FILES = (
    "README.md",
    "GLOBAL_CONTEXT.md",
    "PROJECTS.md",
    "OBSIDIAN_LINK.md",
    "SKILL_DEPENDENCIES.md",
    "LARK_PROFILES.md",
    "SERVER_PROFILES.md",
    "GITHUB_ACCOUNTS.md",
    "SCHEDULE_PREFERENCES.md",
    "FOUNDATION_STATE.json",
)
PROJECT_ENTRY_FILES = ("AGENTS.md", "README.md", "STATUS.md")
TEXT_SUFFIXES = {
    "",
    ".css",
    ".csv",
    ".env.example",
    ".gitignore",
    ".gitattributes",
    ".html",
    ".ini",
    ".java",
    ".js",
    ".json",
    ".md",
    ".properties",
    ".ps1",
    ".py",
    ".sh",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}
SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".idea",
    "__pycache__",
    "node_modules",
    "target",
    "build",
    "dist",
    ".foundation-recovery",
}
SECRET_NAMES = {
    ".env",
    "credentials.json",
    "secrets.json",
    "id_rsa",
    "id_ed25519",
}
SECRET_SUFFIXES = {".key", ".pem", ".p12", ".pfx", ".ppk"}
PROJECT_LINE_RE = re.compile(r"^-\s*[^：:]+[：:]\s*`([^`]+)`", re.MULTILINE)
ACTIVE_PROJECTS_RE = re.compile(
    r"^##\s+活跃项目\s*$([\s\S]*?)(?=^##\s+|\Z)", re.MULTILINE
)
FOUNDATION_PLACEHOLDER_RE = re.compile(
    r"\{\{(?:AGENT_ROOT|DEFAULT_GITHUB_ACCOUNT|DEFAULT_LARK_PROFILE|"
    r"DEFAULT_TIMEZONE|GENERAL_ASSISTANT_PROJECT|OBSIDIAN_VAULT_PATH)\}\}"
)


class RecoveryError(RuntimeError):
    """Raised when a recovery operation violates a safety contract."""


@dataclass(frozen=True)
class TextFile:
    path: Path
    relative: Path
    raw: bytes
    text: str


def digest(data: bytes) -> str:
    return sha256(data).hexdigest()


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def plan_digest(plan: dict[str, Any]) -> str:
    unsigned = {key: value for key, value in plan.items() if key != "plan_sha256"}
    return digest(canonical_json(unsigned))


def lexical_abs(path: Path) -> Path:
    return Path(os.path.abspath(os.path.expanduser(str(path))))


def file_attributes(path: Path) -> int:
    try:
        return int(getattr(path.lstat(), "st_file_attributes", 0))
    except OSError:
        return 0


def is_link_or_reparse(path: Path) -> bool:
    is_junction = getattr(os.path, "isjunction", lambda _: False)
    reparse_flag = int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
    return path.is_symlink() or bool(is_junction(path)) or bool(
        file_attributes(path) & reparse_flag
    )


def existing_chain_has_link(path: Path) -> Path | None:
    current = lexical_abs(path)
    parts = current.parts
    if not parts:
        return None
    probe = Path(parts[0])
    for part in parts[1:]:
        probe = probe / part
        if not probe.exists() and not os.path.lexists(probe):
            break
        if is_link_or_reparse(probe):
            return probe
    return None


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RecoveryError(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise RecoveryError(f"JSON root must be an object: {path}")
    return value


def write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    temporary = path.with_name(path.name + f".tmp-{uuid.uuid4().hex}")
    temporary.write_text(payload, encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def discover_agent_root(start: Path | None = None) -> Path:
    origin = lexical_abs(start or Path(__file__))
    candidates = [origin] if origin.is_dir() else [origin.parent]
    candidates.extend(candidates[0].parents)
    for candidate in candidates:
        if candidate.name == "GLOBAL" and (candidate / "GLOBAL_CONTEXT.md").is_file():
            return candidate.parent
        if (candidate / "GLOBAL" / "GLOBAL_CONTEXT.md").is_file():
            return candidate
    raise RecoveryError(
        "cannot discover Agent root; pass --root pointing to the copied foundation"
    )


def validate_root(root: Path) -> Path:
    root = lexical_abs(root)
    linked = existing_chain_has_link(root)
    if linked is not None:
        raise RecoveryError(f"Agent root or parent is a link/reparse point: {linked}")
    if not root.is_dir():
        raise RecoveryError(f"Agent root does not exist: {root}")
    if not (root / "GLOBAL").is_dir():
        raise RecoveryError(f"GLOBAL directory is missing under Agent root: {root}")
    return root


def is_sensitive_path(path: Path) -> bool:
    lower_name = path.name.lower()
    return (
        lower_name in SECRET_NAMES
        or path.suffix.lower() in SECRET_SUFFIXES
        or (lower_name.startswith(".env.") and lower_name != ".env.example")
    )


def iter_tree(root: Path) -> tuple[list[Path], list[dict[str, Any]]]:
    files: list[Path] = []
    links: list[dict[str, Any]] = []
    for current, dirs, names in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current)
        kept_dirs: list[str] = []
        for name in sorted(dirs):
            child = current_path / name
            relative = child.relative_to(root)
            if name in SKIP_DIRS:
                continue
            if is_link_or_reparse(child):
                links.append(link_metadata(root, child))
                continue
            kept_dirs.append(name)
        dirs[:] = kept_dirs
        for name in sorted(names):
            child = current_path / name
            if is_link_or_reparse(child):
                links.append(link_metadata(root, child))
                continue
            files.append(child)
    return files, links


def link_metadata(root: Path, path: Path) -> dict[str, Any]:
    link_type = "symlink"
    if bool(getattr(os.path, "isjunction", lambda _: False)(path)):
        link_type = "junction"
    try:
        raw_target = os.readlink(path)
    except OSError:
        raw_target = os.path.realpath(path)
    return {
        "path": path.relative_to(root).as_posix(),
        "type": link_type,
        "target": str(raw_target),
    }


def read_text_candidate(root: Path, path: Path) -> TextFile | None:
    if is_sensitive_path(path):
        return None
    suffix = path.suffix.lower()
    if path.name.lower() == ".env.example":
        suffix = ".env.example"
    if suffix not in TEXT_SUFFIXES:
        return None
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise RecoveryError(f"cannot read {path}: {exc}") from exc
    if raw.startswith(b"\xef\xbb\xbf"):
        encoding = "utf-8-sig"
    else:
        encoding = "utf-8"
    try:
        text = raw.decode(encoding)
    except UnicodeDecodeError:
        return None
    return TextFile(path, path.relative_to(root), raw, text)


def is_governance_text(relative: Path) -> bool:
    return bool(relative.parts) and relative.parts[0] == "GLOBAL"


def tree_inventory(root: Path) -> dict[str, str]:
    files, _ = iter_tree(root)
    return {
        path.relative_to(root).as_posix(): digest(path.read_bytes())
        for path in files
        if not is_sensitive_path(path)
    }


def inventory_digest(root: Path) -> str:
    return digest(canonical_json(tree_inventory(root)))


def path_replacements(old_root: str, new_root: str) -> list[tuple[str, str]]:
    old_native = old_root.rstrip("\\/")
    new_native = new_root.rstrip("\\/")
    variants = [
        (old_native, new_native),
        (old_native.replace("\\", "/"), new_native.replace("\\", "/")),
        (old_native.replace("/", "\\"), new_native.replace("/", "\\")),
        (
            old_native.replace("\\", "\\\\"),
            new_native.replace("\\", "\\\\"),
        ),
    ]
    unique: list[tuple[str, str]] = []
    for pair in sorted(variants, key=lambda item: len(item[0]), reverse=True):
        if pair[0] and pair[0] != pair[1] and pair not in unique:
            unique.append(pair)
    return unique


def rewrite_text(text: str, replacements: list[tuple[str, str]]) -> tuple[str, int]:
    result = text
    count = 0
    for old, new in replacements:
        occurrences = result.count(old)
        if occurrences:
            result = result.replace(old, new)
            count += occurrences
    return result, count


def parse_projects(root: Path) -> list[dict[str, Any]]:
    projects_file = root / "GLOBAL" / "PROJECTS.md"
    if not projects_file.is_file():
        return []
    text = projects_file.read_text(encoding="utf-8-sig")
    active_section = ACTIVE_PROJECTS_RE.search(text)
    if active_section is None:
        return []
    projects: list[dict[str, Any]] = []
    for value in PROJECT_LINE_RE.findall(active_section.group(1)):
        path = lexical_abs(Path(value))
        missing_entries = [name for name in PROJECT_ENTRY_FILES if not (path / name).is_file()]
        projects.append(
            {
                "path": str(path),
                "exists": path.is_dir(),
                "missing_entry_files": missing_entries,
                "git_repository": (path / ".git").exists(),
            }
        )
    return projects


def command_path(name: str) -> str | None:
    discovered = shutil.which(name)
    if discovered:
        return str(lexical_abs(Path(discovered)))

    candidates: list[Path] = []
    home = Path.home()
    if os.name == "nt":
        appdata = os.environ.get("APPDATA")
        if appdata:
            npm_bin = Path(appdata) / "npm"
            candidates.extend(
                npm_bin / suffix
                for suffix in (name, f"{name}.cmd", f"{name}.ps1", f"{name}.exe")
            )
        localappdata = os.environ.get("LOCALAPPDATA")
        if localappdata:
            candidates.extend(
                (
                    Path(localappdata) / "Microsoft" / "WindowsApps" / f"{name}.exe",
                    Path(localappdata) / "Programs" / name / f"{name}.com",
                )
            )
    else:
        candidates.extend(
            (
                home / ".local" / "bin" / name,
                home / ".npm-global" / "bin" / name,
            )
        )
    for candidate in candidates:
        try:
            if candidate.is_file():
                return str(lexical_abs(candidate))
        except OSError:
            continue
    return None


def obsidian_cli_path() -> str | None:
    """Discover only the registered CLI, never the GUI executable."""
    if os.name == "nt":
        discovered = command_path("Obsidian.com")
        if discovered:
            return discovered
        localappdata = os.environ.get("LOCALAPPDATA")
        if localappdata:
            redirector = Path(localappdata) / "Programs" / "Obsidian" / "Obsidian.com"
            try:
                if redirector.is_file():
                    return str(lexical_abs(redirector))
            except OSError:
                pass
        return None
    return command_path("obsidian")


def runtime_checks() -> dict[str, Any]:
    return {
        "python": {
            "path": sys.executable,
            "version": ".".join(str(item) for item in sys.version_info[:3]),
            "supported": sys.version_info >= (3, 11),
        },
        "git": {"path": command_path("git")},
        "github_cli": {"path": command_path("gh"), "authorization": "not_checked"},
        "lark_cli": {
            "path": command_path("lark-cli"),
            "authorization": "not_checked",
        },
        "obsidian_cli": {
            "path": obsidian_cli_path(),
            "authorization": "not_checked",
        },
        "ssh": {
            "path": command_path("ssh") or command_path("ssh.exe"),
            "authorization": "not_checked",
        },
    }


def inspect_skill_targets(root: Path, targets: list[Path]) -> list[dict[str, Any]]:
    source = root / SKILL_SOURCE_RELATIVE
    if not source.is_dir():
        return []
    source_skills = sorted(path for path in source.iterdir() if path.is_dir())
    findings: list[dict[str, Any]] = []
    for target in targets:
        target = lexical_abs(target)
        linked = existing_chain_has_link(target)
        if linked is not None:
            findings.append(
                {"target": str(target), "status": "blocked", "reason": f"link in parent chain: {linked}"}
            )
            continue
        for skill in source_skills:
            installed = target / skill.name
            if not installed.exists():
                status = "missing"
            elif is_link_or_reparse(installed):
                status = "blocked_link"
            elif not installed.is_dir():
                status = "blocked_not_directory"
            elif tree_inventory(skill) == tree_inventory(installed):
                status = "aligned"
            else:
                status = "different"
            findings.append(
                {
                    "target": str(target),
                    "skill": skill.name,
                    "source": str(skill),
                    "status": status,
                }
            )
    return findings


def read_state(root: Path) -> dict[str, Any]:
    path = root / STATE_RELATIVE
    if not path.is_file():
        return {
            "schema_version": 0,
            "product": "Personal Agent Foundation",
            "installed_agent_root": None,
            "state_file_missing": True,
        }
    state = load_json(path)
    state["state_file_missing"] = False
    return state


def make_plan(
    root: Path,
    old_root: str | None,
    skill_targets: list[Path],
    obsidian_target: Path | None,
) -> dict[str, Any]:
    root = validate_root(root)
    state = read_state(root)
    recorded_root = state.get("installed_agent_root")
    source_root = old_root or (recorded_root if isinstance(recorded_root, str) else None)
    replacements: list[tuple[str, str]] = []
    if source_root:
        replacements = path_replacements(source_root, str(root))

    files, links = iter_tree(root)
    text_issues: list[dict[str, Any]] = []
    rewrites: list[dict[str, Any]] = []
    placeholder_residue: list[str] = []
    for path in files:
        item = read_text_candidate(root, path)
        if item is None:
            continue
        if is_governance_text(item.relative):
            issues: list[str] = []
            if item.raw.startswith(b"\xef\xbb\xbf"):
                issues.append("utf8_bom")
            if "\r" in item.text:
                issues.append("crlf_or_cr")
            if issues:
                text_issues.append({"path": item.relative.as_posix(), "issues": issues})
            if FOUNDATION_PLACEHOLDER_RE.search(item.text):
                placeholder_residue.append(item.relative.as_posix())
        if replacements:
            rewritten, count = rewrite_text(item.text, replacements)
            if count:
                rewrites.append(
                    {
                        "path": item.relative.as_posix(),
                        "before_sha256": digest(item.raw),
                        "after_sha256": digest(rewritten.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")),
                        "replacement_count": count,
                    }
                )

    missing_core = [
        name
        for name in CORE_GLOBAL_FILES
        if name != "FOUNDATION_STATE.json" and not (root / "GLOBAL" / name).is_file()
    ]
    link_actions: list[dict[str, Any]] = []
    for metadata in links:
        action = {**metadata, "action": "inspect_only"}
        target = metadata["target"]
        if source_root and source_root in target:
            action["action"] = "rewrite_internal_target"
            action["new_target"] = target.replace(source_root, str(root))
        if metadata["path"] == "GLOBAL/obsidian-resource" and obsidian_target:
            action["action"] = "rebuild_obsidian_link"
            action["new_target"] = str(lexical_abs(obsidian_target))
        link_actions.append(action)
    if obsidian_target and not any(
        item["path"] == "GLOBAL/obsidian-resource" for item in link_actions
    ):
        link_actions.append(
            {
                "path": "GLOBAL/obsidian-resource",
                "type": "junction" if os.name == "nt" else "symlink",
                "target": None,
                "new_target": str(lexical_abs(obsidian_target)),
                "action": "rebuild_obsidian_link",
            }
        )

    projects = parse_projects(root)
    skill_findings = inspect_skill_targets(root, skill_targets)
    actions: list[dict[str, Any]] = []
    if source_root and lexical_abs(Path(source_root)) != root:
        actions.append({"kind": "rewrite_paths", "file_count": len(rewrites)})
    if state.get("state_file_missing") or recorded_root != str(root):
        actions.append({"kind": "update_foundation_state", "path": STATE_RELATIVE.as_posix()})
    if text_issues:
        actions.append({"kind": "normalize_text", "file_count": len(text_issues)})
    if any(item["action"] != "inspect_only" for item in link_actions):
        actions.append({"kind": "rebuild_links"})
    if any(item.get("status") in {"missing", "different"} for item in skill_findings):
        actions.append({"kind": "sync_skill_installations"})
    if not (root / "GLOBAL" / ".git").exists():
        actions.append({"kind": "initialize_global_git"})

    interactive_gates: list[dict[str, str]] = []
    if state.get("state_file_missing") and not old_root:
        interactive_gates.append(
            {
                "kind": "old_root_confirmation",
                "reason": "FOUNDATION_STATE.json is missing; provide the previous Agent root when path rewriting is required",
            }
        )
    checks = runtime_checks()
    if not checks["python"]["supported"]:
        interactive_gates.append({"kind": "python", "reason": "Python 3.11+ is required"})
    if checks["git"]["path"] is None:
        interactive_gates.append({"kind": "git", "reason": "Git is not available"})
    for kind, key in (
        ("github_authorization", "github_cli"),
        ("feishu_authorization", "lark_cli"),
        ("obsidian_connection", "obsidian_cli"),
        ("server_connection", "ssh"),
    ):
        if checks[key]["path"] is None:
            interactive_gates.append({"kind": kind, "reason": f"{key} is not available"})
        else:
            reason = "requires live identity/readback check"
            if kind == "server_connection":
                reason = (
                    "requires explicit target selection, host fingerprint verification, "
                    "SSH identity check and bounded read-only service readback"
                )
            interactive_gates.append({"kind": kind, "reason": reason})

    plan: dict[str, Any] = {
        "schema_version": 1,
        "product": "Personal Agent Foundation",
        "mode": "recovery_plan",
        "agent_root": str(root),
        "recorded_root": recorded_root,
        "old_root": source_root,
        "runtime": checks,
        "missing_core_files": missing_core,
        "placeholder_residue": sorted(placeholder_residue),
        "text_issues": text_issues,
        "path_rewrites": rewrites,
        "links": link_actions,
        "projects": projects,
        "skill_installations": skill_findings,
        "actions": actions,
        "interactive_gates": interactive_gates,
        "blocking_issues": [],
    }
    if missing_core:
        plan["blocking_issues"].append(
            "core GLOBAL files are missing; provide a trusted product/template source before repair"
        )
    if placeholder_residue:
        plan["blocking_issues"].append(
            "template placeholders remain; repair must not guess missing values"
        )
    if any(item.get("status", "").startswith("blocked") for item in skill_findings):
        plan["blocking_issues"].append("one or more skill targets are unsafe")
    plan["plan_sha256"] = plan_digest(plan)
    return plan


def create_run_directory(root: Path) -> Path:
    recovery_root = root / "GLOBAL" / ".foundation-recovery"
    recovery_root.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:8]
    run = recovery_root / run_id
    run.mkdir()
    return run


def backup_file(root: Path, run: Path, relative: Path) -> dict[str, Any]:
    source = root / relative
    destination = run / "files" / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    existed = source.is_file()
    before_hash = None
    if existed:
        raw = source.read_bytes()
        before_hash = digest(raw)
        destination.write_bytes(raw)
    return {
        "path": relative.as_posix(),
        "existed": existed,
        "before_sha256": before_hash,
    }


def write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".tmp-{uuid.uuid4().hex}")
    temporary.write_text(text, encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def remove_link_only(path: Path) -> None:
    if not (path.exists() or os.path.lexists(path)):
        return
    if not is_link_or_reparse(path):
        raise RecoveryError(f"refusing to remove non-link path: {path}")
    if bool(getattr(os.path, "isjunction", lambda _: False)(path)):
        os.rmdir(path)
    else:
        path.unlink()


def create_link(path: Path, target: Path, link_type: str) -> None:
    if not target.exists() or not target.is_dir():
        raise RecoveryError(f"link target is not an existing directory: {target}")
    path.parent.mkdir(parents=True, exist_ok=True)
    if os.name == "nt" and link_type == "junction":
        completed = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(path), str(target)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if completed.returncode != 0:
            raise RecoveryError(f"cannot create Junction {path}: {completed.stderr.strip()}")
    else:
        os.symlink(str(target), str(path), target_is_directory=True)
    if not is_link_or_reparse(path):
        raise RecoveryError(f"link verification failed: {path}")


def sync_skill_tree(
    source: Path, destination: Path, replace: bool, backup_root: Path
) -> dict[str, Any]:
    if destination.exists():
        if is_link_or_reparse(destination) or not destination.is_dir():
            raise RecoveryError(f"unsafe installed Skill path: {destination}")
        if tree_inventory(source) == tree_inventory(destination):
            return {"status": "aligned", "destination": str(destination)}
        if not replace:
            raise RecoveryError(
                f"installed Skill differs; rerun with --replace-skill-installations after confirmation: {destination}"
            )
        target_key = digest(str(destination.parent).encode("utf-8"))[:16]
        backup = backup_root / "skills" / target_key / destination.name
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(destination, backup)
        staging = Path(tempfile.mkdtemp(prefix=f".{destination.name}-", dir=destination.parent))
        shutil.rmtree(staging)
        shutil.copytree(source, staging)
        old = destination.with_name(destination.name + f".old-{uuid.uuid4().hex[:8]}")
        os.replace(destination, old)
        try:
            os.replace(staging, destination)
            shutil.rmtree(old)
        except Exception:
            if destination.exists():
                shutil.rmtree(destination)
            os.replace(old, destination)
            if staging.exists():
                shutil.rmtree(staging)
            raise
        return {
            "status": "replaced",
            "destination": str(destination),
            "backup": str(backup.relative_to(backup_root)),
            "after_inventory_sha256": inventory_digest(destination),
        }
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{destination.name}-", dir=destination.parent))
    shutil.rmtree(staging)
    shutil.copytree(source, staging)
    os.replace(staging, destination)
    return {
        "status": "installed",
        "destination": str(destination),
        "after_inventory_sha256": inventory_digest(destination),
    }


def execute_repair(
    plan_path: Path,
    confirm_sha256: str,
    replace_skills: bool,
) -> dict[str, Any]:
    plan = load_json(plan_path)
    expected = plan_digest(plan)
    if plan.get("plan_sha256") != expected or confirm_sha256 != expected:
        raise RecoveryError("plan hash mismatch; regenerate and reconfirm the recovery plan")
    if plan.get("blocking_issues"):
        raise RecoveryError("recovery plan has blocking issues")
    root = validate_root(Path(plan["agent_root"]))
    differing_skills = [
        entry
        for entry in plan.get("skill_installations", [])
        if entry.get("status") == "different"
    ]
    if differing_skills and not replace_skills:
        raise RecoveryError(
            "installed Skill differs; rerun with --replace-skill-installations after confirmation"
        )
    for entry in plan.get("path_rewrites", []):
        source = root / Path(entry["path"])
        if is_link_or_reparse(source) or not source.is_file():
            raise RecoveryError(f"planned text file changed type or disappeared: {entry['path']}")
        if digest(source.read_bytes()) != entry["before_sha256"]:
            raise RecoveryError(f"planned text file changed after plan: {entry['path']}")
    for entry in plan.get("links", []):
        if entry.get("action") != "inspect_only":
            target = Path(entry["new_target"])
            if not target.is_dir():
                raise RecoveryError(f"planned link target is unavailable: {target}")
    run = create_run_directory(root)
    backups: list[dict[str, Any]] = []
    changed_files: list[dict[str, Any]] = []
    link_results: list[dict[str, Any]] = []
    skill_results: list[dict[str, Any]] = []
    git_initialized = False
    try:
        replacements = path_replacements(plan.get("old_root") or "", str(root))
        rewrite_paths = {item["path"] for item in plan.get("path_rewrites", [])}
        normalize_paths = {item["path"] for item in plan.get("text_issues", [])}
        rewrite_paths.discard(STATE_RELATIVE.as_posix())
        normalize_paths.discard(STATE_RELATIVE.as_posix())
        for relative_text in sorted(rewrite_paths | normalize_paths):
            relative = Path(relative_text)
            source = root / relative
            if is_link_or_reparse(source) or not source.is_file():
                raise RecoveryError(f"planned text file changed type or disappeared: {relative_text}")
            item = read_text_candidate(root, source)
            if item is None:
                raise RecoveryError(f"planned text file is no longer safe text: {relative_text}")
            planned = next(
                (entry for entry in plan.get("path_rewrites", []) if entry["path"] == relative_text),
                None,
            )
            if planned and digest(item.raw) != planned["before_sha256"]:
                raise RecoveryError(f"planned text file changed after plan: {relative_text}")
            backups.append(backup_file(root, run, relative))
            rewritten, _ = rewrite_text(item.text, replacements)
            rewritten = rewritten.replace("\r\n", "\n").replace("\r", "\n")
            write_text_atomic(source, rewritten)
            changed_files.append(
                {"path": relative_text, "after_sha256": digest(source.read_bytes())}
            )

        state_relative = STATE_RELATIVE
        state_path = root / state_relative
        backups.append(backup_file(root, run, state_relative))
        state = read_state(root)
        state.update(
            {
                "schema_version": 1,
                "product": "Personal Agent Foundation",
                "installed_agent_root": str(root),
                "global_root": str(root / "GLOBAL"),
                "recovery_skill": str(root / SKILL_SOURCE_RELATIVE / "restore-agent-foundation"),
            }
        )
        state.pop("state_file_missing", None)
        write_json_atomic(state_path, state)
        changed_files.append(
            {"path": state_relative.as_posix(), "after_sha256": digest(state_path.read_bytes())}
        )

        for entry in plan.get("links", []):
            if entry.get("action") == "inspect_only":
                continue
            path = root / Path(entry["path"])
            before = link_metadata(root, path) if os.path.lexists(path) else None
            if os.path.lexists(path):
                remove_link_only(path)
            try:
                create_link(path, Path(entry["new_target"]), entry.get("type", "symlink"))
            except Exception:
                if before is not None and not os.path.lexists(path):
                    create_link(path, Path(before["target"]), before["type"])
                raise
            link_results.append(
                {
                    "path": entry["path"],
                    "status": "rebuilt",
                    "before": before,
                    "after": link_metadata(root, path),
                }
            )

        source_skills = root / SKILL_SOURCE_RELATIVE
        for entry in plan.get("skill_installations", []):
            if entry.get("status") == "aligned":
                continue
            source = source_skills / entry["skill"]
            destination = Path(entry["target"]) / entry["skill"]
            result = sync_skill_tree(source, destination, replace_skills, run)
            skill_results.append(
                {"skill": entry["skill"], "target": entry["target"], **result}
            )

        if not (root / "GLOBAL" / ".git").exists():
            git = command_path("git")
            if not git:
                raise RecoveryError("Git is required to initialize GLOBAL")
            completed = subprocess.run(
                [git, "-C", str(root / "GLOBAL"), "init", "-b", "main"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            if completed.returncode != 0:
                raise RecoveryError(f"cannot initialize GLOBAL Git: {completed.stderr.strip()}")
            git_initialized = True

        verification_targets = sorted(
            {Path(item["target"]) for item in plan.get("skill_installations", [])},
            key=str,
        )
        verification = verify_foundation(
            root, verification_targets, old_root=plan.get("old_root")
        )
        manifest = {
            "schema_version": 1,
            "status": "complete" if verification["ok"] else "blocked",
            "agent_root": str(root),
            "plan_sha256": expected,
            "backups": backups,
            "changed_files": changed_files,
            "link_results": link_results,
            "skill_results": skill_results,
            "git_initialized": git_initialized,
            "verification": verification,
        }
        write_json_atomic(run / "run-manifest.json", manifest)
        if not verification["ok"]:
            raise RecoveryError(f"post-repair verification failed; run manifest: {run / 'run-manifest.json'}")
        return {**manifest, "run_manifest": str(run / "run-manifest.json")}
    except Exception as exc:
        failure = {
            "schema_version": 1,
            "status": "blocked",
            "agent_root": str(root),
            "plan_sha256": expected,
            "backups": backups,
            "changed_files": changed_files,
            "link_results": link_results,
            "skill_results": skill_results,
            "git_initialized": git_initialized,
            "error": str(exc),
        }
        run_manifest = run / "run-manifest.json"
        write_json_atomic(run_manifest, failure)
        try:
            rollback_result = rollback(run_manifest)
        except Exception as rollback_exc:
            raise RecoveryError(
                f"repair failed and automatic rollback also failed; inspect {run_manifest}: {rollback_exc}"
            ) from exc
        raise RecoveryError(
            f"repair failed and was rolled back ({rollback_result['status']}): {exc}"
        ) from exc


def verify_foundation(
    root: Path, skill_targets: list[Path], old_root: str | None = None
) -> dict[str, Any]:
    root = validate_root(root)
    state = read_state(root)
    issues: list[str] = []
    for name in CORE_GLOBAL_FILES:
        if not (root / "GLOBAL" / name).is_file():
            issues.append(f"missing GLOBAL/{name}")
    if state.get("installed_agent_root") != str(root):
        issues.append("FOUNDATION_STATE.json does not match current Agent root")
    files, links = iter_tree(root)
    old_root_hits: list[str] = []
    recorded = state.get("installed_agent_root")
    for path in files:
        item = read_text_candidate(root, path)
        if item is None:
            continue
        if is_governance_text(item.relative):
            if item.raw.startswith(b"\xef\xbb\xbf") or "\r" in item.text:
                issues.append(f"encoding or LF issue: {item.relative.as_posix()}")
            if FOUNDATION_PLACEHOLDER_RE.search(item.text):
                issues.append(f"placeholder residue: {item.relative.as_posix()}")
        if old_root and old_root != str(root) and any(
            old in item.text for old, _ in path_replacements(old_root, str(root))
        ):
            old_root_hits.append(item.relative.as_posix())
    if old_root_hits:
        issues.append("old Agent root remains in: " + ", ".join(sorted(old_root_hits)))
    projects = parse_projects(root)
    for project in projects:
        if not project["exists"]:
            issues.append(f"registered project missing: {project['path']}")
        elif project["missing_entry_files"]:
            issues.append(
                f"project entry files missing: {project['path']}: "
                + ", ".join(project["missing_entry_files"])
            )
    skills = inspect_skill_targets(root, skill_targets)
    for item in skills:
        if item.get("status") != "aligned":
            issues.append(
                f"Skill installation not aligned: {item.get('skill', '?')} at {item['target']} ({item.get('status')})"
            )
    if not (root / "GLOBAL" / ".git").exists():
        issues.append("GLOBAL Git repository is missing")
    return {
        "ok": not issues,
        "agent_root": str(root),
        "issues": issues,
        "projects": projects,
        "links": links,
        "skill_installations": skills,
    }


def rollback(run_manifest: Path) -> dict[str, Any]:
    manifest = load_json(run_manifest)
    if manifest.get("status") == "rolled_back":
        return {
            "ok": True,
            "status": "rolled_back",
            "files": manifest.get("rolled_back_files", []),
            "skills": manifest.get("rolled_back_skills", []),
            "links": manifest.get("rolled_back_links", []),
            "git": manifest.get("git_rollback", "already_rolled_back"),
        }
    root = validate_root(Path(manifest["agent_root"]))
    run = run_manifest.parent
    restored: list[str] = []
    restored_skills: list[str] = []
    restored_links: list[str] = []
    changed_file_hashes = {
        entry["path"]: entry["after_sha256"]
        for entry in manifest.get("changed_files", [])
    }
    for relative_text, after_sha256 in changed_file_hashes.items():
        current = root / Path(relative_text)
        if not current.is_file() or is_link_or_reparse(current):
            raise RecoveryError(
                f"rollback refuses changed or missing repaired file: {current}"
            )
        if digest(current.read_bytes()) != after_sha256:
            raise RecoveryError(
                f"rollback refuses to overwrite a post-repair user change: {current}"
            )
    for entry in reversed(manifest.get("skill_results", [])):
        destination = Path(entry["destination"])
        status = entry.get("status")
        expected_inventory = entry.get("after_inventory_sha256")
        if status in {"installed", "replaced"} and destination.is_dir():
            if expected_inventory and inventory_digest(destination) != expected_inventory:
                raise RecoveryError(
                    f"rollback refuses to overwrite a post-repair Skill change: {destination}"
                )
        if status == "installed":
            if destination.exists():
                if is_link_or_reparse(destination) or not destination.is_dir():
                    raise RecoveryError(f"rollback refuses unsafe Skill path: {destination}")
                shutil.rmtree(destination)
            restored_skills.append(str(destination))
        elif status == "replaced":
            backup = run / entry["backup"]
            if not backup.is_dir():
                raise RecoveryError(f"Skill rollback backup missing: {backup}")
            if destination.exists():
                if is_link_or_reparse(destination) or not destination.is_dir():
                    raise RecoveryError(f"rollback refuses unsafe Skill path: {destination}")
                shutil.rmtree(destination)
            shutil.copytree(backup, destination)
            restored_skills.append(str(destination))

    for entry in reversed(manifest.get("link_results", [])):
        path = root / Path(entry["path"])
        if os.path.lexists(path):
            if link_metadata(root, path) != entry.get("after"):
                raise RecoveryError(
                    f"rollback refuses to overwrite a post-repair link change: {path}"
                )
            remove_link_only(path)
        before = entry.get("before")
        if before is not None:
            create_link(path, Path(before["target"]), before["type"])
        restored_links.append(entry["path"])

    for entry in reversed(manifest.get("backups", [])):
        relative = Path(entry["path"])
        destination = root / relative
        backup = run / "files" / relative
        if entry.get("existed"):
            if not backup.is_file():
                raise RecoveryError(f"rollback backup missing: {backup}")
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(backup.read_bytes())
        elif destination.exists():
            if destination.is_file() and not is_link_or_reparse(destination):
                destination.unlink()
            else:
                raise RecoveryError(f"rollback refuses unexpected non-file: {destination}")
        restored.append(relative.as_posix())
    git_rollback = "not_created_by_run"
    if manifest.get("git_initialized"):
        git_dir = root / "GLOBAL" / ".git"
        if git_dir.is_dir():
            git = command_path("git")
            has_head = False
            if git:
                completed = subprocess.run(
                    [git, "-C", str(root / "GLOBAL"), "rev-parse", "--verify", "HEAD"],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )
                has_head = completed.returncode == 0
            if has_head:
                git_rollback = "preserved_because_repository_has_commits"
            else:
                shutil.rmtree(git_dir)
                git_rollback = "removed_empty_repository_created_by_run"
    manifest["status"] = "rolled_back"
    manifest["rolled_back_files"] = restored
    manifest["rolled_back_skills"] = restored_skills
    manifest["rolled_back_links"] = restored_links
    manifest["git_rollback"] = git_rollback
    write_json_atomic(run_manifest, manifest)
    return {
        "ok": True,
        "status": "rolled_back",
        "files": restored,
        "skills": restored_skills,
        "links": restored_links,
        "git": git_rollback,
    }


def print_json(value: dict[str, Any], stream: Any = sys.stdout) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2), file=stream)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="foundation_recovery.py")
    sub = result.add_subparsers(dest="command", required=True)
    for name in ("audit", "plan", "verify"):
        command = sub.add_parser(name)
        command.add_argument("--root", type=Path)
        command.add_argument("--skill-target", action="append", default=[], type=Path)
        if name in {"audit", "plan"}:
            command.add_argument("--old-root")
            command.add_argument("--obsidian-target", type=Path)
            command.add_argument("--report", type=Path)
        if name == "verify":
            command.add_argument("--old-root")
    repair = sub.add_parser("repair")
    repair.add_argument("--plan", required=True, type=Path)
    repair.add_argument("--confirm-plan-sha256", required=True)
    repair.add_argument("--replace-skill-installations", action="store_true")
    rollback_parser = sub.add_parser("rollback")
    rollback_parser.add_argument("--run-manifest", required=True, type=Path)
    return result


def main(argv: Iterable[str] | None = None) -> int:
    args = parser().parse_args(list(argv) if argv is not None else None)
    try:
        if args.command in {"audit", "plan", "verify"}:
            root = validate_root(args.root) if args.root else validate_root(discover_agent_root())
            targets = [lexical_abs(path) for path in args.skill_target]
        if args.command in {"audit", "plan"}:
            output = make_plan(root, args.old_root, targets, args.obsidian_target)
            if args.report:
                write_json_atomic(args.report, output)
        elif args.command == "verify":
            output = verify_foundation(root, targets, old_root=args.old_root)
        elif args.command == "repair":
            output = execute_repair(
                args.plan, args.confirm_plan_sha256, args.replace_skill_installations
            )
        else:
            output = rollback(args.run_manifest)
    except RecoveryError as exc:
        print_json({"ok": False, "error": str(exc)}, sys.stderr)
        return 2
    print_json(output)
    return 0 if output.get("ok", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
