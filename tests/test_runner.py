import os, time
from unittest.mock import patch
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
        raise ValueError(f"RouterClient: unexpected prompt: {sysmsg[:80]}")

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


def test_run_report_degrades_when_llm_fails(tmp_path):
    cfg = _cfg(tmp_path)
    import os
    os.utime(os.path.join(cfg.session_records_dir, "today.md"), (_NOW, _NOW))
    store = StateStore(cfg.state_dir)
    class BoomClient:
        def complete_json(self, messages, **kw):
            raise RuntimeError("api down")
    sent = {}
    def fake_feishu(argv, **kw):
        sent["argv"] = argv
        class R: returncode = 0
        return R()
    report = run_report("research", cfg, BoomClient(), store,
                        now_ts=_NOW, sources={"arxiv": lambda q: []}, feishu_run=fake_feishu)
    assert report.is_empty()
    assert any("DeepSeek" in n for n in report.notes)
    assert "argv" in sent  # degraded alert WAS sent to Feishu


def test_run_report_empty_skips_feishu(tmp_path):
    cfg = _cfg(tmp_path)
    import os
    os.utime(os.path.join(cfg.session_records_dir, "today.md"), (_NOW, _NOW))
    store = StateStore(cfg.state_dir)
    class EmptyClient:
        def complete_json(self, messages, **kw):
            sysmsg = messages[0]["content"]
            if "兴趣" in sysmsg or "提炼" in sysmsg:
                return {"topics": ["LoRA"], "entities": [], "open_loops": [], "decisions": []}
            if "queries" in sysmsg or "检索串" in sysmsg:
                return {"queries": ["q"]}
            if "novel" in sysmsg or "新的" in sysmsg:
                return {"novel_urls": []}
            if "情报员" in sysmsg:
                return {"items": []}
            return {}
    sent = {}
    def fake_feishu(argv, **kw):
        sent["argv"] = argv
        class R: returncode = 0
        return R()
    report = run_report("research", cfg, EmptyClient(), store,
                        now_ts=_NOW, sources={"arxiv": lambda q: []}, feishu_run=fake_feishu)
    assert report.is_empty()
    assert "argv" not in sent  # no Feishu spam on a normal-empty report


class TrendsClient:
    """LLM client for trends lens: needs distill, judge_novelty, synthesize (no query-gen)."""
    def complete_json(self, messages, **kw):
        sysmsg = messages[0]["content"]
        if "兴趣" in sysmsg or "提炼" in sysmsg:
            return {"topics": ["MLX"], "entities": [], "open_loops": [], "decisions": []}
        if "novel" in sysmsg or "新的" in sysmsg:
            return {"novel_urls": ["https://github.com/a/b/releases/tag/v1"]}
        if "情报员" in sysmsg:
            return {"items": [{"url": "https://github.com/a/b/releases/tag/v1",
                               "title": "a/b 出新版 v1",
                               "one_liner": "大改进", "why_it_matters": "你在用 a/b"}]}
        raise ValueError(f"TrendsClient: unexpected prompt: {sysmsg[:80]}")


def _cfg_trends(tmp_path) -> Config:
    recs = tmp_path / "recs"; recs.mkdir()
    (recs / "today.md").write_text("今天在研究 MLX 框架", encoding="utf-8")
    return Config("http://x/v1", "deepseek-v4-pro", "DS", str(recs), 5,
                  "http://sx", "GH", str(tmp_path / "inbox"), "me", str(tmp_path / "state"))


def test_trends_uses_release_watcher(tmp_path):
    """trends 镜头：有新版 → 报告非空且投递飞书且快照投递后推进；无新版 → 空报告不刷飞书不推进快照。"""
    cfg = _cfg_trends(tmp_path)
    os.utime(os.path.join(cfg.session_records_dir, "today.md"), (_NOW, _NOW))

    fake_candidate = Candidate(
        title="a/b 出新版 v1",
        url="https://github.com/a/b/releases/tag/v1",
        summary="大改进",
        source="github_release",
    )

    sent = {}
    def fake_feishu(argv, **kw):
        sent["argv"] = argv
        class R: returncode = 0
        return R()

    # --- scenario 1: new release → non-empty report + Feishu called + snapshot advanced post-delivery ---
    store1 = StateStore(cfg.state_dir)
    # pre-load profile with repos so fatten_profile preserves them
    store1.save_profile({"stack": [], "tools": [], "topics": [], "repos": ["a/b"]})

    with patch("diting.runner.check_repo_release", return_value=([fake_candidate], "v1")) as mock_check:
        report = run_report("trends", cfg, TrendsClient(), store1,
                            now_ts=_NOW, feishu_run=fake_feishu)

    assert not report.is_empty(), "新版应产生非空报告"
    assert "argv" in sent, "飞书应被调用"
    mock_check.assert_called_once_with("a/b", store1, token=None)
    # snapshot must be advanced AFTER successful delivery
    assert store1.get_seen_version("a/b") == "v1", "快照应在投递成功后推进"

    # --- scenario 2: no new version → empty report, Feishu NOT called, snapshot NOT advanced ---
    sent2 = {}
    def fake_feishu2(argv, **kw):
        sent2["argv"] = argv
        class R: returncode = 0
        return R()

    store2 = StateStore(str(tmp_path / "state2"))
    store2.save_profile({"stack": [], "tools": [], "topics": [], "repos": ["a/b"]})

    with patch("diting.runner.check_repo_release", return_value=([], None)):
        report2 = run_report("trends", cfg, TrendsClient(), store2,
                             now_ts=_NOW, feishu_run=fake_feishu2)

    assert report2.is_empty(), "无新版应产生空报告"
    assert "argv" not in sent2, "无新版不应发飞书"
    assert store2.get_seen_version("a/b") is None, "无新版不应推进快照"
