# src/diting/deliver/project_out.py
from __future__ import annotations
import os
import re
from diting.models import Report


def _header(slug: str, date: str) -> str:
    return (f"---\ntitle: 谛听项目情报 · {slug}\ntype: progress-log\n"
            f"status: active\ncreated: {date}\nlast_updated: {date}\n---\n\n"
            f"# 谛听项目情报 · {slug}\n\n"
            f"> 谛听「项目雷达」镜头自动产出 · 只收和本项目直接相关的料 · 最新在最上\n\n")


def _section(report: Report) -> str:
    lines = [f"## {report.date}"]
    for it in report.items:
        lines.append(f"- [{it.title}]({it.url}) — {it.why_it_matters}")
    return "\n".join(lines) + "\n"


def write_project_intel(slug: str, report: Report, output_dir: str) -> str:
    """把一份 Report 滚动写进 output_dir/<slug>.md（最新日期小节在最上）。"""
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, f"{slug}.md")
    section = _section(report)
    if not os.path.exists(path):
        content = _header(slug, report.date) + section
    else:
        with open(path, "r", encoding="utf-8") as f:
            old = f.read()
        old = re.sub(r"(?m)^last_updated: .*$", f"last_updated: {report.date}", old, count=1)
        idx = old.find("\n## ")
        if idx == -1:
            content = old.rstrip() + "\n\n" + section
        else:
            content = old[:idx + 1] + section + "\n" + old[idx + 1:]
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path
