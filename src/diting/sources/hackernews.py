from __future__ import annotations
import httpx
from diting.models import Candidate

def search_hn(query: str, max_results: int = 5, *, get=httpx.get) -> list[Candidate]:
    try:
        resp = get("https://hn.algolia.com/api/v1/search",
                   params={"query": query, "tags": "story", "hitsPerPage": max_results})
        resp.raise_for_status()
        hits = resp.json().get("hits", [])
    except Exception:
        return []
    out: list[Candidate] = []
    for h in hits:
        title = (h.get("title") or "").strip()
        url = h.get("url") or (
            f"https://news.ycombinator.com/item?id={h['objectID']}" if h.get("objectID") else ""
        )
        if title and url:
            out.append(Candidate(title=title, url=url, summary="", source="hackernews"))
    return out
