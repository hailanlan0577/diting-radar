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
