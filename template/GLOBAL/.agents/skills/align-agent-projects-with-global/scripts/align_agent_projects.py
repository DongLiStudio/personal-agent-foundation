#!/usr/bin/env python3
"""Read-only audit helper for align-agent-projects-with-global."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


PROJECT_LINE_RE = re.compile(r"^-\s+(.+?)[：:]\s*`([^`]+)`(?:\s+-\s+(.*))?$")
SECRET_RE = re.compile(
    r"(?i)(api[_-]?key|secret|token|password|passwd|private[_-]?key)\s*[:=]\s*['\"]?[^'\"\s]{8,}"
)
TEXT_EXTENSIONS = {
    ".md",
    ".txt",
    ".yaml",
    ".yml",
    ".json",
    ".toml",
    ".ini",
    ".cfg",
    ".ps1",
    ".sh",
    ".py",
}
CANDIDATE_ENTRY_FILES = ("README.md", "STATUS.md", "AGENTS.md")
CANDIDATE_SCAN_DIRS = ("tasks", "docs", ".agents", "archive")
DEFAULT_RULE_FILES = ("README.md", "GLOBAL_CONTEXT.md")
STATUS_ORDER = ("blocked", "needs_manual_decision", "aligned", "no_change_needed")
MANAGED_PROJECTS_HEADING = "活跃项目"
OVERRIDE_RE = re.compile(r"(覆盖|例外|冲突|不继承|拒绝|违反|不遵循|不适用|取代|替代|override|exception|conflict)", re.IGNORECASE)
GLOBAL_CONTEXT_RE = re.compile(r"(GLOBAL|全局|上层规则|继承)", re.IGNORECASE)
PROJECT_ASSERTION_RE = re.compile(r"(本项目|本仓库|项目规则|项目约定)", re.IGNORECASE)
EXPLICIT_CONFLICT_RE = re.compile(
    r"((拒绝|违反|不遵循|不适用|取代|替代).{0,40}(GLOBAL|全局|上层规则)|(GLOBAL|全局|上层规则).{0,40}(明确冲突|不再适用|不予继承))",
    re.IGNORECASE,
)


def lexical_abs(path: Path) -> Path:
    return Path(os.path.abspath(path))


@dataclass
class Project:
    name: str
    path: Path
    description: str = ""


@dataclass
class ProjectReport:
    name: str
    path: str
    status: str
    findings: list[str] = field(default_factory=list)
    checks: dict[str, object] = field(default_factory=dict)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def is_probably_text(path: Path) -> bool:
    return path.suffix.lower() in TEXT_EXTENSIONS or path.name in CANDIDATE_ENTRY_FILES


def is_link_or_reparse(path: Path) -> bool:
    if path.is_symlink():
        return True
    if os.name == "nt":
        try:
            import stat

            return bool(path.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)
        except Exception:
            return False
    return False


def existing_path_chain(path: Path) -> list[Path]:
    absolute = lexical_abs(path)
    chain: list[Path] = []
    current = absolute
    while not current.exists() and current != current.parent:
        current = current.parent
    while True:
        chain.append(current)
        if current == current.parent:
            break
        current = current.parent
    return list(reversed(chain))


def has_link_or_reparse_in_existing_chain(path: Path) -> bool:
    return any(is_link_or_reparse(item) for item in existing_path_chain(path))


def parse_projects(projects_md: Path, scope: list[str] | None = None) -> list[Project]:
    content = read_text(projects_md)
    projects: list[Project] = []
    wanted = {item.lower() for item in scope or []}
    in_managed_section = False
    for line in content.splitlines():
        heading = re.match(r"^##\s+(.+?)\s*$", line.strip())
        if heading:
            in_managed_section = heading.group(1).strip() == MANAGED_PROJECTS_HEADING
            continue
        if not in_managed_section:
            continue
        match = PROJECT_LINE_RE.match(line.strip())
        if not match:
            continue
        name, raw_path, description = match.groups()
        project = Project(name=name.strip(), path=Path(raw_path), description=(description or "").strip())
        if wanted and project.name.lower() not in wanted and str(project.path).lower() not in wanted:
            continue
        projects.append(project)
    return projects


def git_status(path: Path) -> dict[str, object]:
    if not (path / ".git").exists():
        return {"is_git_repo": False, "dirty": None, "porcelain": []}
    result = subprocess.run(
        ["git", "-C", str(path), "status", "--short"],
        text=True,
        capture_output=True,
        check=False,
    )
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    return {
        "is_git_repo": True,
        "dirty": bool(lines),
        "porcelain": lines,
        "error": result.stderr.strip() if result.returncode else "",
    }


def migration_rewrite_dirty_check(project_root: Path, old_root: str, new_root: str) -> dict[str, object]:
    result = subprocess.run(
        ["git", "-C", str(project_root), "diff", "--name-only", "--diff-filter=M", "-z"],
        capture_output=True,
        check=False,
    )
    if result.returncode:
        return {"accepted": False, "paths": [], "error": result.stderr.decode("utf-8", errors="replace").strip()}
    paths = [item.decode("utf-8", errors="surrogateescape") for item in result.stdout.split(b"\0") if item]
    porcelain = git_status(project_root).get("porcelain", [])
    if not paths or len(paths) != len(porcelain) or any(not line.startswith(" M ") for line in porcelain):
        return {"accepted": False, "paths": paths, "error": "dirty tree contains staged, untracked, deleted, renamed, or non-file changes"}
    variants = [
        (old_root, new_root),
        (old_root.replace("\\", "/"), new_root.replace("\\", "/")),
        (old_root.replace("\\", "\\\\"), new_root.replace("\\", "\\\\")),
    ]
    checked = []
    for relative in paths:
        current_path = project_root / relative
        if not is_probably_text(current_path):
            return {"accepted": False, "paths": checked, "error": f"modified file is not an approved text file: {relative}"}
        head = subprocess.run(
            ["git", "-C", str(project_root), "show", f"HEAD:{relative}"],
            capture_output=True,
            check=False,
        )
        if head.returncode:
            return {"accepted": False, "paths": checked, "error": f"cannot read HEAD version: {relative}"}
        try:
            expected = head.stdout.decode("utf-8-sig")
            current = current_path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            return {"accepted": False, "paths": checked, "error": f"modified file is not UTF-8 text: {relative}"}
        for old, new in variants:
            expected = expected.replace(old, new)
        if expected != current:
            return {"accepted": False, "paths": checked, "error": f"change is not an exact root-path rewrite: {relative}"}
        checked.append(relative)
    return {"accepted": True, "paths": checked, "error": ""}


def iter_scan_files(root: Path) -> Iterable[Path]:
    for name in CANDIDATE_ENTRY_FILES:
        file_path = root / name
        if file_path.exists():
            yield file_path
    for dirname in CANDIDATE_SCAN_DIRS:
        base = root / dirname
        if not base.exists() or is_link_or_reparse(base):
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            current = Path(dirpath)
            kept_dirs = []
            for dirname_item in dirnames:
                child = current / dirname_item
                if child.name == ".git" or is_link_or_reparse(child):
                    continue
                kept_dirs.append(dirname_item)
            dirnames[:] = kept_dirs
            for filename in filenames:
                file_path = current / filename
                if is_probably_text(file_path):
                    yield file_path


def iter_hash_files(root: Path) -> Iterable[Path]:
    for dirpath, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
        current = Path(dirpath)
        kept_dirs = []
        for dirname_item in dirnames:
            child = current / dirname_item
            if child.name in {".git", "__pycache__"} or is_link_or_reparse(child):
                continue
            kept_dirs.append(dirname_item)
        dirnames[:] = kept_dirs
        for filename in filenames:
            path = current / filename
            if not is_link_or_reparse(path):
                yield path


def load_rule_text(global_root: Path, rule_files: list[str] | None) -> tuple[str, list[str]]:
    selected = list(rule_files or DEFAULT_RULE_FILES)
    texts: list[str] = []
    loaded: list[str] = []
    global_root = lexical_abs(global_root)
    for raw_file in selected:
        candidate = lexical_abs(global_root / raw_file)
        try:
            candidate.relative_to(global_root)
        except ValueError:
            continue
        if not candidate.exists() or not candidate.is_file() or is_link_or_reparse(candidate):
            continue
        try:
            texts.append(read_text(candidate))
            loaded.append(str(candidate.relative_to(global_root)).replace("\\", "/"))
        except UnicodeDecodeError:
            continue
    return "\n".join(texts), loaded


def extract_rule_terms(rule_text: str, summary: str) -> list[str]:
    raw_text = f"{rule_text}\n{summary}"
    candidates = set()
    for match in re.findall(r"`([^`]{3,120})`", raw_text):
        candidates.add(match.strip())
    for match in re.findall(r"[A-Za-z0-9_.:/\\-]{4,}", raw_text):
        candidates.add(match.strip())
    for line in raw_text.splitlines():
        stripped = line.strip()
        if any(marker in stripped for marker in ("必须", "禁止", "默认", "除非", "should", "must", "never")):
            for word in re.split(r"\W+", stripped):
                if len(word) >= 4:
                    candidates.add(word)
    filtered = []
    ignored = {"http", "https", "text", "true", "false", "null"}
    for term in sorted(candidates, key=lambda item: (len(item), item.lower())):
        lowered = term.lower()
        if lowered in ignored or len(term) > 120:
            continue
        filtered.append(term)
    return filtered[:80]


def find_text_issues(
    project_root: Path,
    global_root: Path,
    old_root: str | None,
    rule_terms: list[str],
) -> dict[str, list[str]]:
    issues: dict[str, list[str]] = {
        "old_root_hits": [],
        "current_global_path_hits": [],
        "rule_term_hits": [],
        "override_or_conflict_hits": [],
        "explicit_conflict_hits": [],
        "secret_like_hits": [],
        "evidence": [],
    }
    global_root_text = str(global_root)
    for file_path in iter_scan_files(project_root):
        try:
            text = read_text(file_path)
        except UnicodeDecodeError:
            continue
        relative = str(file_path.relative_to(project_root))
        if old_root and old_root in text:
            issues["old_root_hits"].append(relative)
            for line_number, line in enumerate(text.splitlines(), 1):
                count = line.count(old_root)
                if count:
                    issues["evidence"].append({
                        "file": relative,
                        "line": line_number,
                        "kind": "old_root",
                        "matched_term": old_root,
                        "count": count,
                        "excerpt_hash": hashlib.sha256(line.strip().encode("utf-8")).hexdigest(),
                    })
        if global_root_text in text:
            issues["current_global_path_hits"].append(relative)
            for line_number, line in enumerate(text.splitlines(), 1):
                count = line.count(global_root_text)
                if count:
                    issues["evidence"].append({
                        "file": relative,
                        "line": line_number,
                        "kind": "current_global_path",
                        "matched_term": global_root_text,
                        "count": count,
                        "excerpt_hash": hashlib.sha256(line.strip().encode("utf-8")).hexdigest(),
                    })
        if SECRET_RE.search(text):
            issues["secret_like_hits"].append(relative)
        matched_terms = [term for term in rule_terms if term in text]
        if matched_terms:
            issues["rule_term_hits"].append(relative)
            for line_number, line in enumerate(text.splitlines(), 1):
                for term in matched_terms:
                    count = line.count(term)
                    if count:
                        issues["evidence"].append({
                            "file": relative,
                            "line": line_number,
                            "kind": "rule_term",
                            "matched_term": term,
                            "count": count,
                            "excerpt_hash": hashlib.sha256(line.strip().encode("utf-8")).hexdigest(),
                        })
        relative_parts = Path(relative).parts
        is_historical = bool(relative_parts and relative_parts[0].lower() == "archive")
        override_lines = [
            (line_number, line)
            for line_number, line in enumerate(text.splitlines(), 1)
            if OVERRIDE_RE.search(line) and GLOBAL_CONTEXT_RE.search(line)
        ]
        if override_lines and not is_historical:
            issues["override_or_conflict_hits"].append(relative)
            for line_number, line in override_lines:
                for match in OVERRIDE_RE.finditer(line):
                    issues["evidence"].append({
                        "file": relative,
                        "line": line_number,
                        "kind": "override_or_conflict",
                        "matched_term": match.group(0),
                        "count": 1,
                        "excerpt_hash": hashlib.sha256(line.strip().encode("utf-8")).hexdigest(),
                    })
                if PROJECT_ASSERTION_RE.search(line) and EXPLICIT_CONFLICT_RE.search(line):
                    issues["explicit_conflict_hits"].append(relative)
    return issues


def audit_project(
    project: Project,
    global_root: Path,
    old_root: str | None,
    rule_terms: list[str],
    accept_migration_rewrites: bool = False,
) -> ProjectReport:
    findings: list[str] = []
    checks: dict[str, object] = {}
    root = project.path

    if not root.exists():
        return ProjectReport(project.name, str(root), "blocked", ["项目路径不存在。"], checks)
    if not root.is_dir():
        return ProjectReport(project.name, str(root), "blocked", ["项目路径不是目录。"], checks)
    if has_link_or_reparse_in_existing_chain(root):
        return ProjectReport(project.name, str(root), "blocked", ["项目路径是链接或 reparse point，按边界禁止跟随。"], checks)

    git = git_status(root)
    checks["git"] = git
    migration_dirty = {"accepted": False, "paths": [], "error": "not requested"}
    if git.get("dirty") and accept_migration_rewrites and old_root:
        migration_dirty = migration_rewrite_dirty_check(root, old_root, str(global_root.parent))
        checks["migration_rewrite_dirty"] = migration_dirty
    if git.get("dirty") and not migration_dirty["accepted"]:
        findings.append("Git 工作树存在未提交内容，需要人工确认后再实施。")
    elif migration_dirty["accepted"]:
        findings.append("Git 未提交内容已证明仅为迁移产生的精确根路径重写。")

    text_issues = find_text_issues(root, global_root, old_root, rule_terms)
    checks["text_issues"] = text_issues
    if text_issues["old_root_hits"]:
        findings.append("发现旧根路径命中：" + ", ".join(text_issues["old_root_hits"]))
    if text_issues["override_or_conflict_hits"]:
        findings.append("发现项目覆盖或冲突候选，已保留供 Agent 结合 GLOBAL 规则判断：" + ", ".join(text_issues["override_or_conflict_hits"]))
    if text_issues["explicit_conflict_hits"]:
        findings.append("发现明确拒绝或取代 GLOBAL 的声明，需要人工决定：" + ", ".join(sorted(set(text_issues["explicit_conflict_hits"]))))
    if text_issues["secret_like_hits"]:
        findings.append("发现疑似敏感信息命中，需要人工复核：" + ", ".join(text_issues["secret_like_hits"]))

    for dirname in CANDIDATE_SCAN_DIRS:
        base = root / dirname
        if base.exists() and is_link_or_reparse(base):
            findings.append(f"{dirname} 是链接或 reparse point，已跳过。")

    if text_issues["secret_like_hits"]:
        status = "blocked"
    elif (git.get("dirty") and not migration_dirty["accepted"]) or text_issues["old_root_hits"] or text_issues["explicit_conflict_hits"]:
        status = "needs_manual_decision"
    elif text_issues["rule_term_hits"] or text_issues["current_global_path_hits"]:
        status = "aligned"
    else:
        status = "no_change_needed"

    return ProjectReport(project.name, str(root), status, findings, checks)


def write_reports(
    reports: list[ProjectReport],
    output: Path,
    global_root: Path,
    summary: str,
    loaded_rule_files: list[str],
    rule_terms: list[str],
    warnings: list[str] | None = None,
) -> None:
    status_counts = {status: 0 for status in STATUS_ORDER}
    for report in reports:
        status_counts[report.status] = status_counts.get(report.status, 0) + 1
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "global_root": str(global_root),
        "global_change_summary": summary,
        "loaded_rule_files": loaded_rule_files,
        "rule_terms": rule_terms,
        "warnings": warnings or [],
        "status_counts": status_counts,
        "projects": [report.__dict__ for report in reports],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")

    md_path = output.with_suffix(".md")
    lines = [
        "# GLOBAL 项目对齐审计报告",
        "",
        f"- GLOBAL：`{global_root}`",
        f"- 摘要：{summary or '未提供'}",
        f"- 规则文件：{', '.join(loaded_rule_files) if loaded_rule_files else '未加载'}",
        "",
        "| 项目 | 状态 | 主要发现 |",
        "| --- | --- | --- |",
    ]
    for report in reports:
        finding = "<br>".join(report.findings) if report.findings else "无"
        lines.append(f"| {report.name} | `{report.status}` | {finding} |")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def hash_tree(root: Path) -> dict[str, str]:
    files: dict[str, str] = {}
    for path in sorted(iter_hash_files(root)):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        files[str(path.relative_to(root)).replace("\\", "/")] = digest
    return files


def command_audit(args: argparse.Namespace) -> int:
    global_root = lexical_abs(Path(args.global_root))
    if has_link_or_reparse_in_existing_chain(global_root):
        Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "global_root": str(global_root),
            "global_change_summary": args.global_change_summary or "",
            "loaded_rule_files": [],
            "rule_terms": [],
            "warnings": ["global root path contains a link or reparse point"],
            "status_counts": {status: 0 for status in STATUS_ORDER},
            "projects": [],
        }
        Path(args.report).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        print(f"global root contains link or reparse point: {global_root}", file=sys.stderr)
        return 2
    projects_md = global_root / "PROJECTS.md"
    if not projects_md.exists():
        print(f"PROJECTS.md not found under {global_root}", file=sys.stderr)
        return 2
    projects = parse_projects(projects_md, args.scope)
    rule_text, loaded_rule_files = load_rule_text(global_root, args.rule_file)
    rule_terms = extract_rule_terms(rule_text, args.global_change_summary or "")
    reports = [
        audit_project(project, global_root, args.old_root, rule_terms, args.accept_migration_rewrites)
        for project in projects
    ]
    if not projects and not args.allow_empty_projects:
        write_reports(
            reports,
            Path(args.report),
            global_root,
            args.global_change_summary or "",
            loaded_rule_files,
            rule_terms,
            warnings=["PROJECTS.md contains no matching managed projects"],
        )
        print(f"audited=0 blocked_or_manual=0 report={args.report}")
        return 1
    write_reports(reports, Path(args.report), global_root, args.global_change_summary or "", loaded_rule_files, rule_terms)
    failing = [report for report in reports if report.status in {"blocked", "needs_manual_decision"}]
    print(f"audited={len(reports)} blocked_or_manual={len(failing)} report={args.report}")
    return 1 if failing and args.fail_on_attention else 0


def command_hash(args: argparse.Namespace) -> int:
    tree = hash_tree(Path(args.path))
    Path(args.output).write_text(json.dumps(tree, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"files={len(tree)} output={args.output}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only GLOBAL project alignment helper.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    audit = subparsers.add_parser("audit", help="Audit projects listed in GLOBAL/PROJECTS.md.")
    audit.add_argument("--global-root", required=True)
    audit.add_argument("--old-root")
    audit.add_argument("--global-change-summary", default="")
    audit.add_argument("--rule-file", action="append", help="GLOBAL-relative rule file to load. Defaults to README.md and GLOBAL_CONTEXT.md.")
    audit.add_argument("--scope", nargs="*")
    audit.add_argument("--report", required=True)
    audit.add_argument("--fail-on-attention", action="store_true")
    audit.add_argument("--allow-empty-projects", action="store_true")
    audit.add_argument(
        "--accept-migration-rewrites",
        action="store_true",
        help="Accept dirty projects only when every change is an exact old-root to new-root text replacement.",
    )
    audit.set_defaults(func=command_audit)

    hash_cmd = subparsers.add_parser("hash-tree", help="Write a SHA-256 manifest for a folder.")
    hash_cmd.add_argument("--path", required=True)
    hash_cmd.add_argument("--output", required=True)
    hash_cmd.set_defaults(func=command_hash)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
