"""wechat-cli 入口"""

import sys

import click

from .core.context import AppContext

_VERSION = "0.3.0+dongli.readonly"


@click.group()
@click.version_option(version=_VERSION, prog_name="wechat-cli")
@click.option("--config", "config_path", default=None, envvar="WECHAT_CLI_CONFIG",
              help="config.json 路径（默认自动查找）")
@click.pass_context
def cli(ctx, config_path):
    """WeChat CLI — 加固的本机只读查询引擎

    \b
    使用示例:
      wechat-cli init                                # 首次使用：提取密钥
      wechat-cli sessions                            # 最近会话列表
      wechat-cli sessions --limit 10                 # 最近 10 个会话
      wechat-cli history "张三" --limit 20          # 查看张三的最近 20 条消息
      wechat-cli history "AI交流群" --start-time "2026-04-01"  # 指定时间范围
      wechat-cli search "Claude" --chat "AI交流群"   # 在指定群里搜索关键词
      wechat-cli search "你好" --limit 50           # 全局搜索
    该引擎只注册 init、sessions、history、search、stats。
    业务调用必须经过上层 wechat_readonly.py 的 Profile、授权和脱敏门禁。
    """
    # init/version 命令不需要 AppContext
    if ctx.invoked_subcommand in ("init", "version"):
        return

    try:
        ctx.obj = AppContext(config_path)
    except FileNotFoundError as e:
        click.echo(str(e), err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"初始化失败: {e}", err=True)
        sys.exit(1)


# 注册子命令
from .commands.init import init
from .commands.sessions import sessions
from .commands.history import history
from .commands.search import search
from .commands.stats import stats

cli.add_command(init)
cli.add_command(sessions)
cli.add_command(history)
cli.add_command(search)
cli.add_command(stats)


if __name__ == "__main__":
    cli()
