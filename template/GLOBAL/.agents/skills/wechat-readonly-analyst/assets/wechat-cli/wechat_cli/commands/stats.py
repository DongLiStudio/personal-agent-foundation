"""stats 命令 — 聊天统计分析"""

import click

from ..core.contacts import get_contact_names
from ..core.messages import (
    collect_chat_stats,
    parse_time_range,
    resolve_chat_context,
)
from ..output.formatter import output


@click.command("stats")
@click.argument("chat_name")
@click.option("--start-time", default="", help="起始时间 YYYY-MM-DD [HH:MM[:SS]]")
@click.option("--end-time", default="", help="结束时间 YYYY-MM-DD [HH:MM[:SS]]")
@click.option("--format", "fmt", default="json", type=click.Choice(["json", "text"]), help="输出格式")
@click.pass_context
def stats(ctx, chat_name, start_time, end_time, fmt):
    """聊天统计分析

    \b
    示例:
      wechat-cli stats "AI交流群"
      wechat-cli stats "张三" --start-time "2026-04-01" --end-time "2026-04-03"
      wechat-cli stats "群名" --format text
    """
    app = ctx.obj

    try:
        start_ts, end_ts = parse_time_range(start_time, end_time)
    except ValueError as e:
        click.echo(f"错误: {e}", err=True)
        ctx.exit(2)

    chat_ctx = resolve_chat_context(chat_name, app.msg_db_keys, app.cache, app.decrypted_dir)
    if not chat_ctx:
        click.echo(f"找不到聊天对象: {chat_name}", err=True)
        ctx.exit(1)
    if not chat_ctx['db_path']:
        click.echo(f"找不到 {chat_ctx['display_name']} 的消息记录", err=True)
        ctx.exit(1)

    names = get_contact_names(app.cache, app.decrypted_dir)
    result = collect_chat_stats(
        chat_ctx, names, app.display_name_fn,
        start_ts=start_ts, end_ts=end_ts,
    )

    if fmt == 'json':
        output({
            'chat': chat_ctx['display_name'],
            'username': chat_ctx['username'],
            'is_group': chat_ctx['is_group'],
            **result,
        }, 'json')
    else:
        lines = [f"{chat_ctx['display_name']} 聊天统计"]
        if chat_ctx['is_group']:
            lines[0] += " [群聊]"
        lines.append(f"消息总数: {result['total']}")
        if start_time or end_time:
            lines.append(f"时间范围: {start_time or '最早'} ~ {end_time or '最新'}")

        # 类型分布
        lines.append("\n消息类型分布:")
        for t, cnt in result['type_breakdown'].items():
            pct = cnt / result['total'] * 100 if result['total'] > 0 else 0
            lines.append(f"  {t}: {cnt} ({pct:.1f}%)")

        # 发送者排名
        if result['top_senders']:
            lines.append("\n发言排行 Top 10:")
            for s in result['top_senders']:
                lines.append(f"  {s['name']}: {s['count']}")

        # 24小时分布
        lines.append("\n24小时活跃分布:")
        max_count = max(result['hourly'].values()) if result['hourly'] else 0
        bar_max = 30
        for h in range(24):
            count = result['hourly'].get(h, 0)
            bar_len = int(count / max_count * bar_max) if max_count > 0 else 0
            bar = '█' * bar_len
            lines.append(f"  {h:02d}时 |{bar} {count}")

        output("\n".join(lines), 'text')
