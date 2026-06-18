from diting.models import Candidate, Interests, Report
from diting.synthesize import synthesize

_INT = Interests(("LoRA",), ("MLX",), (), ())

def test_synthesize_builds_ranked_items():
    class FakeClient:
        def complete_json(self, messages, **kw):
            return {"items": [{"url": "http://a", "title": "论文A", "one_liner": "一句话",
                               "why_it_matters": "和你昨天的 LoRA 微调直接相关"}]}
    cands = [Candidate("论文A", "http://a", "abs", "arxiv")]
    r = synthesize(FakeClient(), "research", "2026-06-18", cands, _INT)
    assert isinstance(r, Report) and not r.is_empty()
    assert r.items[0].why_it_matters.startswith("和你昨天")
    assert r.items[0].lens == "research"

def test_synthesize_empty_is_honest():
    class FakeClient:
        def complete_json(self, messages, **kw): return {"items": []}
    r = synthesize(FakeClient(), "research", "2026-06-18", [], _INT, notes=["github 没取到"])
    assert r.is_empty()
    assert any("没值得看" in n for n in r.notes)
    assert "github 没取到" in r.notes

def test_synthesize_loops_lens_uses_loops_system_prompt():
    """loops 镜头：系统 prompt 应区分解法与反对证据，且 lens 字段正确。"""
    class FakeClient:
        def __init__(self): self.seen_sys = None
        def complete_json(self, messages, **kw):
            self.seen_sys = messages[0]["content"]
            return {"items": [{"url": "http://b", "title": "Qdrant pitfalls",
                               "one_liner": "Qdrant 的常见坑",
                               "why_it_matters": "质疑你选 Qdrant 的决策"}]}

    client = FakeClient()
    interests = Interests(
        topics=("向量检索",),
        entities=("Qdrant",),
        open_loops=("embedding 方案未定",),
        decisions=("选用 Qdrant 作为向量数据库",),
    )
    cands = [Candidate("Qdrant pitfalls", "http://b", "some pitfalls", "hn")]
    r = synthesize(client, "loops", "2026-06-18", cands, interests)

    # Report lens 字段正确
    assert r.lens == "loops"
    assert not r.is_empty()
    assert r.items[0].lens == "loops"

    # 系统 prompt 应包含区分解法/反对证据相关词汇
    sys_content = client.seen_sys
    assert sys_content is not None
    assert any(kw in sys_content for kw in ("解法", "反对", "counter", "decision", "decisions")), \
        f"loops 系统 prompt 未区分解法/反对证据: {sys_content!r}"
