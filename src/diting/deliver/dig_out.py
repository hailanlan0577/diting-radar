# src/diting/deliver/dig_out.py
from __future__ import annotations
import os
import time
from diting.models import DigReport


def _frontmatter(report: DigReport) -> str:
    return (f"---\ntitle: {report.date} 谛听深挖 · {report.topic}\n"
            f"type: reference-manual\nstatus: active\n"
            f"created: {report.date}\nlast_updated: {report.date}\n---\n\n"
            f"# {report.topic}\n\n"
            f"> 谛听自动深挖 · {report.date} · {report.source_count} 篇来源\n\n")


def write_dig_to_vault(report: DigReport, dig_vault_dir: str, now_ts: float) -> str:
    os.makedirs(dig_vault_dir, exist_ok=True)
    date = time.strftime("%Y-%m-%d", time.localtime(now_ts))
    safe_topic = report.topic.replace("/", "／").replace("\\", "＼").strip()
    path = os.path.join(dig_vault_dir, f"{date} 谛听深挖 {safe_topic}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(_frontmatter(report))
        f.write(report.markdown)
        f.write("\n")
    return path
