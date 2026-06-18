from diting.dig import generate_dig_queries, synthesize_dig
from diting.models import Candidate, DigReport


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
