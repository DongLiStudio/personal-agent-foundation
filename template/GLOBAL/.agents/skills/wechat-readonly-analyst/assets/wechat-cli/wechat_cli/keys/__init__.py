"""密钥提取模块 — 根据平台调用对应的 scanner"""

import platform


def extract_keys(db_dir, output_path, pid=None):
    """提取微信数据库密钥并保存到 output_path。

    Args:
        db_dir: 微信数据库目录（db_storage）
        output_path: all_keys.json 输出路径；为 None 时只在内存中返回
        pid: 可选，指定微信进程 PID（默认自动检测）

    Returns:
        dict: 数据库相对路径到已验证密钥元数据的映射

    Raises:
        RuntimeError: 提取失败
    """
    system = platform.system().lower()
    if system == "windows":
        from .scanner_windows import extract_keys as _extract
        return _extract(db_dir, output_path, pid=pid)
    else:
        raise RuntimeError("该加固版仅支持 Windows")
