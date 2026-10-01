"""Host-local WeChat Profile bindings protected with Windows DPAPI.

GLOBAL stores only logical Profile descriptions.  This module stores the
sensitive local db_storage path and verified database key catalog in a
CurrentUser DPAPI slot on this host.
"""

from __future__ import annotations

import base64
import ctypes
import ctypes.wintypes as wt
import hashlib
import hmac
import json
import os
import platform
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROFILE_RE = re.compile(r"^[^\\/:*?\"<>|\r\n]{1,64}$")
ROOT = Path(os.environ.get("LOCALAPPDATA", "")) / "DongLi" / "AgentFoundation" / "credentials" / "wechat-readonly"
INDEX = ROOT / "profiles.json"
SALT = ROOT / "host-salt.bin"


class DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wt.DWORD), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]


crypt32 = ctypes.windll.crypt32 if platform.system() == "Windows" else None
kernel32 = ctypes.windll.kernel32 if platform.system() == "Windows" else None


def _blob(data: bytes) -> tuple[DATA_BLOB, ctypes.Array[Any]]:
    buf = ctypes.create_string_buffer(data)
    return DATA_BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_ubyte))), buf


def protect(data: bytes) -> bytes:
    if crypt32 is None:
        raise RuntimeError("Windows DPAPI is required")
    source, source_buf = _blob(data)
    output = DATA_BLOB()
    if not crypt32.CryptProtectData(ctypes.byref(source), "wechat-readonly", None, None, None, 0, ctypes.byref(output)):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(output.pbData, output.cbData)
    finally:
        kernel32.LocalFree(output.pbData)


def unprotect(data: bytes) -> bytes:
    if crypt32 is None:
        raise RuntimeError("Windows DPAPI is required")
    source, source_buf = _blob(data)
    output = DATA_BLOB()
    if not crypt32.CryptUnprotectData(ctypes.byref(source), None, None, None, None, 0, ctypes.byref(output)):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(output.pbData, output.cbData)
    finally:
        kernel32.LocalFree(output.pbData)


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_bytes(data)
    os.replace(temp, path)


def _load_index() -> dict[str, Any]:
    if not INDEX.exists():
        return {"schema": 1, "profiles": {}}
    payload = json.loads(INDEX.read_text(encoding="utf-8"))
    if payload.get("schema") != 1 or not isinstance(payload.get("profiles"), dict):
        raise RuntimeError("WeChat Profile index is invalid")
    return payload


