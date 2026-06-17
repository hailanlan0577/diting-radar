import os, time
from diting.models import Candidate
from diting.config import Config
from diting.state import StateStore
from diting.runner import run_report

_NOW = time.mktime(time.strptime("2026-06-18 10:00", "%Y-%m-%d %H:%M"))

class RouterClient:
    """按 system prompt 关键词返回不同 JSON，模拟 DeepSeek 各步。"""
    def complete_json(self, messages, **kw):
        sysmsg = messages[0]["content"]
        if "兴趣" in sysmsg or "提炼" in sysmsg:
            return {"topics": ["LoRA"], "entities": ["MLX"], "open_loops": [], "decisions": []}
        if "queries" in sysmsg or "检索串" in sysmsg:
            return {"queries": ["lora finetune 2026"]}
        if "novel" in sysmsg or "新的" in sysmsg:
            return {"novel_urls": ["http://a"]}
        if "情报员" in sysmsg:
            return {"items": [{"url": "http://a", "title": "论文A",
                               "one_liner": "一句话", "why_it_matters": "和你 LoRA 相关"}]}
        return {}

def _cfg(tmp_path) -> Config:
    recs = tmp_path / "recs"; recs.mkdir()
    (recs / "today.md").write_text("今天搞 LoRA 微调", encoding="utf-8")
    return Config("http://x/v1", "deepseek-v4-pro", "DS", str(recs), 5,
                  "http://sx", "GH", str(tmp_path / "inbox"), "me", str(tmp_path / "state"))

def test_run_report_end_to_end(tmp_path):
    cfg = _cfg(tmp_path)
    os.utime(os.path.join(cfg.session_records_dir, "today.md"), (_NOW, _NOW))
    store = StateStore(cfg.state_dir)
    fake_sources = {"arxiv": lambda q: [Candidate("论文A", "http://a", "abs", "arxiv")]}
    sent = {}
    def fake_feishu(argv, **kw):
        sent["argv"] = argv
        class R: returncode = 0
        return R()
    report = run_report("research", cfg, RouterClient(), store,
                        now_ts=_NOW, sources=fake_sources, feishu_run=fake_feishu)
    assert not report.is_empty() and report.items[0].url == "http://a"
    # Obsidian 落档
    assert os.path.exists(os.path.join(cfg.vault_inbox_dir, "2026-06-18 谛听情报.md"))
    # 飞书发了
    assert "论文A" in " ".join(sent["argv"])
    # 已推送去重生效：再跑一次，该 URL 被 filter_unpushed 砍掉 → 空报告
    report2 = run_report("research", cfg, RouterClient(), store,
                         now_ts=_NOW, sources=fake_sources, feishu_run=fake_feishu)
    assert report2.is_empty()
