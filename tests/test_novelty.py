from diting.models import Candidate
from diting.state import StateStore
from diting.novelty import filter_unpushed, judge_novelty

def _c(u): return Candidate(f"t{u}", u, "", "src")

def test_filter_unpushed(tmp_path):
    store = StateStore(str(tmp_path)); store.mark_pushed("http://old", "x")
    out = filter_unpushed([_c("http://old"), _c("http://new")], store)
    assert [c.url for c in out] == ["http://new"]

def test_judge_novelty_keeps_subset():
    class FakeClient:
        def complete_json(self, messages, **kw):
            return {"novel_urls": ["http://a"]}
    out = judge_novelty(FakeClient(), [_c("http://a"), _c("http://b")], known_context="ctx")
    assert [c.url for c in out] == ["http://a"]

def test_judge_novelty_empty_input_short_circuits():
    class Boom:
        def complete_json(self, *a, **k): raise AssertionError("不该调 LLM")
    assert judge_novelty(Boom(), [], "ctx") == []

def test_judge_novelty_uses_body_when_present():
    captured = {}
    class C:
        def complete_json(self, messages, **kw):
            captured["user"] = messages[1]["content"]
            return {"novel_urls": ["http://a"]}
    cands = [Candidate("t", "http://a", "短摘要", "arxiv", body="完整正文关键词ZYX")]
    judge_novelty(C(), cands, "ctx")
    assert "完整正文关键词ZYX" in captured["user"]
