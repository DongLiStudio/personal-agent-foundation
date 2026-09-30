"""密钥工具 — 路径匹配、元数据剥离"""

import os
import posixpath


def strip_key_metadata(keys):
    return {k: v for k, v in keys.items() if not k.startswith("_")}


def _is_safe_rel_path(path):
    normalized = path.replace("\\", "/")
    return ".." not in posixpath.normpath(normalized).split("/")


def key_path_variants(rel_path):
    normalized = rel_path.replace("\\", "/")
    variants = []
    for candidate in (
        rel_path,
        normalized,
        normalized.replace("/", "\\"),
        normalized.replace("/", os.sep),
    ):
        if candidate not in variants:
            variants.append(candidate)
    return variants


def get_key_info(keys, rel_path):
    if not _is_safe_rel_path(rel_path):
        return None
    for candidate in key_path_variants(rel_path):
        if candidate in keys and not candidate.startswith("_"):
            return keys[candidate]
    return None
