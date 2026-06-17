from __future__ import annotations
import subprocess
from diting.models import Report
from diting.deliver import LENS_LABEL

def format_feishu_message(report: Report) -> str:
    label = LENS_LABEL.get(report.lens, report.lens)
    head = f"【谛听 · {label} · {report.date}】"
    if report.is_empty():
        return head + "\n今天这块没值得看的。"
    blocks = [head]
    for it in report.items:
        blocks.append(f"• {it.title}\n  {it.one_liner}\n  为什么重要：{it.why_it_matters}\n  {it.url}")
    return "\n".join(blocks)

def send_to_feishu(report: Report, target: str, *, run=subprocess.run) -> bool:
    msg = format_feishu_message(report)
    argv = ["lark-cli", "im", "+messages-send", "--user-id", target, "--text", msg]
    try:
        return run(argv, capture_output=True).returncode == 0
    except Exception:
        return False
