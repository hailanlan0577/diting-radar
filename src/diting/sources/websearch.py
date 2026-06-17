# src/diting/sources/websearch.py
from __future__ import annotations

import httpx
import trafilatura

from diting.models import Candidate


def search_web(
    query: str, searxng_url: str, max_results: int = 5, *, get=httpx.get
) -> list[Candidate]:
    try:
        resp = get(
            f"{searxng_url.rstrip('/')}/search",
            params={"q": query, "format": "json"},
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])[:max_results]
    except Exception:
        return []
    out: list[Candidate] = []
    for r in results:
        title = (r.get("title") or "").strip()
        url = r.get("url") or ""
        if title and url:
            out.append(
                Candidate(
                    title=title,
                    url=url,
                    summary=(r.get("content") or "").strip(),
                    source="websearch",
                )
            )
    return out


def extract_main_text(html: str) -> str:
    return trafilatura.extract(html) or ""
