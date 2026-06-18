from __future__ import annotations
import xml.etree.ElementTree as ET
import httpx
from diting.models import Candidate

_NS = {"a": "http://www.w3.org/2005/Atom"}

def search_arxiv(query: str, max_results: int = 5, *, get=httpx.get) -> list[Candidate]:
    try:
        resp = get("https://export.arxiv.org/api/query",
                   params={"search_query": f"all:{query}", "max_results": max_results,
                           "sortBy": "submittedDate", "sortOrder": "descending"})
        resp.raise_for_status()
        root = ET.fromstring(resp.text)
    except Exception:
        return []
    out: list[Candidate] = []
    for e in root.findall("a:entry", _NS):
        title = (e.findtext("a:title", default="", namespaces=_NS) or "").strip()
        url = (e.findtext("a:id", default="", namespaces=_NS) or "").strip()
        summary = (e.findtext("a:summary", default="", namespaces=_NS) or "").strip()
        if title and url:
            out.append(Candidate(title=title, url=url, summary=summary, source="arxiv"))
    return out
