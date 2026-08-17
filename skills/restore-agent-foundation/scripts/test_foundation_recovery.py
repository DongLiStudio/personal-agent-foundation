from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


SCRIPT = Path(__file__).with_name("foundation_recovery.py")
spec = importlib.util.spec_from_file_location("foundation_recovery", SCRIPT)
assert spec and spec.loader
recovery = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = recovery
spec.loader.exec_module(recovery)


CORE = (
    "README.md",
    "GLOBAL_CONTEXT.md",
    "OBSIDIAN_LINK.md",
    "SKILL_DEPENDENCIES.md",
    "LARK_PROFILES.md",
    "SERVER_PROFILES.md",
    "GITHUB_ACCOUNTS.md",
    "SCHEDULE_PREFERENCES.md",
)


class FoundationRecoveryTests(unittest.TestCase):
    def test_command_path_discovers_windows_user_npm_shim(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            appdata = Path(temp) / "AppData" / "Roaming"
            shim = appdata / "npm" / "lark-cli.cmd"
            shim.parent.mkdir(parents=True)
            shim.write_text("@echo off\n", encoding="utf-8")
            with (
                mock.patch.object(recovery.os, "name", "nt"),
                mock.patch.object(recovery.shutil, "which", return_value=None),
                mock.patch.dict(recovery.os.environ, {"APPDATA": str(appdata)}, clear=False),
            ):
                self.assertEqual(str(recovery.lexical_abs(shim)), recovery.command_path("lark-cli"))

    def test_obsidian_gui_is_not_accepted_as_cli(self) -> None:
        with (
            mock.patch.object(recovery.os, "name", "nt"),
            mock.patch.object(recovery.shutil, "which", return_value=None),
            mock.patch.dict(recovery.os.environ, {"LOCALAPPDATA": "Z:\\missing"}, clear=False),
        ):
            self.assertIsNone(recovery.obsidian_cli_path())

    def make_foundation(self, base: Path, include_state: bool = True) -> tuple[Path, str]:
        root = base / "新电脑 Agent"
        global_root = root / "GLOBAL"
        skills = global_root / ".agents" / "skills"
        sample = skills / "sample-skill"
        sample.mkdir(parents=True)
        (sample / "SKILL.md").write_text(
            "---\nname: sample-skill\ndescription: fixture\n---\n",
            encoding="utf-8",
            newline="\n",
        )
        old_root = str(base / "旧电脑 Agent")
        for name in CORE:
            (global_root / name).write_text(
                f"# {name}\n旧根：`{old_root}`\n",
                encoding="utf-8",
                newline="\n",
            )
        project = root / "示例项目"
        project.mkdir()
        for name in recovery.PROJECT_ENTRY_FILES:
            (project / name).write_text(f"# {name}\n", encoding="utf-8", newline="\n")
        (global_root / "PROJECTS.md").write_text(
            f"# Projects\n\n## 核心工作区\n\n- GLOBAL：`{old_root}{os.sep}GLOBAL`\n"
            f"\n## 活跃项目\n\n- 示例项目：`{old_root}{os.sep}示例项目`\n"
            "\n## 路由规则\n\n- 这里只是说明。\n",
            encoding="utf-8",
            newline="\n",
        )
        (global_root / ".gitignore").write_text(
            "/.foundation-recovery/\n", encoding="utf-8", newline="\n"
        )
        if include_state:
            recovery.write_json_atomic(
                global_root / "FOUNDATION_STATE.json",
                {
                    "schema_version": 1,
                    "product": "Personal Agent Foundation",
                    "installed_agent_root": old_root,
                    "global_root": str(Path(old_root) / "GLOBAL"),
                },
            )
        return root, old_root

    def test_plan_is_read_only_and_detects_moved_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root, old_root = self.make_foundation(Path(temp))
            before = recovery.tree_inventory(root)
            target = Path(temp) / "host skills"
            plan = recovery.make_plan(root, None, [target], None)
            self.assertEqual(old_root, plan["old_root"])
            self.assertTrue(plan["path_rewrites"])
            self.assertTrue(any(item["kind"] == "sync_skill_installations" for item in plan["actions"]))
            self.assertFalse(plan["blocking_issues"])
            self.assertEqual(before, recovery.tree_inventory(root))
            self.assertEqual(plan["plan_sha256"], recovery.plan_digest(plan))

    def test_project_parser_ignores_non_project_sections(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root, _ = self.make_foundation(Path(temp))
            projects = recovery.parse_projects(root)
            self.assertEqual(1, len(projects))
            self.assertTrue(projects[0]["path"].endswith("示例项目"))

    def test_missing_state_is_recoverable_when_old_root_is_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root, old_root = self.make_foundation(Path(temp), include_state=False)
            plan = recovery.make_plan(root, old_root, [], None)
            self.assertNotIn("FOUNDATION_STATE.json", plan["missing_core_files"])
            self.assertFalse(plan["blocking_issues"])
            self.assertTrue(any(item["kind"] == "update_foundation_state" for item in plan["actions"]))

    def test_missing_state_requests_old_root_without_guessing(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root, _ = self.make_foundation(Path(temp), include_state=False)
            plan = recovery.make_plan(root, None, [], None)
            self.assertTrue(
                any(
                    item["kind"] == "old_root_confirmation"
                    for item in plan["interactive_gates"]
                )
            )

    def test_server_profile_is_core_and_ssh_is_an_interactive_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root, _ = self.make_foundation(Path(temp))
            server_profiles = root / "GLOBAL" / "SERVER_PROFILES.md"
            server_profiles.unlink()
            plan = recovery.make_plan(root, None, [], None)
            self.assertIn("SERVER_PROFILES.md", plan["missing_core_files"])
            self.assertTrue(
                any(item["kind"] == "server_connection" for item in plan["interactive_gates"])
            )

    def test_unrelated_mustache_template_is_not_foundation_residue(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root, _ = self.make_foundation(Path(temp))
            project_template = root / "示例项目" / "docs" / "template.md"
            project_template.parent.mkdir()
            project_template.write_text(
                "Hello " + chr(123) * 2 + "customer_name" + chr(125) * 2 + "\n",
                encoding="utf-8",
            )
            plan = recovery.make_plan(root, None, [], None)
            self.assertNotIn(
                "示例项目/docs/template.md", plan["placeholder_residue"]
            )

    def test_project_code_encoding_and_foundation_tokens_are_not_repaired(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root, _ = self.make_foundation(Path(temp))
            project_file = root / "示例项目" / "src" / "fixture.txt"
            project_file.parent.mkdir()
            project_file.write_bytes(
                b"\xef\xbb\xbf"
                + (chr(123) * 2 + "AGENT_ROOT" + chr(125) * 2 + "\r\n").encode(
                    "ascii"
                )
            )
            plan = recovery.make_plan(root, None, [], None)
            self.assertNotIn(
                "示例项目/src/fixture.txt", plan["placeholder_residue"]
            )
            self.assertFalse(
                any(
                    item["path"] == "示例项目/src/fixture.txt"
                    for item in plan["text_issues"]
                )
            )

            global_readme = root / "GLOBAL" / "README.md"
            global_readme.write_bytes(b"# governance\r\n")
            plan = recovery.make_plan(root, None, [], None)
            self.assertTrue(
                any(
                    item["path"] == "GLOBAL/README.md"
                    for item in plan["text_issues"]
                )
            )

    def test_repair_requires_exact_confirmed_plan_hash(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root, _ = self.make_foundation(Path(temp))
            plan = recovery.make_plan(root, None, [], None)
            plan_path = Path(temp) / "plan.json"
            recovery.write_json_atomic(plan_path, plan)
            with self.assertRaisesRegex(recovery.RecoveryError, "plan hash mismatch"):
                recovery.execute_repair(plan_path, "0" * 64, False)

    def test_repair_restores_paths_skills_and_verifies(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root, old_root = self.make_foundation(Path(temp))
            target = Path(temp) / "host skills"
            plan = recovery.make_plan(root, None, [target], None)
            plan_path = Path(temp) / "plan.json"
            recovery.write_json_atomic(plan_path, plan)
            result = recovery.execute_repair(plan_path, plan["plan_sha256"], False)
            self.assertEqual("complete", result["status"])
            self.assertTrue((target / "sample-skill" / "SKILL.md").is_file())
            state = recovery.load_json(root / recovery.STATE_RELATIVE)
            self.assertEqual(str(root), state["installed_agent_root"])
            self.assertNotIn(old_root, (root / "GLOBAL" / "PROJECTS.md").read_text(encoding="utf-8"))
            self.assertTrue(
                recovery.verify_foundation(root, [target], old_root=old_root)["ok"]
            )

    def test_plan_detects_post_plan_file_change(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root, _ = self.make_foundation(Path(temp))
            plan = recovery.make_plan(root, None, [], None)
            plan_path = Path(temp) / "plan.json"
            recovery.write_json_atomic(plan_path, plan)
            changed = root / "GLOBAL" / "README.md"
            changed.write_text("changed\n", encoding="utf-8", newline="\n")
            with self.assertRaisesRegex(recovery.RecoveryError, "changed after plan"):
                recovery.execute_repair(plan_path, plan["plan_sha256"], False)

    def test_post_write_failure_rolls_back_files_and_new_skill_installation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root, old_root = self.make_foundation(Path(temp))
            target = Path(temp) / "host skills"
            plan = recovery.make_plan(root, None, [target], None)
            plan_path = Path(temp) / "plan.json"
            recovery.write_json_atomic(plan_path, plan)
            original_verify = recovery.verify_foundation
            recovery.verify_foundation = lambda *_: {"ok": False, "issues": ["fixture"]}
            try:
                with self.assertRaisesRegex(recovery.RecoveryError, "rolled back"):
                    recovery.execute_repair(plan_path, plan["plan_sha256"], False)
            finally:
                recovery.verify_foundation = original_verify
            state = recovery.load_json(root / recovery.STATE_RELATIVE)
            self.assertEqual(old_root, state["installed_agent_root"])
            self.assertIn(old_root, (root / "GLOBAL" / "PROJECTS.md").read_text(encoding="utf-8"))
            self.assertFalse((target / "sample-skill").exists())
            latest = sorted((root / "GLOBAL" / ".foundation-recovery").iterdir())[-1]
            self.assertEqual("rolled_back", recovery.load_json(latest / "run-manifest.json")["status"])

    def test_different_skill_copy_requires_extra_confirmation_and_rolls_back(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root, _ = self.make_foundation(Path(temp))
            target = Path(temp) / "host skills"
            installed = target / "sample-skill"
            installed.mkdir(parents=True)
            (installed / "SKILL.md").write_text("local customization\n", encoding="utf-8")
            plan = recovery.make_plan(root, None, [target], None)
            plan_path = Path(temp) / "plan.json"
            recovery.write_json_atomic(plan_path, plan)
            with self.assertRaisesRegex(recovery.RecoveryError, "differs"):
                recovery.execute_repair(plan_path, plan["plan_sha256"], False)
            self.assertFalse((root / "GLOBAL" / ".foundation-recovery").exists())

            plan = recovery.make_plan(root, None, [target], None)
            plan_path = Path(temp) / "plan-2.json"
            recovery.write_json_atomic(plan_path, plan)
            result = recovery.execute_repair(plan_path, plan["plan_sha256"], True)
            self.assertEqual("complete", result["status"])
            run_manifest = Path(result["run_manifest"])
            rolled_back = recovery.rollback(run_manifest)
            self.assertEqual("rolled_back", rolled_back["status"])
            self.assertEqual(
                "local customization\n",
                (installed / "SKILL.md").read_text(encoding="utf-8"),
            )
            self.assertEqual("rolled_back", recovery.rollback(run_manifest)["status"])

    def test_rollback_refuses_to_overwrite_post_repair_user_change(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root, _ = self.make_foundation(Path(temp))
            plan = recovery.make_plan(root, None, [], None)
            plan_path = Path(temp) / "plan.json"
            recovery.write_json_atomic(plan_path, plan)
            result = recovery.execute_repair(plan_path, plan["plan_sha256"], False)
            changed = root / "GLOBAL" / "README.md"
            changed.write_text("user changed after repair\n", encoding="utf-8")
            with self.assertRaisesRegex(
                recovery.RecoveryError, "post-repair user change"
            ):
                recovery.rollback(Path(result["run_manifest"]))

    def test_tree_walk_does_not_follow_external_link(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root, _ = self.make_foundation(Path(temp))
            external = Path(temp) / "external"
            external.mkdir()
            sentinel = external / "sentinel.txt"
            sentinel.write_text("KEEP", encoding="utf-8")
            link = root / "GLOBAL" / "obsidian-resource"
            try:
                recovery.create_link(
                    link, external, "junction" if os.name == "nt" else "symlink"
                )
            except (OSError, recovery.RecoveryError):
                self.skipTest("symlink creation not permitted")
            files, links = recovery.iter_tree(root)
            self.assertNotIn(sentinel, files)
            self.assertTrue(any(item["path"] == "GLOBAL/obsidian-resource" for item in links))
            self.assertEqual("KEEP", sentinel.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
