from diting.sources.websearch import search_web, extract_main_text


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


def test_extract_main_text():
    html = "<html><body><article><p>核心正文内容很长很长很长。</p></article></body></html>"
    assert "核心正文" in extract_main_text(html)
