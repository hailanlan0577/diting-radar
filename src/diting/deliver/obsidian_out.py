from __future__ import annotations
import os, time
from diting.models import Report
from diting.deliver import LENS_LABEL

def _frontmatter(date: str) -> str:
    return (f"---\ntitle: {date} 谛听情报\ntype: note\nstatus: inbox\n"
            f"created: {date}\nlast_updated: {date}\n---\n\n# {date} 谛听情报\n")

def _section(report: Report, time_str: str) -> str:
    label = LENS_LABEL.get(report.lens, report.lens)
    lines = [f"\n## {time_str} {label}\n"]
    for it in report.items:
        lines.append(f"### [{it.title}]({it.url})")
        lines.append(f"- {it.one_liner}")
        lines.append(f"- **为什么对你重要**：{it.why_it_matters}")
        lines.append(f"- 来源：{it.source}\n")
    if report.is_empty():
        lines.append("_今天这块没值得看的。_\n")
    for n in report.notes:
        if n != "今天这块没值得看的":
            lines.append(f"> 注：{n}\n")
    return "\n".join(lines)

def write_report_to_inbox(report: Report, inbox_dir: str, now_ts: float) -> str:
    os.makedirs(inbox_dir, exist_ok=True)
    lt = time.localtime(now_ts)
    date = time.strftime("%Y-%m-%d", lt); time_str = time.strftime("%H:%M", lt)
    path = os.path.join(inbox_dir, f"{date} 谛听情报.md")
    with open(path, "a", encoding="utf-8") as f:
        if f.tell() == 0:
            f.write(_frontmatter(date))
        f.write(_section(report, time_str))
    return path
