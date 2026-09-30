"""get-recent-sessions 命令"""

import os
import sqlite3
from contextlib import closing
from datetime import datetime

import click

from ..core.contacts import get_contact_names
from ..core.messages import decompress_content, format_msg_type
from ..output.formatter import output


@click.command("sessions")
@click.option("--limit", default=20, help="返回的会话数量")
@click.option("--format", "fmt", default="json", type=click.Choice(["json", "text"]), help="输出格式")
@click.pass_context
def sessions(ctx, limit, fmt):
    """获取最近会话列表

    \b
    示例:
      wechat-cli sessions                # 默认返回最近 20 个会话 (JSON)
      wechat-cli sessions --limit 10     # 最近 10 个会话
      wechat-cli sessions --format text  # 纯文本输出
    """
    app = ctx.obj

    path = app.cache.get(os.path.join("session", "session.db"))
    if not path:
        click.echo("错误: 无法解密 session.db", err=True)
        ctx.exit(3)

    names = get_contact_names(app.cache, app.decrypted_dir)
    with closing(sqlite3.connect(path)) as conn:
        rows = conn.execute("""
            SELECT username, unread_count, summary, last_timestamp,
                   last_msg_type, last_msg_sender, last_sender_display_name
            FROM SessionTable
            WHERE last_timestamp > 0
            ORDER BY last_timestamp DESC
            LIMIT ?
        """, (limit,)).fetchall()

    results = []
    for r in rows:
        username, unread, summary, ts, msg_type, sender, sender_name = r
        display = names.get(username, username)
        is_group = '@chatroom' in username

        if isinstance(summary, bytes):
            summary = decompress_content(summary, 4) or '(压缩内容)'
        if isinstance(summary, str) and ':\n' in summary:
            summary = summary.split(':\n', 1)[1]

        sender_display = ''
        if is_group and sender:
            sender_display = names.get(sender, sender_name or sender)

        results.append({
            'chat': display,
            'username': username,
            'is_group': is_group,
            'unread': unread or 0,
            'last_message': str(summary or ''),
            'msg_type': format_msg_type(msg_type),
            'sender': sender_display,
            'timestamp': ts,
            'time': datetime.fromtimestamp(ts).strftime('%m-%d %H:%M'),
        })

    if fmt == 'json':
        output(results, 'json')
    else:
        lines = []
        for r in results:
            entry = f"[{r['time']}] {r['chat']}"
            if r['is_group']:
                entry += " [群]"
            if r['unread'] > 0:
                entry += f" ({r['unread']}条未读)"
            entry += f"\n  {r['msg_type']}: "
            if r['sender']:
                entry += f"{r['sender']}: "
            entry += r['last_message']
            lines.append(entry)
        output(f"最近 {len(results)} 个会话:\n\n" + "\n\n".join(lines), 'text')
