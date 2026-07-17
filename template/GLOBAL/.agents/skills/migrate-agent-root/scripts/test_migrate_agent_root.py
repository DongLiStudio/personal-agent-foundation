#!/usr/bin/env python3
"""Fixture tests for migrate_agent_root.py. Uses only temporary directories."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


SCRIPT = Path(__file__).with_name("migrate_agent_root.py")
ALIGN_SCRIPT = SCRIPT.parents[2] / "align-agent-projects-with-global" / "scripts" / "align_agent_projects.py"


def run_cmd(args: list[str], expect: int = 0, script: Path = SCRIPT) -> subprocess.CompletedProcess[str]:
    result = subprocess.run([sys.executable, str(script), *args], text=True, capture_output=True, encoding="utf-8", errors="replace")
    if result.returncode != expect:
        raise AssertionError(f"expected {expect}, got {result.returncode}\nSTDOUT={result.stdout}\nSTDERR={result.stderr}")
    return result


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def load_manifest(report: Path) -> dict[str, object]:
    return json.loads((report / "migration-manifest.json").read_text(encoding="utf-8"))


def make_basic_fixture(base: Path) -> tuple[Path, Path]:
    source = base / "旧 Agent 根"
    destination = base / "新 Agent 根"
    project = source / "通用 助手"
    write(source / "GLOBAL" / "README.md", f"GLOBAL at {source}\\GLOBAL and {str(source).replace(os.sep, '/')}/GLOBAL\n")
    write(source / "GLOBAL" / "PROJECTS.md", f"# 项目索引\n\n## 活跃项目\n\n- {{GENERAL_ASSISTANT_PROJECT}}： `{project}` - fixture project\n")
    write(source / "GLOBAL" / ".agents" / "skills" / "demo" / "SKILL.md", f"source: {source}\n")
    write(project / "README.md", f"project root {project}\n")
    write(project / "STATUS.md", "fixture state\n")
    write(source / "binary.bin", "\x00\x01not a text rewrite")
    return source, destination


def make_align_report(path: Path, status: str = "aligned") -> None:
    write(path, json.dumps({"projects": [{"name": "{{GENERAL_ASSISTANT_PROJECT}}", "status": status}]}, ensure_ascii=False))


def make_junction(link: Path, target: Path) -> bool:
    if os.name != "nt":
        try:
            os.symlink(target, link, target_is_directory=True)
            return True
        except OSError:
            return False
    result = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], text=True, capture_output=True, encoding="utf-8", errors="replace")
    return result.returncode == 0


def test_plan_execute_verify_and_gate() -> None:
    with tempfile.TemporaryDirectory(prefix="migrate-agent-root-") as tmp:
        base = Path(tmp)
        source, destination = make_basic_fixture(base)
        report = base / "report"

        project = source / "通用 助手"
        subprocess.run(["git", "-C", str(project), "init"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(project), "add", "."], check=True, capture_output=True)
        subprocess.run([
            "git", "-C", str(project), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
            "commit", "-m", "fixture baseline",
        ], check=True, capture_output=True)

        run_cmd(["plan", "--source", str(source), "--destination", str(destination), "--report", str(report)])
        plan = load_manifest(report)
        assert plan["status"] == "planned"
        assert plan["summary"]["rewrite_files"] >= 2

        nonempty = base / "非空 target"
        nonempty.mkdir()
        write(nonempty / "keep.txt", "x")
        run_cmd(["plan", "--source", str(source), "--destination", str(nonempty), "--report", str(base / "blocked")], expect=1)

        run_cmd(["execute", "--source", str(source), "--destination", str(destination), "--report", str(report)])
        assert (destination / "GLOBAL" / "README.md").exists()
        assert str(source) not in (destination / "GLOBAL" / "README.md").read_text(encoding="utf-8")

        align_migrated = base / "align-migrated.json"
        run_cmd([
            "audit", "--global-root", str(destination / "GLOBAL"), "--old-root", str(source),
            "--global-change-summary", "fixture root migration", "--report", str(align_migrated),
            "--accept-migration-rewrites", "--fail-on-attention",
        ], script=ALIGN_SCRIPT)
        aligned_payload = json.loads(align_migrated.read_text(encoding="utf-8"))
        assert aligned_payload["projects"][0]["checks"]["migration_rewrite_dirty"]["accepted"] is True

        align_pass = base / "align-pass.json"
        make_align_report(align_pass, "aligned")
        run_cmd(["verify", "--source", str(source), "--destination", str(destination), "--report", str(report), "--align-report", str(align_pass), "--require-align-pass"])

        align_fail = base / "align-fail.json"
        make_align_report(align_fail, "blocked")
        run_cmd(["verify", "--source", str(source), "--destination", str(destination), "--report", str(base / "fail"), "--align-report", str(align_fail), "--require-align-pass"], expect=1)

        run_cmd(["execute", "--source", str(source), "--destination", str(destination), "--report", str(base / "again")], expect=1)


def test_hash_tamper_and_encoding_lf_block_verify() -> None:
    with tempfile.TemporaryDirectory(prefix="migrate-agent-root-hash-") as tmp:
        base = Path(tmp)
        source, destination = make_basic_fixture(base)
        run_cmd(["execute", "--source", str(source), "--destination", str(destination), "--report", str(base / "report")])

        (destination / "binary.bin").write_bytes(b"tampered")
        run_cmd(["verify", "--source", str(source), "--destination", str(destination), "--report", str(base / "tampered")], expect=1)
        tampered = load_manifest(base / "tampered")
        assert tampered["verification"]["hash_mismatches"]
        assert not tampered["verification"]["binary_old_root_hits"]

        (destination / "binary.bin").write_bytes(str(source).encode("utf-8"))
        run_cmd(["verify", "--source", str(source), "--destination", str(destination), "--report", str(base / "binary-old")], expect=1)
        binary_old = load_manifest(base / "binary-old")
        assert binary_old["verification"]["binary_old_root_hits"]

        (destination / "binary.bin").write_bytes((source / "binary.bin").read_bytes())
        (destination / "GLOBAL" / "PROJECTS.md").write_bytes(b"\xef\xbb\xbfline\r\n")
        run_cmd(["verify", "--source", str(source), "--destination", str(destination), "--report", str(base / "encoding")], expect=1)
        encoding = load_manifest(base / "encoding")
        assert encoding["verification"]["encoding_or_lf_issues"]


def test_align_report_bom_and_bad_json() -> None:
    with tempfile.TemporaryDirectory(prefix="migrate-agent-root-align-") as tmp:
        base = Path(tmp)
        source, destination = make_basic_fixture(base)
        run_cmd(["execute", "--source", str(source), "--destination", str(destination), "--report", str(base / "report")])

        bom_align = base / "bom-align.json"
        bom_align.write_bytes(b"\xef\xbb\xbf" + json.dumps({"projects": [{"name": "x", "status": "aligned"}]}).encode("utf-8"))
        run_cmd(["verify", "--source", str(source), "--destination", str(destination), "--report", str(base / "bom"), "--align-report", str(bom_align), "--require-align-pass"])

        bad_align = base / "bad-align.json"
        bad_align.write_text("{bad", encoding="utf-8")
        run_cmd(["verify", "--source", str(source), "--destination", str(destination), "--report", str(base / "bad"), "--align-report", str(bad_align), "--require-align-pass"], expect=1)
        bad = load_manifest(base / "bad")
        assert bad["verification"]["alignment_gate"]["error"]


def test_links_rebuild_or_clean_failure() -> None:
    with tempfile.TemporaryDirectory(prefix="migrate-agent-root-link-") as tmp:
        base = Path(tmp)
        source, destination = make_basic_fixture(base)
        external = base / "外部 Vault"
        external.mkdir()
        external_link = source / "GLOBAL" / "obsidian-resource"
        internal_link = source / "GLOBAL" / "internal-project-link"
        external_ok = make_junction(external_link, external)
        internal_ok = make_junction(internal_link, source / "通用 助手")
        if not (external_ok or internal_ok):
            return

        run_cmd(["plan", "--source", str(source), "--destination", str(destination), "--report", str(base / "plan")])
        plan = load_manifest(base / "plan")
        assert plan["copy_plan"]["links"]
        if internal_ok:
            assert any(link.get("internal_to_source") for link in plan["copy_plan"]["links"])

        run_cmd(["execute", "--source", str(source), "--destination", str(destination), "--report", str(base / "execute")])
        execute = load_manifest(base / "execute")
        assert execute["verification"]["link_rebuild_results"]
        assert all(result["status"] == "rebuilt" for result in execute["verification"]["link_rebuild_results"])
        assert (destination / "GLOBAL" / "obsidian-resource").exists() or (destination / "GLOBAL" / "internal-project-link").exists()


def test_source_and_destination_parent_junction_block() -> None:
    with tempfile.TemporaryDirectory(prefix="migrate-agent-root-boundary-") as tmp:
        base = Path(tmp)
        real_source, _destination = make_basic_fixture(base / "real")
        source_link = base / "source-junction"
        if make_junction(source_link, real_source):
            run_cmd(["plan", "--source", str(source_link), "--destination", str(base / "new-root"), "--report", str(base / "source-block")], expect=1)

        source, _destination = make_basic_fixture(base / "dest-parent")
        parent_target = base / "real-destination-parent"
        parent_target.mkdir()
        parent_link = base / "destination-parent-junction"
        if make_junction(parent_link, parent_target):
            run_cmd(["plan", "--source", str(source), "--destination", str(parent_link / "new-root"), "--report", str(base / "dest-block")], expect=1)


def test_nested_git_dirty_recorded() -> None:
    with tempfile.TemporaryDirectory(prefix="migrate-agent-root-git-") as tmp:
        base = Path(tmp)
        source, destination = make_basic_fixture(base)
        repo = source / "通用 助手"
        subprocess.run(["git", "-C", str(repo), "init"], text=True, capture_output=True, encoding="utf-8", errors="replace", check=True)
        write(repo / "dirty.txt", "dirty\n")
        run_cmd(["plan", "--source", str(source), "--destination", str(destination), "--report", str(base / "plan")])
        plan = load_manifest(base / "plan")
        assert "通用 助手" in plan["git_repositories"]
        assert plan["verification"]["git_status"][0]["dirty"] is True


def test_regenerable_outputs_are_audited_and_excluded() -> None:
    with tempfile.TemporaryDirectory(prefix="migrate-agent-root-generated-") as tmp:
        base = Path(tmp)
        source, destination = make_basic_fixture(base)
        project = source / "通用 助手"
        generated = {
            project / "node_modules" / "pkg" / "index.js": str(source),
            project / "dist" / "assets" / "bundle.js": "to" + "ken='generated-placeholder-token'\r\n",
            project / "src-tauri" / "target" / "debug" / "metadata.bin": str(source),
            project / "src-tauri" / "target-next" / "release" / "asset.js": "generated\r\n",
        }
        for path, text in generated.items():
            write(path, text)

        report = base / "report"
        run_cmd(["plan", "--source", str(source), "--destination", str(destination), "--report", str(report)])
        plan = load_manifest(report)
        skipped = plan["copy_plan"]["skipped"]
        skipped_paths = {item["path"] for item in skipped}
        assert "通用 助手/node_modules" in skipped_paths
        assert "通用 助手/dist" in skipped_paths
        assert "通用 助手/src-tauri/target" in skipped_paths
        assert "通用 助手/src-tauri/target-next" in skipped_paths
        assert plan["summary"]["skipped_files"] == 4
        assert plan["summary"]["skipped_bytes"] > 0

        run_cmd(["execute", "--source", str(source), "--destination", str(destination), "--report", str(report)])
        for path in generated:
            assert not (destination / path.relative_to(source)).exists()
        execute = load_manifest(report)
        assert not execute["verification"]["binary_old_root_hits"]
        assert not execute["verification"]["encoding_or_lf_issues"]
        assert not execute["verification"]["secret_like_hits"]


def test_failed_staging_verification_is_cleaned() -> None:
    with tempfile.TemporaryDirectory(prefix="migrate-agent-root-cleanup-") as tmp:
        base = Path(tmp)
        source, destination = make_basic_fixture(base)
        secret_fixture = "to" + "ken=" + "fixture-secret-value\n"
        write(source / "通用 助手" / "unsafe.md", secret_fixture)
        report = base / "report"
        run_cmd(["execute", "--source", str(source), "--destination", str(destination), "--report", str(report)], expect=1)
        manifest = load_manifest(report)
        assert manifest["status"] == "blocked"
        assert manifest["verification"]["secret_like_hits"] == ["通用 助手/unsafe.md"]
        assert not destination.exists()
        assert not list(destination.parent.glob(f".{destination.name}.staging-*"))


def test_align_empty_projects_and_junction_block() -> None:
    with tempfile.TemporaryDirectory(prefix="align-agent-projects-") as tmp:
        base = Path(tmp)
        global_root = base / "GLOBAL"
        global_root.mkdir()
        write(global_root / "README.md", "# GLOBAL\n")
        write(global_root / "GLOBAL_CONTEXT.md", "GLOBAL rule `DYNAMIC_GATE_X` must apply.\n")
        write(global_root / "PROJECTS.md", "# empty\n")
        run_cmd(["audit", "--global-root", str(global_root), "--report", str(base / "empty.json"), "--fail-on-attention"], expect=1, script=ALIGN_SCRIPT)
        run_cmd(["audit", "--global-root", str(global_root), "--report", str(base / "empty-ok.json"), "--fail-on-attention", "--allow-empty-projects"], script=ALIGN_SCRIPT)

        target = base / "real project"
        target.mkdir()
        write(target / "README.md", "DYNAMIC_GATE_X\n")
        project_root = base / "junction project"
        if make_junction(project_root, target):
            write(global_root / "PROJECTS.md", f"# 项目索引\n\n## 活跃项目\n\n- demo： `{project_root}` - junction\n")
            run_cmd(["audit", "--global-root", str(global_root), "--report", str(base / "junction.json"), "--fail-on-attention"], expect=1, script=ALIGN_SCRIPT)
            payload = json.loads((base / "junction.json").read_text(encoding="utf-8"))
            assert payload["projects"][0]["status"] == "blocked"

        global_target = base / "real-global"
        global_target.mkdir()
        write(global_target / "PROJECTS.md", "# empty\n")
        global_link = base / "global-junction"
        if make_junction(global_link, global_target):
            run_cmd(["audit", "--global-root", str(global_link), "--report", str(base / "global-junction.json")], expect=2, script=ALIGN_SCRIPT)


if __name__ == "__main__":
    test_plan_execute_verify_and_gate()
    test_hash_tamper_and_encoding_lf_block_verify()
    test_align_report_bom_and_bad_json()
    test_links_rebuild_or_clean_failure()
    test_source_and_destination_parent_junction_block()
    test_nested_git_dirty_recorded()
    test_regenerable_outputs_are_audited_and_excluded()
    test_failed_staging_verification_is_cleaned()
    test_align_empty_projects_and_junction_block()
    print("fixture tests passed")
