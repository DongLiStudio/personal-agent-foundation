from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(ROOT / "assets" / "wechat-cli"))
sys.path.insert(0, str(SCRIPTS))

import profile_store  # noqa: E402
import wechat_readonly  # noqa: E402
from wechat_cli.keys.common import save_results  # noqa: E402


class HardeningTests(unittest.TestCase):
    def test_profile_name_validation(self):
        self.assertEqual(profile_store.validate_profile_name("个人微信"), "个人微信")
        for bad in ("", "../bad", "a/b", "x\ny"):
            with self.assertRaises(ValueError):
                profile_store.validate_profile_name(bad)

    def test_limit_is_positive_without_privacy_ceiling(self):
        self.assertEqual(wechat_readonly.bounded_limit(200), 200)
        self.assertEqual(wechat_readonly.bounded_limit(100000), 100000)
        for bad in (0, -1):
            with self.assertRaises(ValueError):
                wechat_readonly.bounded_limit(bad)

    def test_key_catalog_validation(self):
        catalog = {"message/msg.db": {"enc_key": "ab" * 32, "salt": "cd" * 16, "size_mb": 1.0}}
        self.assertEqual(profile_store._validate_key_catalog(catalog)["message/msg.db"]["enc_key"], "ab" * 32)
        with self.assertRaises(ValueError):
            profile_store._validate_key_catalog({"../secret.db": catalog["message/msg.db"]})

    def test_offline_query_does_not_materialize_plaintext_key_file(self):
        wrapper = (ROOT / "scripts" / "wechat_readonly.py").read_text(encoding="utf-8")
        context = (ROOT / "assets" / "wechat-cli" / "wechat_cli" / "core" / "context.py").read_text(encoding="utf-8")
        self.assertNotIn("all_keys.json\").write_text", wrapper)
        self.assertIn("WECHAT_CLI_KEYS_STDIN", wrapper)
        self.assertIn("json.load(sys.stdin)", context)

    def test_key_capture_can_return_catalog_without_writing_file(self):
        salt = "cd" * 16
        key = "ab" * 32
        result = save_results(
            [("message/msg.db", "hidden", 4096, salt, b"")],
            {salt: ["message/msg.db"]},
            {salt: key},
            None,
            lambda _message: None,
        )
        self.assertEqual(result["message/msg.db"]["enc_key"], key)

    def test_history_sender_filter_and_summary(self):
        payload = {
            "messages": [
                "[2026-09-01 09:00:00] me: one",
                "[2026-09-01 09:01:00] other: two",
                "[2026-09-01 09:02:00] me: three",
            ]
        }
        filtered = wechat_readonly.filter_history_payload(payload, "me", True)
        self.assertEqual(filtered["source_count"], 3)
        self.assertEqual(filtered["count"], 2)
        self.assertEqual(filtered["messages"], [])
        self.assertTrue(filtered["summary_only"])

    def test_redaction(self):
        windows_home = "C:" + r"\Users\Alice\Documents\x"
        value = f"wxid_secret {windows_home} abcdef0123456789abcdef0123456789"
        redacted = wechat_readonly.redact_text(value, 500)
        self.assertNotIn("wxid_secret", redacted)
        self.assertNotIn("C:" + "\\Users", redacted)
        self.assertNotIn("abcdef0123456789abcdef0123456789", redacted)

    def test_cli_surface_has_no_export_or_mutation_commands(self):
        main = (ROOT / "assets" / "wechat-cli" / "wechat_cli" / "main.py").read_text(encoding="utf-8")
        self.assertNotIn("commands.export", main)
        self.assertNotIn("commands.new_messages", main)
        self.assertNotIn("commands.favorites", main)

    def test_windows_scanner_has_read_but_no_write_or_injection(self):
        scanner = (ROOT / "assets" / "wechat-cli" / "wechat_cli" / "keys" / "scanner_windows.py").read_text(encoding="utf-8")
        self.assertIn("ReadProcessMemory", scanner)
        for forbidden in ("WriteProcessMemory", "CreateRemoteThread", "VirtualAllocEx", "DebugActiveProcess"):
            self.assertNotIn(forbidden, scanner)

    def test_dpapi_round_trip(self):
        if sys.platform != "win32":
            self.skipTest("Windows-only")
        sample = b"profile-self-test"
        self.assertEqual(profile_store.unprotect(profile_store.protect(sample)), sample)


if __name__ == "__main__":
    unittest.main()
