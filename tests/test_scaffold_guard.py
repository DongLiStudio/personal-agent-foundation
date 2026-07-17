from __future__ import annotations

from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "template"
MANIFEST_PATH = ROOT / "template-manifest.json"
SCRIPT = ROOT / "skills" / "install-agent-scaffold" / "scripts" / "scaffold_guard.py"

spec = importlib.util.spec_from_file_location("scaffold_guard", SCRIPT)
assert spec and spec.loader
guard = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = guard
spec.loader.exec_module(guard)


def tree_hash(root: Path) -> str:
    value = sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        value.update(path.relative_to(root).as_posix().encode("utf-8"))
        value.update(path.read_bytes())
    return value.hexdigest()


def values(target: Path) -> dict[str, str]:
    return {
        "AGENT_ROOT": str(target.resolve()),
        "DEFAULT_LARK_PROFILE": "example-default-profile",
        "DEFAULT_GITHUB_ACCOUNT": "example-user",
        "DEFAULT_TIMEZONE": "Asia/Shanghai",
        "GENERAL_ASSISTANT_PROJECT": "示例通用助手",
        "OBSIDIAN_VAULT_PATH": "未配置（首次连接 Obsidian 时设置）",
    }


class ScaffoldGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = guard.load_json(MANIFEST_PATH)

    def write_values(self, directory: Path, target: Path) -> Path:
        path = directory / "values.json"
        path.write_text(json.dumps(values(target), ensure_ascii=False), encoding="utf-8")
        return path

    def test_full_template_inventory_and_placeholders(self) -> None:
        report = guard.audit_template(TEMPLATE, self.manifest)
        self.assertEqual(56, report["file_count"])
        self.assertEqual(
            {
                "AGENT_ROOT",
                "DEFAULT_GITHUB_ACCOUNT",
                "DEFAULT_LARK_PROFILE",
                "DEFAULT_TIMEZONE",
                "GENERAL_ASSISTANT_PROJECT",
                "OBSIDIAN_VAULT_PATH",
            },
            set(report["placeholders"]),
        )

    def test_plan_is_write_free_and_supports_unicode_space_path(self) -> None:
        before = tree_hash(TEMPLATE)
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            target = temp_path / "中文 Agent Root"
            config = self.write_values(temp_path, target)
            report, rendered = guard.plan_install(
                TEMPLATE, self.manifest, config, target
            )
            self.assertEqual("dry-run", report["mode"])
            self.assertEqual(56, report["file_count"])
            self.assertFalse(target.exists())
            self.assertTrue(all(b"{{" not in content for _, content in rendered))
        self.assertEqual(before, tree_hash(TEMPLATE))

    def test_install_verifies_and_second_install_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            target = temp_path / "Agent Root"
            config = self.write_values(temp_path, target)
            result = guard.install(TEMPLATE, self.manifest, config, target)
            self.assertTrue(result["verification"]["ok"])
            self.assertTrue((target / "GLOBAL" / "README.md").is_file())
            with self.assertRaisesRegex(guard.GuardError, "target already exists"):
                guard.install(TEMPLATE, self.manifest, config, target)

    def test_rendered_global_skill_test_suites_pass(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            target = temp_path / "中文 Agent Root"
            config = self.write_values(temp_path, target)
            guard.install(TEMPLATE, self.manifest, config, target)
            test_files = sorted(
                (target / "GLOBAL" / ".agents" / "skills").rglob("test_*.py")
            )
            self.assertGreaterEqual(len(test_files), 5)
            for test_file in test_files:
                with self.subTest(test_file=test_file):
                    completed = subprocess.run(
                        [sys.executable, str(test_file)],
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        env={
                            **os.environ,
                            "PYTHONIOENCODING": "utf-8",
                            "PYTHONUTF8": "1",
                        },
                    )
                    self.assertEqual(
                        0,
                        completed.returncode,
                        completed.stdout + completed.stderr,
                    )

    def test_existing_target_is_never_merged(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "existing"
            target.mkdir()
            marker = target / "user-file.txt"
            marker.write_text("preserve", encoding="utf-8")
            config = self.write_values(Path(temp), target)
            with self.assertRaisesRegex(guard.GuardError, "target already exists"):
                guard.plan_install(TEMPLATE, self.manifest, config, target)
            self.assertEqual("preserve", marker.read_text(encoding="utf-8"))

    def test_unknown_placeholder_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            copied = Path(temp) / "template"
            shutil.copytree(TEMPLATE, copied)
            readme = copied / "GLOBAL" / "README.md"
            readme.write_text(
                readme.read_text(encoding="utf-8") + "\n{{UNKNOWN_VALUE}}\n",
                encoding="utf-8",
                newline="\n",
            )
            with self.assertRaisesRegex(guard.GuardError, "UNKNOWN_VALUE"):
                guard.audit_template(copied, self.manifest)

    def test_bom_and_crlf_are_blocked(self) -> None:
        for payload, message in (
            (b"\xef\xbb\xbftext\n", "BOM"),
            (b"text\r\n", "LF line endings"),
        ):
            with self.subTest(message=message), tempfile.TemporaryDirectory() as temp:
                copied = Path(temp) / "template"
                shutil.copytree(TEMPLATE, copied)
                (copied / "GLOBAL" / "README.md").write_bytes(payload)
                with self.assertRaisesRegex(guard.GuardError, message):
                    guard.audit_template(copied, self.manifest)

    def test_cli_emits_utf8_json_with_chinese_path(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "audit-template",
                "--template",
                str(TEMPLATE),
                "--manifest",
                str(MANIFEST_PATH),
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        report = json.loads(completed.stdout)
        self.assertEqual(str(TEMPLATE.resolve()), report["template"])


class ProductBoundaryTests(unittest.TestCase):
    def test_product_is_not_an_agent_management_project(self) -> None:
        for forbidden in ("AGENTS.md", "STATUS.md", "tasks", "archive"):
            self.assertFalse((ROOT / forbidden).exists(), forbidden)

    def test_template_contains_no_runtime_artifacts(self) -> None:
        forbidden_names = {"__pycache__", ".pytest_cache"}
        for path in TEMPLATE.rglob("*"):
            self.assertNotIn(path.name, forbidden_names, str(path))
            self.assertNotEqual(".pyc", path.suffix.lower(), str(path))

    def test_public_template_has_no_known_personal_identifiers(self) -> None:
        forbidden_patterns = (
            re.compile(r"[A-Za-z]:\\(?:Users|Project)\\", re.IGNORECASE),
            re.compile(r"cli_[a-f0-9]{12,}", re.IGNORECASE),
            re.compile(r"[\w.+-]+@(?!(?:example\.invalid)\b)[\w.-]+\.[A-Za-z]{2,}"),
        )
        for path in (item for item in TEMPLATE.rglob("*") if item.is_file()):
            text = path.read_text(encoding="utf-8")
            for pattern in forbidden_patterns:
                self.assertIsNone(pattern.search(text), f"{pattern.pattern} in {path}")

    def test_all_product_text_is_utf8_without_bom_and_lf(self) -> None:
        text_suffixes = {"", ".md", ".json", ".yaml", ".yml", ".py", ".txt"}
        for path in (item for item in ROOT.rglob("*") if item.is_file()):
            if ".git" in path.parts or path.suffix.lower() not in text_suffixes:
                continue
            raw = path.read_bytes()
            self.assertFalse(raw.startswith(b"\xef\xbb\xbf"), str(path))
            raw.decode("utf-8")
            self.assertNotIn(b"\r", raw, str(path))


if __name__ == "__main__":
    unittest.main()
