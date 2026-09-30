"""Render an already-redacted chat summary JSON as a polished single-file HTML report."""

from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path


SENSITIVE_PATTERNS = (
    re.compile(r"(?i)wxid_[a-z0-9_-]+"),
    re.compile(r"(?i)\b[0-9a-f]{48,}\b"),
    re.compile(r"(?i)(?:[a-z]:\\|/users/|/home/)"),
)
FORBIDDEN_KEYS = {
    "messages", "results", "username", "wxid", "db_path", "database_path",
    "keys", "key", "salt", "config_path", "decrypted_path",
}
ALLOWED_TOP_LEVEL = {
    "title", "subtitle", "date_range", "total_messages", "thesis", "metrics",
    "sections", "actions", "warning", "data_note",
}


def esc(value: object) -> str:
    return html.escape(str(value or ""), quote=True)


def validate_safe(raw: str) -> None:
    if len(raw.encode("utf-8")) > 1024 * 1024:
        raise ValueError("Report input exceeds the 1 MiB safety limit.")
    if any(pattern.search(raw) for pattern in SENSITIVE_PATTERNS):
        raise ValueError("Input appears to contain an identifier, key, or local path. Redact it first.")


def validate_schema(data: dict) -> None:
    if not isinstance(data, dict):
        raise ValueError("Report input must be a JSON object.")
    unknown = set(data) - ALLOWED_TOP_LEVEL
    if unknown:
        raise ValueError("Report input contains unsupported top-level fields.")

    def walk(value: object) -> None:
        if isinstance(value, dict):
            if any(str(key).lower() in FORBIDDEN_KEYS for key in value):
                raise ValueError("Report input contains raw-query or sensitive fields.")
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            if len(value) > 100:
                raise ValueError("Report input contains an oversized list.")
            for item in value:
                walk(item)
        elif isinstance(value, str) and len(value) > 4000:
            raise ValueError("Report input contains an oversized text field.")

    walk(data)


def render(data: dict) -> str:
    title = esc(data.get("title", "微信聊天洞察"))
    subtitle = esc(data.get("subtitle", "从本机可用记录提炼"))
    date_range = esc(data.get("date_range", "时间范围未提供"))
    total = esc(data.get("total_messages", "—"))
    thesis = esc(data.get("thesis", "信息已完成脱敏整理。"))
    warning = esc(data.get("warning", ""))
    data_note = esc(data.get("data_note", "仅包含本机可用记录；媒体附件内容未默认解析。"))

    metrics = [{"value": total, "label": "消息总数"}]
    metrics.extend(data.get("metrics", [])[:5])
    metric_html = "".join(
        f'<article class="metric"><strong>{esc(item.get("value", "—"))}</strong><span>{esc(item.get("label", "指标"))}</span></article>'
        for item in metrics
    )

    section_html = []
    for index, section in enumerate(data.get("sections", []), 1):
        bullets = "".join(f"<li>{esc(item)}</li>" for item in section.get("bullets", []))
        section_html.append(
            f'<article class="card"><div class="index">{index:02d}</div>'
            f'<h3>{esc(section.get("title", "主题"))}</h3>'
            f'<p>{esc(section.get("body", ""))}</p>'
            f'{f"<ul>{bullets}</ul>" if bullets else ""}</article>'
        )

    action_html = "".join(
        f'<div class="action"><span>{esc(item.get("text", ""))}</span><b>{esc(item.get("priority", ""))}</b></div>'
        for item in data.get("actions", [])
    )
    warning_html = f'<aside class="warning"><b>风险提醒</b><p>{warning}</p></aside>' if warning else ""

    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="脱敏微信聊天洞察报告"><title>{title}</title>
