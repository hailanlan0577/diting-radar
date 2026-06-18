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
    """loops 镜头：系统 prompt 应区分解法与反对证据，且 lens 字段正确；decisions 应在 LLM ctx 中。"""
    import json

    class FakeClient:
        def __init__(self): self.seen = None
        def complete_json(self, messages, **kw):
            self.seen = messages
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
    sys_content = client.seen[0]["content"]
    assert sys_content is not None
    assert any(kw in sys_content for kw in ("解法", "反对", "counter", "decision", "decisions")), \
        f"loops 系统 prompt 未区分解法/反对证据: {sys_content!r}"

    # 用户 ctx 应包含 decisions 字段且传入了 LLM
    user_ctx = json.loads(client.seen[1]["content"])
    assert "decisions" in user_ctx, "ctx 缺少 decisions 字段"
    assert "选用 Qdrant 作为向量数据库" in user_ctx["decisions"], \
        f"decisions 未在 ctx 中: {user_ctx.get('decisions')}"

def test_synthesize_feeds_body_when_present():
    captured = {}
    class C:
        def complete_json(self, messages, **kw):
            captured["user"] = messages[1]["content"]
            return {"items": []}
    cands = [Candidate("t", "http://a", "短摘要", "arxiv", body="正文独有词WQX")]
    synthesize(C(), "research", "2026-06-18", cands, Interests((), (), (), ()))
    assert "正文独有词WQX" in captured["user"]

def test_synthesize_matches_source_despite_trailing_slash():
    """候选 url 无斜杠，LLM 回的 url 带斜杠，应仍能匹配到正确 source，不回退 '?'。"""
    class C:
        def complete_json(self, messages, **kw):
            return {"items": [{"url": "http://a/", "title": "t",
                               "one_liner": "x", "why_it_matters": "y"}]}
    cands = [Candidate("t", "http://a", "s", "arxiv")]   # 候选无斜杠，LLM 回带斜杠
    rep = synthesize(C(), "research", "2026-06-18", cands, Interests((), (), (), ()))
    assert rep.items[0].source == "arxiv"   # 不再回退 "?"
