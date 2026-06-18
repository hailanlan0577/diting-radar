# src/diting/sources/fetch.py
from __future__ import annotations
from typing import Callable
import re
from urllib.parse import quote, unquote, urlparse, parse_qs
import trafilatura
from diting.models import Candidate


def _html_of(resp) -> str:
    """从 scrapling 返回对象里取出 HTML（0.4.9: html_content 是 TextHandler，str 子类）。"""
    for attr in ("html_content", "body", "content", "text"):
        v = getattr(resp, attr, None)
        if isinstance(v, str) and v:
            return str(v)          # 转成纯 str 喂 trafilatura（TextHandler 是 str 子类）
    return ""


def _scrapling_html(url: str, stealthy: bool, timeout_s: int) -> str:
    """默认抓取器：普通站点用 Fetcher（HTTP）；反爬站点用无头隐身 StealthyFetcher。
    分开 import：本机 StealthyFetcher 依赖（browserforge）当前 import 即报错，
    绝不能让它拖垮普通 HTTP 抓取路径（失败时由 fetch_text 兜底返空）。
    scrapling 0.4.9 实测：Fetcher.get 的 timeout 单位是『秒』。"""
    if stealthy:
        from scrapling.fetchers import StealthyFetcher
        return _html_of(StealthyFetcher().fetch(url, headless=True, timeout=timeout_s * 1000))
    from scrapling.fetchers import Fetcher
    return _html_of(Fetcher().get(url, timeout=timeout_s))


_DDG_HTML = "https://html.duckduckgo.com/html/"
_RESULT_RE = re.compile(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.S)


def _ddg_unwrap(href: str) -> str:
    """DDG html 版链接形如 //duckduckgo.com/l/?uddg=<urlencoded>，解出真实 url。"""
    if "uddg=" in href:
        full = href if href.startswith("http") else "https:" + href
        u = parse_qs(urlparse(full).query).get("uddg", [""])[0]
        return unquote(u)
    return href if href.startswith("http") else ""


def _ddg_html(query: str, max_results: int, timeout_s: int) -> str:
    from scrapling.fetchers import Fetcher    # 仅 Fetcher（HTTP），不碰 StealthyFetcher
    return _html_of(Fetcher().get(f"{_DDG_HTML}?q={quote(query)}", timeout=timeout_s))


def search_engine(query: str, *, max_results: int = 5,
                  serp_fetcher=None, timeout_s: int = 30) -> list[Candidate]:
    """抓搜索引擎结果作为 searxng 兜底。失败返 []（precision-first）。"""
    serp_fetcher = serp_fetcher or _ddg_html
    try:
        html = serp_fetcher(query, max_results, timeout_s)
    except Exception:
        return []
    out: list[Candidate] = []
    for m in _RESULT_RE.finditer(html or ""):
        url = _ddg_unwrap(m.group(1))
        title = re.sub(r"<[^>]+>", "", m.group(2)).strip()
        if url and title:
            out.append(Candidate(title=title, url=url, summary="", source="websearch"))
        if len(out) >= max_results:
            break
    return out


def fetch_text(url: str, *, stealthy: bool = False,
               fetcher: Callable[[str, bool, int], str] | None = None,
               timeout_s: int = 30) -> str:
    """抓 url 正文为纯文本。任何失败/空内容一律返回 ""，绝不抛出（precision-first）。"""
    fetcher = fetcher or _scrapling_html
    try:
        html = fetcher(url, stealthy, timeout_s)
    except Exception:
        return ""
    if not html:
        return ""
    return trafilatura.extract(html) or ""
