#!/usr/bin/env python3
"""Fixture tests for align_agent_projects.py."""

from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path


SCRIPT = Path(__file__).with_name("align_agent_projects.py")
SPEC = importlib.util.spec_from_file_location("align_agent_projects", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def main() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        fixture_root = Path(temp_dir).resolve()
        projects_md = fixture_root / "PROJECTS.md"
        projects_md.write_text(
            """# 项目索引

## 核心工作区

- Agent 全局治理工作区：`X:\\AgentRoot\\GLOBAL`
- Obsidian 入口：`X:\\AgentRoot\\GLOBAL\\obsidian-resource`

## 活跃项目

- 项目甲：`X:\\AgentRoot\\项目甲` - 说明
- 项目乙：`X:\\AgentRoot\\项目乙`

## 备注

- 示例：`X:\\Example`
""",
            encoding="utf-8",
            newline="\n",
        )

        projects = MODULE.parse_projects(projects_md)
        assert [project.name for project in projects] == ["项目甲", "项目乙"]
        by_name = MODULE.parse_projects(projects_md, ["项目乙"])
        assert [project.name for project in by_name] == ["项目乙"]
        by_path = MODULE.parse_projects(projects_md, [r"X:\AgentRoot\项目甲"])
        assert [project.name for project in by_path] == ["项目甲"]

        project_root = fixture_root / "project"
        project_root.mkdir()
        (project_root / "AGENTS.md").write_text(
            "本项目飞书 Profile 不继承全局默认值。\n",
            encoding="utf-8",
            newline="\n",
        )
        report = MODULE.audit_project(
            MODULE.Project("project", project_root), fixture_root / "GLOBAL", None, ["全局"]
        )
        assert report.status == "aligned"
        assert report.checks["text_issues"]["override_or_conflict_hits"] == ["AGENTS.md"]

        (project_root / "AGENTS.md").write_text(
            "本项目拒绝 GLOBAL 上层规则。\n",
            encoding="utf-8",
            newline="\n",
        )
        report = MODULE.audit_project(
            MODULE.Project("project", project_root), fixture_root / "GLOBAL", None, ["GLOBAL"]
        )
        assert report.status == "needs_manual_decision"
        assert report.checks["text_issues"]["explicit_conflict_hits"] == ["AGENTS.md"]

    print("fixture tests passed")


if __name__ == "__main__":
    main()
