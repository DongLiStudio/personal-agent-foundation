"""Windows 密钥提取 — 扫描 Weixin.exe 进程内存"""

import ctypes
import ctypes.wintypes as wt
import concurrent.futures
import functools
import hashlib
import os
import re
import struct
import subprocess
import time
from pathlib import Path

from .common import (
    collect_db_files,
    cross_verify_keys,
    save_results,
    scan_memory_for_keys,
    verify_enc_key,
)

print = functools.partial(print, flush=True)

kernel32 = ctypes.windll.kernel32
MEM_COMMIT = 0x1000
READABLE = {0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80}
PBKDF2_ROUNDS = 256_000
_STD_STRING_KEY_SIZE = 32
_STD_STRING_CAPACITIES = (47,)
_DLL_XOR_PATTERN = re.compile(
    b"\x48\xBA(.{8})"
    b".{3,8}?\x48\xBA(.{8})"
    b".{3,8}?\x48\xBA(.{8})"
    b".{3,8}?\x48\xBA(.{8})"
    b".{3,8}?\x48\x85\xC0",
    re.DOTALL,
)


class MBI(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", ctypes.c_uint64), ("AllocationBase", ctypes.c_uint64),
        ("AllocationProtect", wt.DWORD), ("_pad1", wt.DWORD),
        ("RegionSize", ctypes.c_uint64), ("State", wt.DWORD),
        ("Protect", wt.DWORD), ("Type", wt.DWORD), ("_pad2", wt.DWORD),
    ]


def _get_pids():
    """返回所有 Weixin.exe 进程的 (pid, mem_kb) 列表，按内存降序"""
    r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq Weixin.exe", "/FO", "CSV", "/NH"],
                       capture_output=True, text=True)
    pids = []
    for line in r.stdout.strip().split('\n'):
        if not line.strip():
            continue
        p = line.strip('"').split('","')
        if len(p) >= 5:
            pid = int(p[1])
            mem = int(p[4].replace(',', '').replace(' K', '').strip() or '0')
            pids.append((pid, mem))
    if not pids:
        raise RuntimeError("Weixin.exe 未运行")
    pids.sort(key=lambda x: x[1], reverse=True)
    for pid, mem in pids:
        print(f"[+] Weixin.exe PID={pid} ({mem // 1024}MB)")
    return pids


def _read_mem(h, addr, sz):
    buf = ctypes.create_string_buffer(sz)
    n = ctypes.c_size_t(0)
    if kernel32.ReadProcessMemory(h, ctypes.c_uint64(addr), buf, sz, ctypes.byref(n)):
        return buf.raw[:n.value]
    return None


def _get_process_image_path(handle):
    size = wt.DWORD(32768)
    buffer = ctypes.create_unicode_buffer(size.value)
    query = getattr(kernel32, "QueryFullProcessImageNameW", None)
    if query and query(handle, 0, buffer, ctypes.byref(size)):
        return buffer.value
    return ""


def _find_weixin_dll(image_path):
    if not image_path:
        return None
    install_dir = Path(image_path).parent
    candidates = []
    for pattern in (
        "Weixin.dll",
        "WeChat.dll",
        "*/Weixin.dll",
        "*/WeChat.dll",
        "install/*/Weixin.dll",
        "install/*/WeChat.dll",
    ):
        try:
            candidates.extend(path for path in install_dir.glob(pattern) if path.is_file())
        except OSError:
            continue
    if not candidates:
        return None
    return max(set(candidates), key=lambda path: path.stat().st_mtime)


def _extract_xor_key_candidates(data):
    return {
        b"".join(match.groups())
        for match in _DLL_XOR_PATTERN.finditer(data)
    }


def _scan_xor_keys_from_dll(dll_path):
    if not dll_path:
        return []
    found = set()
    tail = b""
    with open(dll_path, "rb") as file:
        while True:
            chunk = file.read(4 * 1024 * 1024)
            if not chunk:
                break
            data = tail + chunk
            found.update(_extract_xor_key_candidates(data))
            tail = data[-128:]
    return sorted(found)


