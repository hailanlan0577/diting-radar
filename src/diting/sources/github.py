# src/diting/sources/github.py
from __future__ import annotations
import httpx
from diting.models import Candidate

def search_github_repos(query: str, max_results: int = 5, *, get=httpx.get,
                        token: str | None = None) -> list[Candidate]:
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        resp = get("https://api.github.com/search/repositories",
                   params={"q": query, "sort": "updated", "order": "desc",
                           "per_page": max_results}, headers=headers)
        resp.raise_for_status()
        items = resp.json().get("items", [])
    except Exception:
        return []
    out: list[Candidate] = []
    for it in items:
        name = it.get("full_name") or ""
        url = it.get("html_url") or ""
        if name and url:
            out.append(Candidate(title=name, url=url,
                                 summary=it.get("description") or "", source="github"))
    return out
