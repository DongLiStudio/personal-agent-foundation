#!/usr/bin/env python3
"""Minimal read-only IMAP probe/search/attachment downloader.

The password or app-specific authorization code must be supplied through
AGENT_MAIL_SECRET. Commands never modify message flags and use BODY.PEEK.
"""

from __future__ import annotations

import argparse
import email
import hashlib
import imaplib
import json
import os
import pathlib
import ssl
import sys
from email import policy
from email.header import decode_header, make_header


def decode(value: str | None) -> str:
    if not value:
        return ""
    return str(make_header(decode_header(value)))


def connect(args: argparse.Namespace) -> imaplib.IMAP4_SSL:
    secret = os.environ.get("AGENT_MAIL_SECRET")
    if not secret:
        raise RuntimeError("AGENT_MAIL_SECRET is not set")
    context = ssl.create_default_context()
    client = imaplib.IMAP4_SSL(args.host, args.port, ssl_context=context)
    client.login(args.username, secret)
    # NetEase/Coremail may reject mailbox selection as "Unsafe Login" unless
    # a third-party client identifies itself with the IMAP ID extension.
    if "ID" in client.capabilities:
        imaplib.Commands.setdefault("ID", ("AUTH",))
        client._simple_command(
            "ID",
            '("name" "Codex Mail Profile" "version" "1.0" "vendor" "OpenAI")',
        )
    return client


def select_readonly(client: imaplib.IMAP4_SSL, mailbox: str, allow_select_fallback: bool = False) -> str:
    status, data = client.select(mailbox, readonly=True)
    if status != "OK" and allow_select_fallback:
        status, data = client.select(mailbox, readonly=False)
        if status == "OK":
            return "select-with-body-peek"
    if status != "OK":
        detail = " ".join(item.decode(errors="replace") for item in (data or []) if item)
        raise RuntimeError(f"cannot open mailbox read-only: {mailbox}: {detail}")
    return "examine-readonly"


def parse_message(raw: bytes) -> email.message.Message:
    return email.message_from_bytes(raw, policy=policy.default)


def message_meta(uid: str, msg: email.message.Message) -> dict[str, object]:
    attachments = []
    for part in msg.walk():
        filename = part.get_filename()
        if filename:
            attachments.append(decode(filename))
    return {
        "uid": uid,
        "date": msg.get("Date", ""),
        "from": decode(msg.get("From")),
        "subject": decode(msg.get("Subject")),
        "attachments": attachments,
    }


def fetch_peek(client: imaplib.IMAP4_SSL, uid: str) -> bytes:
    status, data = client.uid("fetch", uid, "(BODY.PEEK[])")
    if status != "OK" or not data or not isinstance(data[0], tuple):
        raise RuntimeError(f"cannot fetch UID {uid}")
    return data[0][1]


def cmd_probe(args: argparse.Namespace) -> dict[str, object]:
    client = connect(args)
    try:
        status, mailboxes = client.list()
        if status != "OK":
            raise RuntimeError("cannot list mailboxes")
        return {
            "ok": True,
            "host": args.host,
            "port": args.port,
            "username": args.username,
            "mailbox_count": len(mailboxes or []),
            "mailboxes": [item.decode(errors="replace") for item in (mailboxes or [])],
            "server_welcome": client.welcome.decode(errors="replace") if client.welcome else "",
        }
    finally:
        try:
            client.logout()
        except Exception:
            pass


def cmd_search(args: argparse.Namespace) -> dict[str, object]:
    client = connect(args)
    try:
        select_mode = select_readonly(client, args.mailbox, args.allow_select_fallback)
        status, data = client.uid("search", None, args.query)
        if status != "OK":
            raise RuntimeError("IMAP search failed")
        uids = (data[0] or b"").decode().split()
        if args.limit:
            uids = uids[-args.limit :]
        items = [message_meta(uid, parse_message(fetch_peek(client, uid))) for uid in uids]
        return {"ok": True, "mailbox": args.mailbox, "select_mode": select_mode, "count": len(items), "messages": items}
    finally:
        try:
            client.close()
        except Exception:
            pass
        try:
            client.logout()
        except Exception:
            pass


def safe_name(name: str) -> str:
    cleaned = "".join("_" if ch in '<>:"/\\|?*' else ch for ch in name).strip(" .")
    return cleaned or "attachment.bin"


def cmd_download(args: argparse.Namespace) -> dict[str, object]:
    out = pathlib.Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=True)
    client = connect(args)
    results = []
    try:
        select_mode = select_readonly(client, args.mailbox, args.allow_select_fallback)
        for uid in args.uids.split(","):
            uid = uid.strip()
            if not uid:
                continue
            msg = parse_message(fetch_peek(client, uid))
            for index, part in enumerate(msg.walk(), start=1):
                filename = part.get_filename()
                if not filename:
                    continue
                payload = part.get_payload(decode=True) or b""
                target = out / f"{uid}-{index}-{safe_name(decode(filename))}"
                target.write_bytes(payload)
                results.append(
                    {
                        "uid": uid,
                        "original_name": decode(filename),
                        "path": str(target),
                        "size": len(payload),
                        "sha256": hashlib.sha256(payload).hexdigest(),
                    }
                )
        return {"ok": True, "mailbox": args.mailbox, "select_mode": select_mode, "attachments": results}
    finally:
        try:
            client.close()
        except Exception:
            pass
        try:
            client.logout()
        except Exception:
            pass


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Read-only IMAP utility")
    p.add_argument("--host", required=True)
    p.add_argument("--port", type=int, default=993)
    p.add_argument("--username", required=True)
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("probe")
    search = sub.add_parser("search")
    search.add_argument("--mailbox", default="INBOX")
    search.add_argument("--query", default="ALL")
    search.add_argument("--limit", type=int, default=50)
    search.add_argument("--allow-select-fallback", action="store_true")
    download = sub.add_parser("download")
    download.add_argument("--mailbox", default="INBOX")
    download.add_argument("--uids", required=True)
    download.add_argument("--output", required=True)
    download.add_argument("--allow-select-fallback", action="store_true")
    return p


def main() -> int:
    args = parser().parse_args()
    try:
        if args.command == "probe":
            result = cmd_probe(args)
        elif args.command == "search":
            result = cmd_search(args)
        else:
            result = cmd_download(args)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