<style>
:root{{--bg:#060a13;--panel:#0e1726;--line:rgba(255,255,255,.1);--text:#f5f8fc;--muted:#9ba9bd;--cyan:#70e7ff;--blue:#788fff;--gold:#e8c37c;--danger:#ff9e96}}
*{{box-sizing:border-box}}html{{scroll-behavior:smooth}}body{{margin:0;color:var(--text);background:radial-gradient(circle at 8% 0,rgba(120,143,255,.2),transparent 38rem),radial-gradient(circle at 95% 12%,rgba(112,231,255,.13),transparent 32rem),var(--bg);font:16px/1.7 Inter,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif}}body:before{{content:"";position:fixed;inset:0;pointer-events:none;background-image:linear-gradient(rgba(255,255,255,.025) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.025) 1px,transparent 1px);background-size:48px 48px;mask-image:linear-gradient(#000,transparent 85%)}}.wrap{{width:min(1120px,calc(100% - 36px));margin:auto;position:relative}}header{{display:flex;justify-content:space-between;align-items:center;padding:24px 0;color:var(--muted);font-size:.85rem}}button{{color:var(--text);background:rgba(255,255,255,.05);border:1px solid var(--line);border-radius:999px;padding:9px 15px;cursor:pointer}}.hero{{min-height:62vh;display:grid;align-content:center;padding:70px 0 88px}}.eyebrow{{color:var(--cyan);font-size:.76rem;font-weight:800;letter-spacing:.17em;text-transform:uppercase}}h1{{font-size:clamp(3rem,8vw,6.8rem);line-height:.95;letter-spacing:-.065em;margin:16px 0 24px;max-width:900px}}h1 span{{color:transparent;background:linear-gradient(95deg,#fff,var(--cyan) 60%,var(--blue));-webkit-background-clip:text;background-clip:text}}.sub{{max-width:720px;color:#c8d2df;font-size:1.12rem}}.date{{margin-top:26px;color:var(--muted)}}section{{padding:60px 0}}h2{{font-size:clamp(2rem,4vw,3.1rem);letter-spacing:-.045em;line-height:1.1;margin:0 0 28px}}.metrics{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}}.metric,.card,.quote,.actions,.warning{{background:linear-gradient(145deg,rgba(255,255,255,.06),rgba(255,255,255,.025));border:1px solid var(--line);border-radius:22px;box-shadow:0 22px 60px rgba(0,0,0,.3);backdrop-filter:blur(14px)}}.metric{{min-height:145px;padding:24px;display:flex;flex-direction:column;justify-content:space-between}}.metric strong{{font-size:2.5rem;letter-spacing:-.05em;color:var(--cyan)}}.metric span{{color:var(--muted)}}.quote{{padding:38px;border-color:rgba(112,231,255,.3)}}.quote p{{font-size:clamp(1.5rem,3vw,2.3rem);line-height:1.4;letter-spacing:-.025em;margin:16px 0 0}}.grid{{display:grid;grid-template-columns:repeat(2,1fr);gap:14px}}.card{{padding:28px;position:relative;overflow:hidden}}.card .index{{position:absolute;right:18px;bottom:-24px;font-size:6.4rem;font-weight:800;color:rgba(255,255,255,.04);line-height:1}}h3{{font-size:1.3rem;margin:8px 0 10px}}.card p,.card li,.warning p{{color:var(--muted)}}ul{{padding-left:20px;margin-bottom:0}}.actions{{padding:30px;display:grid;gap:10px}}.action{{display:flex;justify-content:space-between;gap:20px;padding:15px 17px;background:rgba(255,255,255,.035);border:1px solid var(--line);border-radius:15px}}.action b{{color:var(--gold)}}.warning{{margin-top:14px;padding:24px;border-color:rgba(255,158,150,.3)}}.warning b{{color:var(--danger)}}.warning p{{margin:8px 0 0}}footer{{margin-top:56px;padding:42px 0 62px;border-top:1px solid var(--line);color:var(--muted);font-size:.86rem}}@media(max-width:720px){{.metrics,.grid{{grid-template-columns:1fr}}h1{{font-size:clamp(2.8rem,15vw,4.6rem)}}section{{padding:44px 0}}header span{{display:none}}}}@media print{{:root{{--bg:#fff;--text:#111827;--muted:#526071;--line:#d9e0e8}}body{{background:#fff}}body:before,button{{display:none}}.hero{{min-height:auto;padding:38px 0}}h1 span{{color:#111827;background:none}}.metric,.card,.quote,.actions,.warning{{box-shadow:none;backdrop-filter:none;break-inside:avoid}}}}
</style></head><body>
<header class="wrap"><b>CONVERSATION INTELLIGENCE</b><span>{date_range}</span><button onclick="window.print()">打印 / 存为 PDF</button></header>
<main><section class="wrap hero"><div class="eyebrow">Privacy-safe full review</div><h1><span>{title}</span></h1><p class="sub">{subtitle}</p><div class="date">{date_range}</div></section>
<section class="wrap"><h2>关键数字</h2><div class="metrics">{metric_html}</div></section>
<section class="wrap"><article class="quote"><div class="eyebrow">Core thesis</div><p>{thesis}</p></article></section>
<section class="wrap"><h2>核心洞察</h2><div class="grid">{''.join(section_html)}</div></section>
<section class="wrap"><h2>下一步</h2><div class="actions">{action_html or '<div class="action"><span>暂无明确行动项</span><b>—</b></div>'}</div>{warning_html}</section></main>
<footer><div class="wrap">数据边界：{data_note}<br>本报告不包含密钥、wxid、数据库路径或完整聊天原文。</div></footer>
</body></html>"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    raw = args.input.read_text(encoding="utf-8")
    validate_safe(raw)
    data = json.loads(raw)
    validate_schema(data)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(data), encoding="utf-8")
    print(json.dumps({"ok": True, "sections": len(data.get("sections", [])), "actions": len(data.get("actions", []))}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
