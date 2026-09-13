from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).with_name("foundation_update.py")
spec = importlib.util.spec_from_file_location("foundation_update", SCRIPT)
assert spec and spec.loader
update = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = update
spec.loader.exec_module(update)


class FoundationUpdateTests(unittest.TestCase):
    def fixture(self, base: Path) -> tuple[Path, Path]:
        root = base / "用户 Agent"
        global_root = root / "GLOBAL"
        skill = global_root / ".agents" / "skills" / "sample" / "SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text("old\n", encoding="utf-8", newline="\n")
        (global_root / "PROJECTS.md").write_text("用户项目\n", encoding="utf-8", newline="\n")
        (global_root / "GLOBAL_CONTEXT.md").write_text("用户规则\n", encoding="utf-8", newline="\n")
        (global_root / "FOUNDATION_STATE.json").write_text(
            json.dumps(
                {"general_assistant_project": "通用助手"},
                ensure_ascii=False,
                indent=2,
            ) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        source = base / "product"
        template = source / "template" / "GLOBAL"
        source_skill = template / ".agents" / "skills" / "sample" / "SKILL.md"
        source_skill.parent.mkdir(parents=True)
        agent_root_placeholder = chr(123) * 2 + "AGENT_ROOT" + chr(125) * 2
        source_skill.write_text(
            f"new {agent_root_placeholder}\n", encoding="utf-8", newline="\n"
        )
        (template / "PROJECTS.md").write_text("公开项目模板\n", encoding="utf-8", newline="\n")
        (template / "GLOBAL_CONTEXT.md").write_text("新版规则\n", encoding="utf-8", newline="\n")
        (template / "NEW.md").write_text("new file\n", encoding="utf-8", newline="\n")
        (source / "template-manifest.json").write_text("{}\n", encoding="utf-8", newline="\n")
        return root, source

    def test_plan_classifies_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root, source = self.fixture(Path(temp))
            plan = update.make_plan(root, source)
            self.assertIn("PROJECTS.md", [item["path"] for item in plan["preserved"]])
            self.assertIn("GLOBAL_CONTEXT.md", [item["path"] for item in plan["review_merge"]])
            self.assertEqual(
                {".agents/skills/sample/SKILL.md", "NEW.md"},
                {item["path"] for item in plan["actions"]},
            )

    def test_apply_preserves_user_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root, source = self.fixture(Path(temp))
            plan = update.make_plan(root, source)
            plan_path = Path(temp) / "plan.json"
            update.write_json(plan_path, plan)
            result = update.apply_plan(plan_path, plan["plan_sha256"])
            self.assertEqual("用户项目\n", (root / "GLOBAL" / "PROJECTS.md").read_text(encoding="utf-8"))
            self.assertIn(str(root), (root / "GLOBAL" / ".agents" / "skills" / "sample" / "SKILL.md").read_text(encoding="utf-8"))
            self.assertTrue((root / "GLOBAL" / "NEW.md").is_file())
            self.assertTrue(Path(result["run_manifest"]).is_file())

    def test_plan_change_blocks_apply(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root, source = self.fixture(Path(temp))
            plan = update.make_plan(root, source)
            plan_path = Path(temp) / "plan.json"
            update.write_json(plan_path, plan)
            target = root / "GLOBAL" / ".agents" / "skills" / "sample" / "SKILL.md"
            target.write_text("changed\n", encoding="utf-8")
            with self.assertRaises(update.UpdateError):
                update.apply_plan(plan_path, plan["plan_sha256"])

    def test_unresolved_placeholder_blocks_write(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root, source = self.fixture(Path(temp))
            file = source / "template" / "GLOBAL" / ".agents" / "skills" / "sample" / "SKILL.md"
            unknown_placeholder = chr(123) * 2 + "UNKNOWN" + chr(125) * 2 + "\n"
            file.write_text(unknown_placeholder, encoding="utf-8")
            self.assertTrue(update.make_plan(root, source)["blocking_issues"])

    def test_general_assistant_project_is_rendered_from_foundation_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root, source = self.fixture(Path(temp))
            file = source / "template" / "GLOBAL" / ".agents" / "skills" / "sample" / "SKILL.md"
            token = chr(123) * 2 + "GENERAL_ASSISTANT_PROJECT" + chr(125) * 2
            file.write_text(f"handoff to {token}\n", encoding="utf-8", newline="\n")
            plan = update.make_plan(root, source)
            self.assertFalse(plan["blocking_issues"])
            self.assertEqual(
                b"handoff to \xe9\x80\x9a\xe7\x94\xa8\xe5\x8a\xa9\xe6\x89\x8b\n",
                update.rendered_bytes(file, root),
            )

    def test_rollback_restores_replaced_and_removes_added(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root, source = self.fixture(Path(temp))
            plan = update.make_plan(root, source)
            plan_path = Path(temp) / "plan.json"
            update.write_json(plan_path, plan)
            result = update.apply_plan(plan_path, plan["plan_sha256"])
            update.rollback(Path(result["run_manifest"]))
            target = root / "GLOBAL" / ".agents" / "skills" / "sample" / "SKILL.md"
            self.assertEqual("old\n", target.read_text(encoding="utf-8"))
            self.assertFalse((root / "GLOBAL" / "NEW.md").exists())

    def test_apply_rejects_path_traversal_in_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root, source = self.fixture(Path(temp))
            plan = update.make_plan(root, source)
            plan["actions"][0]["path"] = "../outside.md"
            plan["plan_sha256"] = update.plan_digest(plan)
            plan_path = Path(temp) / "plan.json"
            update.write_json(plan_path, plan)
            with self.assertRaises(update.UpdateError):
                update.apply_plan(plan_path, plan["plan_sha256"])


if __name__ == "__main__":
    unittest.main()
