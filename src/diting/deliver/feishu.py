from __future__ import annotations
import subprocess
from diting.models import Report, DigReport
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
    # 以机器人身份发：用户身份发给自己 open_id 会落进飞书不显示的"自聊"，机器人私聊才会弹出+提醒
    argv = ["lark-cli", "im", "+messages-send", "--as", "bot", "--user-id", target, "--text", msg]
    try:
        return run(argv, capture_output=True).returncode == 0
    except Exception:
        return False

def format_dig_notice(report: DigReport, doc_path: str) -> str:
    return (f"【谛听 · 🔬 深挖 · {report.date}】{report.topic}\n"
            f"{report.one_liner}\n"
            f"📄 {doc_path}（{report.source_count} 篇来源）")


def send_dig_notice(report: DigReport, target: str, doc_path: str, *, run=subprocess.run) -> bool:
    msg = format_dig_notice(report, doc_path)
    # 同 send_to_feishu：机器人身份私聊才会弹出+提醒
    argv = ["lark-cli", "im", "+messages-send", "--as", "bot", "--user-id", target, "--text", msg]
    try:
        return run(argv, capture_output=True).returncode == 0
    except Exception:
        return False
