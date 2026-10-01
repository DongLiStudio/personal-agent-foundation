from __future__ import annotations

import importlib.util
import json
import argparse
import contextlib
import io
import sys
import tempfile
import unittest
from datetime import datetime
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
    def test_date_normalization_and_key_error_classification(self):
        self.assertEqual(wechat_readonly.normalize_time("2026-08-30"), "2026-08-30")
        self.assertEqual(wechat_readonly.normalize_time("2026-08-30 09:10"), "2026-08-30 09:10")
        expected = datetime.fromisoformat("2026-08-30T09:10:00+08:00").astimezone().strftime("%Y-%m-%d %H:%M:%S")
        self.assertEqual(wechat_readonly.normalize_time("2026-08-30T09:10:00+08:00"), expected)
        with self.assertRaises(ValueError):
            wechat_readonly.normalize_time("not-a-date")
        self.assertFalse(wechat_readonly.key_failure("start_time 格式无效"))
        self.assertFalse(wechat_readonly.key_failure("找不到聊天对象"))
        self.assertTrue(wechat_readonly.key_failure("database decryption failed"))

    def test_existing_catalog_query_error_never_refreshes_without_key_evidence(self):
        args = argparse.Namespace(profile="个人微信", command="history", chat="test", limit=2, offset=0,
                                  start_time="2026-08-30T00:00:00+08:00", end_time="", message_type="",
                                  sender="", summary_only=False, max_chars=240, refresh_key_catalog=False)
        catalog = {"message/msg.db": {"enc_key": "ab" * 32, "salt": "cd" * 16}}
        with tempfile.TemporaryDirectory() as temp, mock.patch.object(wechat_readonly, "parse_args", return_value=args), \
             mock.patch.object(wechat_readonly.platform, "system", return_value="Windows"), \
             mock.patch.object(wechat_readonly, "CLI", Path(sys.executable)), \
             mock.patch.object(wechat_readonly, "RUNTIME_ROOT", Path(temp)), \
             mock.patch.object(wechat_readonly, "resolve", return_value=Path(temp)), \
             mock.patch.object(wechat_readonly, "has_standing_read_authorization", return_value=True), \
             mock.patch.object(wechat_readonly, "get_key_catalog", return_value=catalog), \
             mock.patch.object(wechat_readonly, "extract_keys") as capture, \
             mock.patch.object(wechat_readonly, "invoke", return_value=mock.Mock(returncode=2, stderr="start_time 格式无效")) as invoke:
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(wechat_readonly.main(), 4)
            self.assertIn('"ok": false', output.getvalue())
            self.assertNotIn("key refresh", output.getvalue())
            expected = datetime.fromisoformat("2026-08-30T00:00:00+08:00").astimezone().strftime("%Y-%m-%d %H:%M:%S")
            self.assertIn(expected, invoke.call_args.args[1])
            capture.assert_not_called()

    def test_missing_catalog_uses_standing_grant_and_only_stores_after_success(self):
        args = argparse.Namespace(profile="个人微信", command="sessions", limit=1, max_chars=240,
                                  refresh_key_catalog=False)
        catalog = {"message/msg.db": {"enc_key": "ab" * 32, "salt": "cd" * 16}}
        with tempfile.TemporaryDirectory() as temp, mock.patch.object(wechat_readonly, "parse_args", return_value=args), \
             mock.patch.object(wechat_readonly.platform, "system", return_value="Windows"), \
             mock.patch.object(wechat_readonly, "CLI", Path(sys.executable)), \
             mock.patch.object(wechat_readonly, "RUNTIME_ROOT", Path(temp)), \
             mock.patch.object(wechat_readonly, "resolve", return_value=Path(temp)), \
             mock.patch.object(wechat_readonly, "has_standing_read_authorization", return_value=True), \
             mock.patch.object(wechat_readonly, "get_key_catalog", return_value=None), \
             mock.patch.object(wechat_readonly, "extract_keys", return_value=catalog) as capture, \
             mock.patch.object(wechat_readonly, "store_key_catalog") as store, \
             mock.patch.object(wechat_readonly, "invoke", return_value=mock.Mock(returncode=0, stdout='{"sessions": []}')):
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(wechat_readonly.main(), 0)
            self.assertIn('"ok": true', output.getvalue())
            capture.assert_called_once()
            store.assert_called_once_with("个人微信", catalog)

    def test_capture_rejects_unbound_identity_and_keeps_scanner_errors_distinct(self):
        with mock.patch.object(wechat_readonly, "has_standing_read_authorization", return_value=False), \
             mock.patch.object(wechat_readonly, "extract_keys") as capture:
            with self.assertRaises(PermissionError):
                wechat_readonly.capture_bound_keys("个人微信", Path("unused"))
            capture.assert_not_called()
        with mock.patch.object(wechat_readonly, "has_standing_read_authorization", return_value=True), \
             mock.patch.object(wechat_readonly, "extract_keys", side_effect=RuntimeError("未能从任何微信进程中提取到密钥")):
            with self.assertRaises(LookupError):
                wechat_readonly.capture_bound_keys("个人微信", Path("unused"))
        with mock.patch.object(wechat_readonly, "has_standing_read_authorization", return_value=True), \
             mock.patch.object(wechat_readonly, "extract_keys", side_effect=RuntimeError("scanner permission error")):
            with self.assertRaisesRegex(RuntimeError, "scanner failed"):
                wechat_readonly.capture_bound_keys("个人微信", Path("unused"))

    def test_failed_refresh_does_not_overwrite_stored_catalog(self):
        args = argparse.Namespace(profile="个人微信", command="sessions", limit=1, max_chars=240,
                                  refresh_key_catalog=True)
        catalog = {"message/msg.db": {"enc_key": "ab" * 32, "salt": "cd" * 16}}
        with tempfile.TemporaryDirectory() as temp, mock.patch.object(wechat_readonly, "parse_args", return_value=args), \
             mock.patch.object(wechat_readonly.platform, "system", return_value="Windows"), \
             mock.patch.object(wechat_readonly, "CLI", Path(sys.executable)), \
             mock.patch.object(wechat_readonly, "RUNTIME_ROOT", Path(temp)), \
             mock.patch.object(wechat_readonly, "resolve", return_value=Path(temp)), \
             mock.patch.object(wechat_readonly, "has_standing_read_authorization", return_value=True), \
             mock.patch.object(wechat_readonly, "get_key_catalog", return_value=catalog), \
             mock.patch.object(wechat_readonly, "extract_keys", side_effect=RuntimeError("未能从任何微信进程中提取到密钥")), \
             mock.patch.object(wechat_readonly, "store_key_catalog") as store, \
             mock.patch.object(wechat_readonly, "invoke") as invoke:
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(wechat_readonly.main(), 8)
            self.assertIn('account_identity_unverified', output.getvalue())
            store.assert_not_called()
            invoke.assert_not_called()

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
        value = r"wxid_secret C:\Fixture\Alice\Documents\x abcdef0123456789abcdef0123456789"
        redacted = wechat_readonly.redact_text(value, 500)
        self.assertNotIn("wxid_secret", redacted)
        self.assertNotIn("C:\\Users", redacted)
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
