"""init 命令 — 交互式初始化，提取密钥并生成配置"""

import json
import os
import sys

import click

from ..core.config import STATE_DIR, CONFIG_FILE, KEYS_FILE, auto_detect_db_dir


@click.command()
@click.option("--db-dir", default=None, help="微信数据目录路径（默认自动检测）")
@click.option("--force", is_flag=True, help="强制重新提取密钥")
def init(db_dir, force):
    """初始化 wechat-cli：提取密钥并生成配置"""
    click.echo("WeChat CLI 初始化")
    click.echo("=" * 40)

    # 1. 检查是否已初始化
    if os.path.exists(CONFIG_FILE) and os.path.exists(KEYS_FILE) and not force:
        click.echo(f"已初始化（配置: {CONFIG_FILE}）")
        click.echo("使用 --force 重新提取密钥")
        return

    # 2. 创建状态目录
    os.makedirs(STATE_DIR, exist_ok=True)

    # 3. 确定 db_dir。加固版禁止自动猜测账号，必须由 Profile 层显式传入。
    if db_dir is None:
        click.echo("[!] 加固版要求由已授权 Profile 显式提供微信数据目录", err=True)
        sys.exit(1)
    else:
        db_dir = os.path.abspath(db_dir)
        if not os.path.isdir(db_dir):
            click.echo("[!] 指定的数据目录不存在（路径已隐藏）", err=True)
            sys.exit(1)
        click.echo("[+] 使用指定数据目录（路径已隐藏）")

    # 4. 提取密钥
    click.echo("\n开始提取密钥...")
    try:
        from ..keys import extract_keys
        key_map = extract_keys(db_dir, KEYS_FILE)
    except RuntimeError as e:
        click.echo(f"\n[!] 密钥提取失败: {e}", err=True)
        if "sudo" not in str(e).lower():
            click.echo("提示: macOS/Linux 可能需要 sudo 权限", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"\n[!] 密钥提取出错: {e}", err=True)
        sys.exit(1)

    # 5. 写入配置
    cfg = {
        "db_dir": db_dir,
    }
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)

    click.echo(f"\n[+] 初始化完成!")
    click.echo(f"    配置: {CONFIG_FILE}")
    click.echo(f"    密钥: {KEYS_FILE}")
    click.echo(f"    提取到 {len(key_map)} 个数据库密钥")
    click.echo("\n现在可以使用:")
    click.echo("  wechat-cli sessions")
    click.echo("  wechat-cli history \"联系人\"")
