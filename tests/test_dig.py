import time
import types
import os
import yaml

import pytest

from diting.dig import generate_dig_queries, synthesize_dig
from diting.models import Candidate, DigReport
from diting.state import StateStore


class _Client:
    def __init__(self, payload):
        self._p = payload
        self.seen = None
    def complete_json(self, messages, **kw):
        self.seen = messages
        return self._p


def test_generate_dig_queries_returns_and_caps():
    c = _Client({"queries": ["q1", "q2", "q3", "q4", "q5", "q6", "q7"]})
    out = generate_dig_queries(c, "RAG 新做法", max_queries=6)
    assert out == ["q1", "q2", "q3", "q4", "q5", "q6"]
    # 话题被传给了模型
    assert "RAG 新做法" in c.seen[1]["content"]

def test_generate_dig_queries_empty_payload():
    assert generate_dig_queries(_Client({}), "X") == []


def test_synthesize_dig_builds_report():
    class C:
        def __init__(self): self.seen = None
        def complete_json(self, messages, **kw):
            self.seen = messages
            return {"one_liner": "RAG 有三种新路线", "markdown": "## 概览\n正文..."}
    c = C()
    cands = [Candidate("论文A", "http://a", "摘要", "websearch", body="正文关键词QWE")]
    r = synthesize_dig(c, "RAG 新做法", "2026-06-18", cands)
    assert isinstance(r, DigReport)
    assert r.markdown.startswith("## 概览") and r.one_liner == "RAG 有三种新路线"
    assert r.source_count == 1 and not r.is_empty()
    assert "正文关键词QWE" in c.seen[1]["content"]   # 喂了正文


def test_synthesize_dig_empty_candidates_returns_empty():
    class C:
        def complete_json(self, m, **k): raise AssertionError("空候选不该调模型")
    r = synthesize_dig(C(), "RAG", "2026-06-18", [])
    assert r.is_empty() and r.source_count == 0


# ── Task 8: run_dig 端到端测试 ─────────────────────────────────────────────────

_NOW = time.mktime(time.strptime("2026-06-18 20:00", "%Y-%m-%d %H:%M"))


def _dig_cfg(tmp_path, queue_topics=("RAG 新做法",)):
    recs = tmp_path / "recs"; recs.mkdir()
    (recs / "t.md").write_text("今天搞 RAG", encoding="utf-8")
    os.utime(str(recs / "t.md"), (_NOW, _NOW))
    qp = tmp_path / "dig_queue.yaml"
    qp.write_text(yaml.safe_dump(list(queue_topics), allow_unicode=True), encoding="utf-8")
    return types.SimpleNamespace(
        session_records_dir=str(recs), lookback_days=5,
        dig_queue_path=str(qp), dig_max_sources=12, known_antibot_domains=(),
        dig_vault_dir=str(tmp_path / "vault"), feishu_target="ou_me",
    )


class _DigRouter:
    def complete_json(self, messages, **kw):
        s = messages[0]["content"]
        if "兴趣" in s or "提炼" in s:
            return {"topics": ["RAG 新做法"], "entities": [], "open_loops": [], "decisions": []}
        if "queries" in s or "检索" in s:
            return {"queries": ["rag new 2026"]}
        if "研究员" in s:
            return {"one_liner": "三条路线", "markdown": "## 概览\n正文"}
        raise ValueError(f"unexpected prompt: {s[:60]}")


def test_run_dig_end_to_end(tmp_path):
    from diting.dig import run_dig
    cfg = _dig_cfg(tmp_path)
    store = StateStore(str(tmp_path / "state"))
    sent = {}
    def fake_feishu(argv, **kw):
        sent["argv"] = argv
        class R: returncode = 0
        return R()
    report = run_dig(cfg, _DigRouter(), store, now_ts=_NOW,
                     search=lambda q: [Candidate("论文A", "http://a", "摘要", "websearch")],
                     fetch=lambda url, *, stealthy=False: "正文内容",
                     feishu_run=fake_feishu)
    assert not report.is_empty() and report.topic == "RAG 新做法"
    assert any("谛听深挖 RAG 新做法" in f for f in os.listdir(cfg.dig_vault_dir))
    assert "argv" in sent                       # 飞书发了短通知
    assert store.is_dug("RAG 新做法")            # 投递成功后才登记


def test_run_dig_no_topic_skips_delivery(tmp_path):
    from diting.dig import run_dig
    cfg = _dig_cfg(tmp_path, queue_topics=[])
    store = StateStore(str(tmp_path / "state"))
    store.mark_dug("RAG 新做法")                 # 兴趣里唯一话题也挖过了 → 无题
    sent = {}
    def fake_feishu(argv, **kw):
        sent["argv"] = argv
        class R: returncode = 0
        return R()
    report = run_dig(cfg, _DigRouter(), store, now_ts=_NOW,
                     search=lambda q: [], fetch=lambda u, **k: "", feishu_run=fake_feishu)
    assert report.is_empty()
    assert "argv" not in sent                    # 无题不发飞书
