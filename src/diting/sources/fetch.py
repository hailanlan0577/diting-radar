# src/diting/sources/fetch.py
from __future__ import annotations
from typing import Callable
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
