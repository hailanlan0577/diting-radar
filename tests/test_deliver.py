import os, time
from diting.models import RankedItem, Report
from diting.deliver.obsidian_out import write_report_to_inbox
from diting.deliver.feishu import format_feishu_message, send_to_feishu

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
    assert captured["argv"][:5] == ["lark-cli", "im", "+messages-send", "--user-id", "me"]
    assert captured["argv"][5] == "--text"
    assert "论文A" in captured["argv"][6]
