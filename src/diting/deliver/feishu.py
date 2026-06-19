from __future__ import annotations
import subprocess
import sys
from diting.models import Report, DigReport
from diting.deliver import LENS_LABEL


def _run_lark(argv, run) -> bool:
    """跑 lark-cli 发送；失败/异常时打印到 stderr——不静默吞错误，
    让 launchd 缺 PATH（找不到 lark-cli）等问题能在 cron 日志里立刻看到。"""
    try:
        proc = run(argv, capture_output=True)
    except Exception as e:
        print(f"[feishu] 发送异常（lark-cli 找不到或调用失败）：{e}", file=sys.stderr)
        return False
    if proc.returncode != 0:
        err = getattr(proc, "stderr", b"") or b""
        if isinstance(err, (bytes, bytearray)):
            err = err.decode("utf-8", "replace")
        print(f"[feishu] 发送失败 returncode={proc.returncode}：{str(err)[:500]}", file=sys.stderr)
        return False
    return True

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
    return _run_lark(argv, run)

def format_dig_notice(report: DigReport, doc_path: str) -> str:
    return (f"【谛听 · 🔬 深挖 · {report.date}】{report.topic}\n"
            f"{report.one_liner}\n"
            f"📄 {doc_path}（{report.source_count} 篇来源）")


def send_dig_notice(report: DigReport, target: str, doc_path: str, *, run=subprocess.run) -> bool:
    msg = format_dig_notice(report, doc_path)
    # 同 send_to_feishu：机器人身份私聊才会弹出+提醒
    argv = ["lark-cli", "im", "+messages-send", "--as", "bot", "--user-id", target, "--text", msg]
    return _run_lark(argv, run)
