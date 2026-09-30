"""Manage host-local WeChat logical Profiles without exposing raw data paths."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

from profile_store import bind, discover_candidates, list_profiles, remove, self_test


def emit(payload: object) -> None:
    print(json.dumps(payload, ensure_ascii=True, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage DPAPI-protected local WeChat Profile bindings")
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("discover", help="list redacted local WeChat data candidates")
    sub.add_parser("list", help="list logical Profiles without revealing paths")
    connect = sub.add_parser("connect", help="bind one logical Profile to one discovered candidate")
    connect.add_argument("--profile", required=True)
    connect.add_argument("--candidate", required=True, help="candidate fingerprint returned by discover")
    connect.add_argument("--confirm-owner", action="store_true", help="confirm the user owns or may access this account")
    delete = sub.add_parser("remove", help="remove only the local binding, never WeChat data")
    delete.add_argument("--profile", required=True)
    delete.add_argument("--confirm", action="store_true")
    sub.add_parser("self-test", help="test DPAPI without reading WeChat")
    args = parser.parse_args()

    if args.action == "discover":
        candidates = []
        for index, (candidate_id, _path, mtime) in enumerate(discover_candidates(), 1):
            candidates.append({
                "candidate": candidate_id,
                "order": index,
                "last_activity_utc": datetime.fromtimestamp(mtime, timezone.utc).isoformat(),
            })
        emit({"ok": True, "candidates": candidates, "paths_revealed": False})
        return 0
    if args.action == "list":
        emit({"ok": True, "profiles": list_profiles(), "default_profile": None})
        return 0
    if args.action == "self-test":
        emit(self_test())
        return 0
    if args.action == "connect":
        if not args.confirm_owner:
            emit({"ok": False, "error": "Explicit owner/authorization confirmation is required."})
            return 2
        matches = [item for item in discover_candidates() if item[0] == args.candidate]
        if len(matches) != 1:
            emit({"ok": False, "error": "Candidate is missing or ambiguous; run discover again."})
            return 3
        emit({"ok": True, **bind(args.profile, matches[0][1]), "protection": "windows-dpapi-current-user"})
        return 0
    if not args.confirm:
        emit({"ok": False, "error": "Removal confirmation is required."})
        return 2
    emit({"ok": True, "profile": args.profile, "removed": remove(args.profile), "wechat_data_deleted": False})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
