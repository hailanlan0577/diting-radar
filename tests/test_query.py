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
