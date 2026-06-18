import json
from diting.models import Interests
from diting.query import generate_queries

class _FakeClient:
    def __init__(self): self.seen = None
    def complete_json(self, messages, **kw):
        self.seen = messages
        return {"queries": ["fine-grained retrieval LoRA 2026", "MLX LoRA finetune best practice"]}

def test_generate_research_queries():
    c = _FakeClient()
    qs = generate_queries(c, "research",
                          Interests(("LoRA 微调",), ("MLX",), (), ("阈值改 0.3",)), {"topics": ["细粒度检索"]})
    assert len(qs) == 2 and "LoRA" in qs[0]
    assert "research" in c.seen[0]["content"].lower() or "论文" in c.seen[0]["content"]

def test_queries_capped(monkeypatch):
    c = _FakeClient()
    c.complete_json = lambda m, **k: {"queries": [f"q{i}" for i in range(20)]}
    assert len(generate_queries(c, "research", Interests((), (), (), ()), {}, max_queries=6)) == 6

def test_generate_loops_queries():
    """loops 镜头：系统 prompt 包含反方关键词，ctx 传入 decisions。"""
    class _LoopsClient:
        def __init__(self): self.seen = None
        def complete_json(self, messages, **kw):
            self.seen = messages
            return {"queries": ["Qdrant drawbacks", "Qdrant vs alternatives", "open loop best practice"]}

    c = _LoopsClient()
    interests = Interests(
        topics=("向量检索",),
        entities=("Qdrant",),
        open_loops=("embedding 方案未定",),
        decisions=("选用 Qdrant 作为向量数据库",),
    )
    qs = generate_queries(c, "loops", interests, {})
    # 返回值是列表
    assert isinstance(qs, list)
    # 系统 prompt 应包含反方/唱反调类词汇
    sys_content = c.seen[0]["content"]
    assert any(kw in sys_content for kw in ("反方", "唱反调", "drawbacks", "loops")), \
        f"loops 系统 prompt 缺少反方关键词: {sys_content!r}"
    # 用户 ctx 应包含 decisions 字段
    user_ctx = json.loads(c.seen[1]["content"])
    assert "decisions" in user_ctx, "ctx 缺少 decisions 字段"
    assert "选用 Qdrant 作为向量数据库" in user_ctx["decisions"]
    # open_loops 也应在 ctx 中
    assert "open_loops" in user_ctx