def _iter_raw_key_pointers(data):
    """Yield pointers from MSVC std::string objects holding 32-byte keys.

    Weixin 4.1.10+ no longer reliably keeps the SQLCipher ``x'...'`` text in
    memory.  Its raw database key is still held by a long ``std::string`` whose
    object layout is: pointer, zero padding, size=32, capacity=47.
    """
    for capacity in _STD_STRING_CAPACITIES:
        marker = b"\x00" * 8 + struct.pack("<QQ", _STD_STRING_KEY_SIZE, capacity)
        cursor = 0
        while True:
            marker_pos = data.find(marker, cursor)
            if marker_pos < 0:
                break
            object_pos = marker_pos - 8
            if object_pos >= 0:
                pointer = struct.unpack_from("<Q", data, object_pos)[0]
                if 0x10000 <= pointer < 0x0000800000000000:
                    yield pointer
            cursor = marker_pos + 1


def _is_potential_raw_key(value):
    if not value or len(value) != _STD_STRING_KEY_SIZE:
        return False
    if len(set(value)) < 15:
        return False
    return sum(32 <= byte <= 126 for byte in value) <= 24


def _derive_encryption_key(raw_key, page1):
    return hashlib.pbkdf2_hmac(
        "sha512", raw_key, page1[:16], PBKDF2_ROUNDS, dklen=32,
    )


def _derive_key_map(raw_keys, db_files, remaining_salts, xor_keys=()):
    """Derive and verify per-database keys from raw Weixin key candidates."""
    derived_map = {}
    unique_pages = {}
    for _rel, _path, _size, salt_hex, page1 in db_files:
        if salt_hex in remaining_salts and salt_hex not in unique_pages:
            unique_pages[salt_hex] = page1

    # Session/contact/message databases are useful probes.  A raw key that
    # verifies one database is then expanded across all salts.
    ordered_salts = sorted(
        unique_pages,
        key=lambda salt: (
            not any(
                token in rel.replace("\\", "/").lower()
                for rel, _path, _size, item_salt, _page in db_files
                if item_salt == salt
                for token in ("session/", "contact/", "message/")
            ),
            salt,
        ),
    )
    if not ordered_salts:
        return derived_map
    probe_page = unique_pages[ordered_salts[0]]

    masks = tuple(xor_keys) or (None,)

    def verify_raw_key(item):
        raw_key, mask = item
        passphrase = (
            bytes(left ^ right for left, right in zip(raw_key, mask))
            if mask is not None
            else raw_key
        )
        enc_key = _derive_encryption_key(passphrase, probe_page)
        return passphrase if verify_enc_key(enc_key, probe_page) else None

    worker_count = min(8, max(1, os.cpu_count() or 1))
    candidate_pairs = (
        (raw_key, mask)
        for mask in masks
        for raw_key in raw_keys
    )
    with concurrent.futures.ThreadPoolExecutor(max_workers=worker_count) as pool:
        verified_passphrases = [
            passphrase for passphrase in pool.map(verify_raw_key, candidate_pairs)
            if passphrase is not None
        ]

    for passphrase in verified_passphrases:
        for salt_hex, page1 in unique_pages.items():
            if salt_hex in derived_map:
                continue
            enc_key = _derive_encryption_key(passphrase, page1)
            if verify_enc_key(enc_key, page1):
                derived_map[salt_hex] = enc_key.hex()
    return derived_map


def _enum_regions(h):
    regs = []
    addr = 0
    mbi = MBI()
    while addr < 0x7FFFFFFFFFFF:
        if kernel32.VirtualQueryEx(h, ctypes.c_uint64(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)) == 0:
            break
        if mbi.State == MEM_COMMIT and mbi.Protect in READABLE and 0 < mbi.RegionSize < 500 * 1024 * 1024:
            regs.append((mbi.BaseAddress, mbi.RegionSize))
        nxt = mbi.BaseAddress + mbi.RegionSize
        if nxt <= addr:
            break
        addr = nxt
    return regs


