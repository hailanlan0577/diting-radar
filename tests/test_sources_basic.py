from diting.sources.arxiv import search_arxiv
from diting.sources.hackernews import search_hn

class _Resp:
    def __init__(self, text="", payload=None): self.text = text; self._p = payload
    def raise_for_status(self): pass
    def json(self): return self._p

_ATOM = """<feed xmlns="http://www.w3.org/2005/Atom">
<entry><title>Better Retrieval</title><id>http://arxiv.org/abs/2606.0001</id>
<summary>A new method.</summary></entry></feed>"""

def test_arxiv_parses_atom():
    out = search_arxiv("retrieval", get=lambda *a, **k: _Resp(text=_ATOM))
    assert out[0].title == "Better Retrieval"
    assert out[0].url == "http://arxiv.org/abs/2606.0001"
    assert out[0].source == "arxiv"

def test_hn_parses_json():
    payload = {"hits": [{"title": "Show HN: X", "url": "http://x", "objectID": "1"}]}
    out = search_hn("x", get=lambda *a, **k: _Resp(payload=payload))
    assert out[0].title == "Show HN: X" and out[0].source == "hackernews"

def test_source_degrades_on_error():
    def boom(*a, **k): raise RuntimeError("net down")
    assert search_arxiv("x", get=boom) == []
    assert search_hn("x", get=boom) == []

def test_hn_skips_hit_without_url_or_objectid():
    payload = {"hits": [{"title": "no url no id"}]}
    out = search_hn("x", get=lambda *a, **k: _Resp(payload=payload))
    assert out == []
