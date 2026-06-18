from diting.sources.websearch import search_web, extract_main_text
from diting.models import Candidate


class _Resp:
    def __init__(self, payload):
        self._p = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._p


def test_search_web_parses():
    payload = {"results": [{"title": "T", "url": "http://u", "content": "摘要"}]}
    out = search_web("q", "http://sx:8080", get=lambda *a, **k: _Resp(payload))
    assert out[0].title == "T" and out[0].source == "websearch" and out[0].summary == "摘要"


def test_search_web_falls_back_when_searxng_empty():
    empty = _Resp({"results": []})
    called = {}
    def fake_search(q, max_results=5):
        called["q"] = q
        return [Candidate("X", "http://x", "", "websearch")]
    out = search_web("rag", "http://sx", get=lambda *a, **k: empty, search_fn=fake_search)
    assert called["q"] == "rag" and out[0].url == "http://x"


def test_search_web_no_fallback_when_searxng_has_results():
    payload = _Resp({"results": [{"title": "T", "url": "http://u", "content": "c"}]})
    def fake_search(q, max_results=5):
        raise AssertionError("有结果就不该兜底")
    out = search_web("q", "http://sx", get=lambda *a, **k: payload, search_fn=fake_search)
    assert out[0].url == "http://u"


def test_extract_main_text():
    html = "<html><body><article><p>核心正文内容很长很长很长。</p></article></body></html>"
    assert "核心正文" in extract_main_text(html)