def _save_index(payload: dict[str, Any]) -> None:
    _atomic_write(INDEX, (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def _host_salt() -> bytes:
    ROOT.mkdir(parents=True, exist_ok=True)
    if not SALT.exists():
        _atomic_write(SALT, secrets.token_bytes(32))
    value = SALT.read_bytes()
    if len(value) != 32:
        raise RuntimeError("Host fingerprint salt is invalid")
    return value


def fingerprint(path: Path) -> str:
    normalized = os.path.normcase(os.path.abspath(path))
    return hmac.new(_host_salt(), normalized.encode("utf-8"), hashlib.sha256).hexdigest()[:16]


def validate_profile_name(name: str) -> str:
    name = name.strip()
    if not PROFILE_RE.fullmatch(name):
        raise ValueError("Profile name must be 1-64 characters and contain no path-reserved characters")
    return name


def _slot_name(profile: str) -> str:
    return hashlib.sha256(profile.encode("utf-8")).hexdigest() + ".slot"


def _read_slot(profile: str) -> tuple[dict[str, Any], dict[str, Any]]:
    profile = validate_profile_name(profile)
    index = _load_index()
    info = index["profiles"].get(profile)
    if not info:
        raise KeyError(f"Unknown WeChat Profile: {profile}")
    slot_path = ROOT / info["slot"]
    raw = unprotect(base64.b64decode(slot_path.read_bytes(), validate=True))
    payload = json.loads(raw.decode("utf-8"))
    if payload.get("profile") != profile or payload.get("schema") not in (1, 2):
        raise RuntimeError("WeChat Profile slot identity mismatch")
    return payload, info


def _write_slot(profile: str, payload: dict[str, Any]) -> None:
    encrypted = protect(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    _atomic_write(ROOT / _slot_name(profile), base64.b64encode(encrypted))


def _validate_key_catalog(catalog: Any) -> dict[str, Any]:
    if not isinstance(catalog, dict) or not catalog:
        raise ValueError("Verified WeChat database key catalog is empty or invalid")
    clean: dict[str, Any] = {}
    for relative, metadata in catalog.items():
        if not isinstance(relative, str) or Path(relative).is_absolute() or ".." in Path(relative).parts:
            raise ValueError("WeChat database key catalog contains an unsafe relative path")
        if not isinstance(metadata, dict):
            raise ValueError("WeChat database key metadata is invalid")
        enc_key = metadata.get("enc_key")
        salt = metadata.get("salt")
        if not isinstance(enc_key, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", enc_key):
            raise ValueError("WeChat database key catalog contains an invalid key")
        if not isinstance(salt, str) or not re.fullmatch(r"[0-9a-fA-F]{32}", salt):
            raise ValueError("WeChat database key catalog contains an invalid salt")
        clean[relative] = {
            "enc_key": enc_key.lower(),
            "salt": salt.lower(),
            "size_mb": metadata.get("size_mb", 0),
        }
    return clean


def bind(profile: str, db_dir: Path) -> dict[str, Any]:
    profile = validate_profile_name(profile)
    db_dir = db_dir.resolve(strict=True)
    if db_dir.name.lower() != "db_storage" or not any(db_dir.rglob("*.db")):
        raise ValueError("Selected candidate is not a valid WeChat db_storage directory")
    payload = {
        "schema": 2,
        "profile": profile,
        "db_dir": str(db_dir),
        "key_catalog": None,
        "key_captured_at": None,
        "standing_read_authorization": True,
        "bound_at": datetime.now(timezone.utc).isoformat(),
    }
    slot = _slot_name(profile)
    _write_slot(profile, payload)
    index = _load_index()
    index["profiles"][profile] = {
        "slot": slot,
        "fingerprint": fingerprint(db_dir),
        "bound_at": payload["bound_at"],
    }
    _save_index(index)
    return {"profile": profile, "fingerprint": index["profiles"][profile]["fingerprint"], "bound": True}


def resolve(profile: str) -> Path:
    payload, info = _read_slot(profile)
    path = Path(payload["db_dir"])
    if not path.is_dir():
        raise FileNotFoundError("Bound WeChat data directory is unavailable; rebind this Profile")
    if not hmac.compare_digest(fingerprint(path), info["fingerprint"]):
        raise RuntimeError("WeChat Profile binding fingerprint mismatch")
    return path


def get_key_catalog(profile: str) -> dict[str, Any] | None:
    payload, _info = _read_slot(profile)
    catalog = payload.get("key_catalog")
    return _validate_key_catalog(catalog) if catalog else None


def has_standing_read_authorization(profile: str) -> bool:
    payload, _info = _read_slot(profile)
    return payload.get("schema") == 2 and payload.get("standing_read_authorization") is True


def store_key_catalog(profile: str, catalog: Any) -> dict[str, Any]:
    profile = validate_profile_name(profile)
    payload, _info = _read_slot(profile)
    clean = _validate_key_catalog(catalog)
    payload.update({
        "schema": 2,
        "key_catalog": clean,
        "key_captured_at": datetime.now(timezone.utc).isoformat(),
        "standing_read_authorization": True,
    })
    _write_slot(profile, payload)
    return {"profile": profile, "key_catalog_stored": True, "database_entries": len(clean)}


def list_profiles() -> list[dict[str, Any]]:
    index = _load_index()
    result = []
    for name, info in sorted(index["profiles"].items()):
        try:
            available = resolve(name).is_dir()
        except Exception:
            available = False
        try:
            offline_key_available = get_key_catalog(name) is not None
        except Exception:
            offline_key_available = False
        result.append({
            "profile": name,
            "fingerprint": info.get("fingerprint", ""),
            "available": available,
            "offline_key_available": offline_key_available,
            "bound_at": info.get("bound_at"),
        })
    return result


def remove(profile: str) -> bool:
    profile = validate_profile_name(profile)
    index = _load_index()
    info = index["profiles"].pop(profile, None)
    if not info:
        return False
    slot = ROOT / info["slot"]
    if slot.exists():
        slot.unlink()
    _save_index(index)
    return True


def discover_candidates() -> list[tuple[str, Path, float]]:
    roots: list[Path] = []
    appdata = Path(os.environ.get("APPDATA", ""))
    config_dir = appdata / "Tencent" / "xwechat" / "config"
    if config_dir.is_dir():
        for ini in config_dir.glob("*.ini"):
            for encoding in ("utf-8", "gbk"):
                try:
                    text = ini.read_text(encoding=encoding).strip()
                    if text and "\n" not in text and "\r" not in text:
                        candidate = Path(text)
                        if candidate.is_dir():
                            roots.append(candidate)
                    break
                except UnicodeDecodeError:
                    continue
                except OSError:
                    break
    roots.append(Path.home() / "Documents")
    seen: set[str] = set()
    found: list[tuple[str, Path, float]] = []
    for root in roots:
        base = root / "xwechat_files"
        if not base.is_dir():
            continue
        for db_dir in base.glob("*/db_storage"):
            normalized = os.path.normcase(os.path.abspath(db_dir))
            if normalized in seen or not db_dir.is_dir():
                continue
            seen.add(normalized)
            latest = db_dir.stat().st_mtime
            for item in db_dir.rglob("*.db*"):
                try:
                    latest = max(latest, item.stat().st_mtime)
                except OSError:
                    pass
            found.append((fingerprint(db_dir), db_dir, latest))
    found.sort(key=lambda item: item[2], reverse=True)
    return found


def self_test() -> dict[str, Any]:
    sample = secrets.token_bytes(48)
    restored = unprotect(protect(sample))
    return {"ok": hmac.compare_digest(sample, restored), "protection": "windows-dpapi-current-user"}
