import os, time
from diting.models import RankedItem, Report, DigReport
from diting.deliver.obsidian_out import write_report_to_inbox
from diting.deliver.feishu import format_feishu_message, send_to_feishu, format_dig_notice, send_dig_notice

_NOW = time.mktime(time.strptime("2026-06-18 10:05", "%Y-%m-%d %H:%M"))
_R = Report("research", "2026-06-18",
            (RankedItem("论文A", "http://a", "一句话", "和你 LoRA 相关", "arxiv", "research"),), ())

def test_obsidian_creates_then_appends(tmp_path):
    p = write_report_to_inbox(_R, str(tmp_path), _NOW)
    body = open(p, encoding="utf-8").read()
    assert "type: note" in body and "谛听情报" in body
    assert "🔭 科研雷达" in body and "http://a" in body and "和你 LoRA 相关" in body
    # 再投一份不应重建 frontmatter
    write_report_to_inbox(Report("research", "2026-06-18", (), ("今天这块没值得看的",)), str(tmp_path), _NOW)
    assert open(p, encoding="utf-8").read().count("type: note") == 1
    # 断言空报告追加诚实行
    body2 = open(p, encoding="utf-8").read()
    assert "今天这块没值得看的" in body2

def test_feishu_message_and_send():
    msg = format_feishu_message(_R)
    assert "论文A" in msg and "和你 LoRA 相关" in msg
    captured = {}
    def fake_run(argv, **kw):
        captured["argv"] = argv
        class R: returncode = 0
        return R()
    assert send_to_feishu(_R, "me", run=fake_run) is True
    assert captured["argv"][:7] == ["lark-cli", "im", "+messages-send", "--as", "bot", "--user-id", "me"]
    assert captured["argv"][7] == "--text"
    assert "论文A" in captured["argv"][8]

def test_feishu_send_failure_logs(capsys):
    """飞书发送失败(returncode≠0)时返回 False 并打印到 stderr（不再静默吞错误）。"""
    def fake_run(argv, **kw):
        class R:
            returncode = 1
            stderr = b"lark-cli: command not found"
        return R()
    assert send_to_feishu(_R, "me", run=fake_run) is False
    err = capsys.readouterr().err
    assert "[feishu]" in err and "失败" in err


def test_feishu_send_exception_logs(capsys):
    """lark-cli 找不到(抛异常)时返回 False 并打印原因（这正是 launchd 缺 PATH 的症状）。"""
    def boom(argv, **kw):
        raise FileNotFoundError("lark-cli")
    assert send_to_feishu(_R, "me", run=boom) is False
    assert "[feishu]" in capsys.readouterr().err


def test_format_dig_notice_has_topic_oneliner_path():
    r = DigReport(topic="RAG 新做法", date="2026-06-18", markdown="...", one_liner="三条路线", source_count=4)
    msg = format_dig_notice(r, "/vault/谛听深挖/2026-06-18 谛听深挖 RAG 新做法.md")
    assert "RAG 新做法" in msg and "三条路线" in msg
    assert "谛听深挖 RAG 新做法.md" in msg and "4" in msg

def test_send_dig_notice_uses_bot():
    r = DigReport(topic="RAG", date="2026-06-18", markdown="x", one_liner="y", source_count=1)
    captured = {}
    def fake_run(argv, **kw):
        captured["argv"] = argv
        class R: returncode = 0
        return R()
    ok = send_dig_notice(r, "ou_me", "/p.md", run=fake_run)
    assert ok is True
    assert "--as" in captured["argv"] and "bot" in captured["argv"]
    assert "ou_me" in captured["argv"]
