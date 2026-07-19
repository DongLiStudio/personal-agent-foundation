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
            with self.assertRaisesRegex(guard.GuardError, "target directory is not empty"):
                guard.install(TEMPLATE, self.manifest, config, target)

    def test_existing_empty_target_directory_is_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            target = temp_path / "Agent"
            target.mkdir()
            config = self.write_values(temp_path, target)
            report, _ = guard.plan_install(TEMPLATE, self.manifest, config, target)
            self.assertEqual("will_use_empty_directory", report["target_status"])
            result = guard.install(TEMPLATE, self.manifest, config, target)
            self.assertTrue(result["verification"]["ok"])
            self.assertTrue((target / "GLOBAL" / "README.md").is_file())

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

    def test_existing_nonempty_target_is_never_merged(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "existing"
            target.mkdir()
            marker = target / "user-file.txt"
            marker.write_text("preserve", encoding="utf-8")
            config = self.write_values(Path(temp), target)
            with self.assertRaisesRegex(guard.GuardError, "target directory is not empty"):
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

    def test_obsidian_contract_does_not_assume_author_layout(self) -> None:
        contract = (TEMPLATE / "GLOBAL" / "OBSIDIAN_LINK.md").read_text(
            encoding="utf-8"
        )
        for author_path in (
            "信息\\README-信息.md",
            "资源\\README-资源.md",
            "想法\\README-想法.md",
            "特殊\\README-特殊.md",
            "想法\\发展\\优先要做的重点项目.md",
            "知识\\方法论\\方法论路由：方法论的方法论.md",
        ):
            self.assertNotIn(author_path, contract)
        for text in (
            "Obsidian Vault Link",
            "个人 Obsidian 库入口",
            "{{AGENT_ROOT}}\\GLOBAL\\obsidian-resource",
            "## 安全规则",
            "## 目录理解",
            "## 优先阅读",
            "## 未配置判定",
            "仅仅创建 `obsidian-resource` 软连接/Junction 不等于配置完成",
        ):
            self.assertIn(text, contract)
        self.assertNotIn("{{OBSIDIAN_VAULT_PATH}}", contract)
        self.assertNotIn("Vault：", contract)

    def test_obsidian_connection_requires_structure_before_completion(self) -> None:
        installer = (
            ROOT / "skills" / "install-agent-scaffold" / "SKILL.md"
        ).read_text(encoding="utf-8")
        workflow = (
            ROOT
            / "skills"
            / "install-agent-scaffold"
            / "references"
            / "installation-workflow.md"
        ).read_text(encoding="utf-8")
        obsidian_layout = (
            ROOT
            / "skills"
            / "install-agent-scaffold"
            / "references"
            / "obsidian-layout.md"
        ).read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        contract = (ROOT / "docs" / "installation-contract.md").read_text(
            encoding="utf-8"
        )
        manifest = MANIFEST_PATH.read_text(encoding="utf-8")
        combined = "\n".join([installer, workflow, obsidian_layout, readme, contract])
        for text in (
            "不能只询问软连接路径",
            "基础结构",
            "目录理解",
            "优先阅读入口",
            "只读列出 Vault 根目录一层",
            "与模板整体结构同构",
            "不记录 Vault 原始绝对路径",
            "不得长期写入 `GLOBAL/OBSIDIAN_LINK.md`",
            "只创建 `GLOBAL/obsidian-resource` 软连接/Junction 不构成 Obsidian 配置完成",
            "只有用户明确说“之后再定”",
        ):
            self.assertIn(text, combined)
        self.assertNotIn("OBSIDIAN_VAULT_PATH", manifest)

    def test_onboarding_bundles_full_host_personalization_prompt(self) -> None:
        host_integration = (
            ROOT
            / "skills"
            / "install-agent-scaffold"
            / "references"
            / "host-integration.md"
        ).read_text(encoding="utf-8")
        required_text = (
            "开始任何项目工作前，必须完整读取当前项目根目录的 "
            "AGENTS.md、README.md 和 STATUS.md",
            "项目实时文件优先于历史对话、摘要和旧记录",
            "发生会话压缩、任务迁移、跨任务委派、长期岗位接单或项目归属变化后",
            "未回报不得视为完成。已有明确决定不得重复询问。",
        )
        for text in required_text:
            self.assertIn(text, host_integration)

    def test_installer_requires_explicit_connector_choices(self) -> None:
        installer = (
            ROOT / "skills" / "install-agent-scaffold" / "SKILL.md"
        ).read_text(encoding="utf-8")
        workflow = (
            ROOT
            / "skills"
            / "install-agent-scaffold"
            / "references"
            / "installation-workflow.md"
        ).read_text(encoding="utf-8")
        combined = installer + "\n" + workflow
        for text in (
            "不得把飞书、GitHub 或 Obsidian 静默设为“未配置”",
            "是否现在连接飞书",
            "是否现在连接 GitHub",
            "是否现在连接 Obsidian",
            "默认推荐和预选项应为“现在连接”",
        ):
            self.assertIn(text, combined)

    def test_installer_defers_identity_names_until_tools_can_authorize(self) -> None:
        installer = (
            ROOT / "skills" / "install-agent-scaffold" / "SKILL.md"
        ).read_text(encoding="utf-8")
        workflow = (
            ROOT
            / "skills"
            / "install-agent-scaffold"
            / "references"
            / "installation-workflow.md"
        ).read_text(encoding="utf-8")
        contract = (ROOT / "docs" / "installation-contract.md").read_text(
            encoding="utf-8"
        )
        combined = installer + "\n" + workflow + "\n" + contract
        for text in (
            "初始安装阶段不得询问用户飞书 Profile 名、GitHub 账号名或 Obsidian Vault 路径",
            "先安装 GLOBAL 和 Skills",
            "不要向用户询问“Profile 名是什么”作为前置条件",
            "不要向用户询问“GitHub 用户名是什么”作为前置条件",
            "飞书、GitHub 和 Obsidian 不属于初始模板渲染输入",
        ):
            self.assertIn(text, combined)
        self.assertNotIn("用户选择连接时再收集默认 Profile 名", combined)
        self.assertNotIn("用户选择连接时再收集默认账号", combined)

    def test_connectors_default_to_connect_now_after_skill_restore(self) -> None:
        installer = (
            ROOT / "skills" / "install-agent-scaffold" / "SKILL.md"
        ).read_text(encoding="utf-8")
        workflow = (
            ROOT
            / "skills"
            / "install-agent-scaffold"
            / "references"
            / "installation-workflow.md"
        ).read_text(encoding="utf-8")
        host_integration = (
            ROOT
            / "skills"
            / "install-agent-scaffold"
            / "references"
            / "host-integration.md"
        ).read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        contract = (ROOT / "docs" / "installation-contract.md").read_text(
            encoding="utf-8"
        )
        combined = "\n".join(
            [installer, workflow, host_integration, readme, contract]
        )
        for text in (
            "默认推荐和预选项均为“现在连接”",
            "默认推荐和预选项必须是“现在连接”",
            "三个连接项的默认选项都应是“现在连接”",
            "默认选项必须是“现在连接”",
            "用户主动选择稍后再配时才保留未配置说明",
        ):
            self.assertIn(text, combined)

    def test_feishu_connection_defaults_to_new_dedicated_profile(self) -> None:
        installer = (
            ROOT / "skills" / "install-agent-scaffold" / "SKILL.md"
        ).read_text(encoding="utf-8")
        workflow = (
            ROOT
            / "skills"
            / "install-agent-scaffold"
            / "references"
            / "installation-workflow.md"
        ).read_text(encoding="utf-8")
        contract = (ROOT / "docs" / "installation-contract.md").read_text(
            encoding="utf-8"
        )
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        lark_profiles = (TEMPLATE / "GLOBAL" / "LARK_PROFILES.md").read_text(
            encoding="utf-8"
        )
        combined = "\n".join([installer, workflow, contract, readme, lark_profiles])
        for text in (
            "默认创建新的飞书应用",
            "新的专用 Profile",
            "不得自动复用本机已有 Profile",
            "active Profile",
            "已有 Profile 只用于只读冲突检查",
            "用户明确选择高级迁移/共用",
            "共享权限、身份路由和审计边界",
            "若建议名称已存在",
        ):
            self.assertIn(text, combined)
        self.assertNotIn("默认复用本机已有 Profile", combined)
        self.assertNotIn("自动复用 active Profile", combined)

    def test_identity_records_use_authoritative_provider_names(self) -> None:
        installer = (
            ROOT / "skills" / "install-agent-scaffold" / "SKILL.md"
        ).read_text(encoding="utf-8")
        workflow = (
            ROOT
            / "skills"
            / "install-agent-scaffold"
            / "references"
            / "installation-workflow.md"
        ).read_text(encoding="utf-8")
        contract = (ROOT / "docs" / "installation-contract.md").read_text(
            encoding="utf-8"
        )
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        lark_profiles = (TEMPLATE / "GLOBAL" / "LARK_PROFILES.md").read_text(
            encoding="utf-8"
        )
        github_accounts = (TEMPLATE / "GLOBAL" / "GITHUB_ACCOUNTS.md").read_text(
            encoding="utf-8"
        )
        combined = "\n".join(
            [installer, workflow, contract, readme, lark_profiles, github_accounts]
        )
        for text in (
            "公司列表标题和公司名称",
            "真实公司/租户名称",
            "CLI profile 名只",
            "不得使用程序自拟",
            "账号列表标题、username 和切换命令",
            "gh api user --jq '.login'",
            "真实 login",
            "Display name",
            "不得替代 username/login",
        ):
            self.assertIn(text, combined)
        self.assertNotIn("程序自拟账号名称", github_accounts)
        self.assertNotIn("默认组织（安装时配置）", lark_profiles)
        self.assertNotIn("默认账号（安装时配置）", github_accounts)

    def test_visual_install_panel_is_a_gate_when_host_supports_it(self) -> None:
        host_integration = (
            ROOT
            / "skills"
            / "install-agent-scaffold"
            / "references"
            / "host-integration.md"
        ).read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        combined = host_integration + "\n" + readme
        for text in (
            "任何宿主支持可视化安装面板",
            "当前宿主可用时必须优先尝试可视化安装面板或确认摘要",
            "例如 Codex 中可能表现为 `Visualize` 插件/能力",
            "不要把某个宿主或插件名称当作唯一实现",
            "必须先尝试",
            "本次安装不得直接继续收集配置",
            "图形交互未使用",
        ):
            self.assertIn(text, combined)

    def test_installer_documents_agent_root_and_empty_target_policy(self) -> None:
        installer = (
            ROOT / "skills" / "install-agent-scaffold" / "SKILL.md"
        ).read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        contract = (ROOT / "docs" / "installation-contract.md").read_text(
            encoding="utf-8"
        )
        combined = installer + "\n" + readme + "\n" + contract
        for text in (
            "默认推荐的 Agent 根目录最终文件夹名为 `Agent`",
            "目标不存在时创建",
            "目标已存在且为空时",
            "目标已有内容时",
            "不得合并、覆盖或删除用户文件",
        ):
            self.assertIn(text, combined)

    def test_onboarding_guides_first_project_and_global_skill_smoke_tests(self) -> None:
        onboarding = (
            ROOT
            / "skills"
            / "install-agent-scaffold"
            / "references"
            / "onboarding.md"
        ).read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        combined = onboarding + "\n" + readme
        for text in (
            "创建第一个项目目录",
            "打开目录、添加项目或导入工作区",
            "GLOBAL Skill 快速试用",
            "已可用、需要授权、待安装外部依赖、当前宿主不支持",
            "不要把“源稿存在”等同于“宿主已经可调用”",
        ):
            self.assertIn(text, combined)

    def test_onboarding_teaches_global_files_interactively(self) -> None:
        onboarding = (
            ROOT
            / "skills"
            / "install-agent-scaffold"
            / "references"
            / "onboarding.md"
        ).read_text(encoding="utf-8")
        for text in (
            "GLOBAL 文件导览",
            "先列出 `GLOBAL` 根目录中的文件和关键目录",
            "它是什么、为什么这样设计、什么时候要看",
            "你想先了解哪个",
            "一个一个讲",
            "README.md",
            "GLOBAL_CONTEXT.md",
            "PROJECTS.md",
            "OBSIDIAN_LINK.md",
            "SKILL_DEPENDENCIES.md",
            "LARK_PROFILES.md",
            "GITHUB_ACCOUNTS.md",
            "SCHEDULE_PREFERENCES.md",
            ".agents/skills/",
            "项目目录与 `GLOBAL` 同级",
            "GLOBAL 导览完成前，不要直接跳到“安装成功”",
        ):
            self.assertIn(text, onboarding)

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
