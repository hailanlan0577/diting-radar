from diting.sources.fetch import fetch_text

_HTML = "<html><body><article><p>这是一篇很长很长的核心正文内容。</p></article></body></html>"

def test_fetch_text_extracts_body():
    out = fetch_text("http://x", fetcher=lambda url, stealthy, timeout_ms: _HTML)
    assert "核心正文" in out

def test_fetch_text_returns_empty_on_exception():
    def boom(url, stealthy, timeout_ms): raise RuntimeError("network down")
    assert fetch_text("http://x", fetcher=boom) == ""

def test_fetch_text_returns_empty_on_blank_html():
    assert fetch_text("http://x", fetcher=lambda *a, **k: "") == ""

def test_fetch_text_passes_stealthy_flag():
    seen = {}
    def spy(url, stealthy, timeout_ms): seen["stealthy"] = stealthy; return _HTML
    fetch_text("http://x", stealthy=True, fetcher=spy)
    assert seen["stealthy"] is True
