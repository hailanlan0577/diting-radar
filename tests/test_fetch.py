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


def test_ddg_html_uses_httpx_with_proxy(monkeypatch):
    from diting.sources import fetch

    class _Resp:
        text = _DDG

        def raise_for_status(self):
            return None

    seen = {}

    def fake_get(url, **kwargs):
        seen["url"] = url
        seen["kwargs"] = kwargs
        return _Resp()

    monkeypatch.setattr(fetch.httpx, "get", fake_get)
    monkeypatch.setattr(fetch, "_proxy", lambda: "http://127.0.0.1:7890")

    html = fetch._ddg_html("OpenAI Agents SDK", 3, 30)

    assert "Cool Paper" in html
    assert seen["url"].startswith("https://html.duckduckgo.com/html/?q=")
    assert seen["kwargs"]["proxy"] == "http://127.0.0.1:7890"
    assert seen["kwargs"]["follow_redirects"] is True


def test_quiet_scrapling_forces_error_level_even_after_reset():
    """_quiet_scrapling() 应能在 logger 被设回 INFO 后压回 ERROR（模拟 scrapling setup_logger 行为）。"""
    import logging
    from diting.sources import fetch
    logging.getLogger("scrapling").setLevel(logging.INFO)  # 模拟 scrapling setup_logger 设回 INFO
    fetch._quiet_scrapling()
    assert logging.getLogger("scrapling").level == logging.ERROR


def test_quiet_scrapling_drops_ssrf_noise_keeps_real_errors():
    """mihomo 拦广告域→302 到 127.0.0.1→curl SSRF 防护拒绝 的 ERROR 是良性噪音
    （抓取失败已由 fetch_text/search_engine 兜底返空），应被过滤；其它真错误保留。"""
    import logging
    from diting.sources import fetch
    fetch._quiet_scrapling()
    logger = logging.getLogger("scrapling")

    def rec(msg):
        return logging.LogRecord("scrapling", logging.ERROR, __file__, 0, msg, None, None)

    # SSRF 噪音被丢（filter 返回 False = 不处理）
    assert logger.filter(rec(
        "Failed after 3 attempts: Failed to perform, curl: (7) Redirect to internal "
        "IP 127.0.0.1 rejected (SSRF protection).")) is False
    # 其它真错误保留
    assert logger.filter(rec("some other genuine scrapling error")) is True


def test_quiet_scrapling_filter_is_idempotent():
    """多次调用不重复加 filter（_quiet_scrapling 每次抓取都会被调）。"""
    import logging
    from diting.sources import fetch
    from diting.sources.fetch import _DropSSRFNoise
    fetch._quiet_scrapling()
    fetch._quiet_scrapling()
    n = sum(isinstance(f, _DropSSRFNoise) for f in logging.getLogger("scrapling").filters)
    assert n == 1
