from diting.sources.fetch import fetch_text, search_engine

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


_DDG = (
    '<a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Farxiv.org%2Fabs%2F1234&rut=x">Cool Paper</a>'
    '<a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fgithub.com%2Ffoo%2Fbar">A Repo</a>'
)

_DDG_HREF_FIRST = (
    '<a href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.org%2Fx" class="result__a">Href First</a>'
)

def test_search_engine_parses_ddg():
    out = search_engine("rag", serp_fetcher=lambda q, n, t: _DDG)
    urls = [c.url for c in out]
    assert "https://arxiv.org/abs/1234" in urls
    assert out[0].source == "websearch" and out[0].title == "Cool Paper"

def test_search_engine_empty_on_exception():
    def boom(q, n, t): raise RuntimeError("network down")
    assert search_engine("rag", serp_fetcher=boom) == []

def test_search_engine_respects_max_results():
    out = search_engine("rag", max_results=1, serp_fetcher=lambda q, n, t: _DDG)
    assert len(out) == 1

def test_search_engine_href_before_class():
    """href 属性在 class 之前时，解析结果应与 class 在前一致。"""
    out = search_engine("x", serp_fetcher=lambda q, n, t: _DDG_HREF_FIRST)
    assert len(out) == 1
    assert out[0].url == "https://example.org/x"
    assert out[0].title == "Href First"


def test_quiet_scrapling_forces_error_level_even_after_reset():
    """_quiet_scrapling() 应能在 logger 被设回 INFO 后压回 ERROR（模拟 scrapling setup_logger 行为）。"""
    import logging
    from diting.sources import fetch
    logging.getLogger("scrapling").setLevel(logging.INFO)  # 模拟 scrapling setup_logger 设回 INFO
    fetch._quiet_scrapling()
    assert logging.getLogger("scrapling").level == logging.ERROR