def extract_keys(db_dir, output_path, pid=None):
    """提取 Windows 微信数据库密钥。

    Args:
        db_dir: 微信数据库目录
        output_path: all_keys.json 输出路径
        pid: 可选，指定 PID（默认自动检测所有 Weixin.exe）

    Returns:
        dict: 数据库相对路径到已验证密钥元数据的映射
    """
    print("=" * 60)
    print("  提取所有微信数据库密钥")
    print("=" * 60)

    db_files, salt_to_dbs = collect_db_files(db_dir)

    print(f"\n找到 {len(db_files)} 个数据库, {len(salt_to_dbs)} 个不同的salt")

    pids = _get_pids() if pid is None else [(pid, 0)]

    hex_re = re.compile(b"x'([0-9a-fA-F]{64,192})'")
    key_map = {}
    remaining_salts = set(salt_to_dbs.keys())
    all_hex_matches = 0
    raw_key_candidates = set()
    dll_paths = set()
    t0 = time.time()

    for pid_val, mem_kb in pids:
        h = kernel32.OpenProcess(0x0010 | 0x0400, False, pid_val)
        if not h:
            print(f"[WARN] 无法打开进程 PID={pid_val}，跳过")
            continue

        try:
            dll_path = _find_weixin_dll(_get_process_image_path(h))
            if dll_path:
                dll_paths.add(dll_path)
            regions = _enum_regions(h)
            total_bytes = sum(s for _, s in regions)
            total_mb = total_bytes / 1024 / 1024
            print(f"\n[*] 扫描 PID={pid_val} ({total_mb:.0f}MB, {len(regions)} 区域)")

            scanned_bytes = 0
            for reg_idx, (base, size) in enumerate(regions):
                data = _read_mem(h, base, size)
                scanned_bytes += size
                if not data:
                    continue

                all_hex_matches += scan_memory_for_keys(
                    data, hex_re, db_files, salt_to_dbs,
                    key_map, remaining_salts, base, pid_val, print,
                )
                for pointer in _iter_raw_key_pointers(data):
                    raw_key = _read_mem(h, pointer, _STD_STRING_KEY_SIZE)
                    if _is_potential_raw_key(raw_key):
                        raw_key_candidates.add(raw_key)

                if (reg_idx + 1) % 200 == 0:
                    elapsed = time.time() - t0
                    progress = scanned_bytes / total_bytes * 100 if total_bytes else 100
                    print(
                        f"  [{progress:.1f}%] {len(key_map)}/{len(salt_to_dbs)} salts matched, "
                        f"{all_hex_matches} hex patterns, {elapsed:.1f}s"
                    )
        finally:
            kernel32.CloseHandle(h)

        if not remaining_salts:
            print(f"\n[+] 所有密钥已找到，跳过剩余进程")
            break

    if remaining_salts and raw_key_candidates:
        xor_keys = []
        for dll_path in dll_paths:
            try:
                xor_keys.extend(_scan_xor_keys_from_dll(dll_path))
            except OSError:
                continue
        xor_keys = sorted(set(xor_keys))
        print(
            f"\n[*] 新版密钥结构候选 {len(raw_key_candidates)} 个，"
            f"DLL 辅助候选 {len(xor_keys)} 个，开始 PBKDF2 验证"
        )
        if xor_keys:
            derived = _derive_key_map(
                raw_key_candidates, db_files, remaining_salts, xor_keys=xor_keys,
            )
        else:
            derived = _derive_key_map(raw_key_candidates, db_files, remaining_salts)
        key_map.update(derived)
        remaining_salts.difference_update(derived)
        if derived:
            print(f"[+] 新版密钥结构验证通过，匹配 {len(derived)} 个数据库 salt")

    elapsed = time.time() - t0
    print(
        f"\n扫描完成: {elapsed:.1f}s, {len(pids)} 个进程, "
        f"{all_hex_matches} hex模式, {len(raw_key_candidates)} 个新版结构候选"
    )

    cross_verify_keys(db_files, salt_to_dbs, key_map, print)
    return save_results(db_files, salt_to_dbs, key_map, output_path, print)
