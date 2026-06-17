# src/diting/synthesize.py
from __future__ import annotations
from diting.models import Candidate, Interests, RankedItem, Report

_SYSTEM = (
    "你是用户的私人技术情报员（precision-first，宁缺毋滥）。从候选里挑出真正值得他看的，"
    "排序，并为每条写：one_liner（一句话摘要）、why_it_matters（为什么对**他**重要——"
    "尽量关联到他最近做的事/卡点）。不够格的直接不要。**绝不硬凑**，宁可全部舍弃。"
    '严格输出 JSON：{"items": [{"url","title","one_liner","why_it_matters"}]}'
)

def synthesize(client, lens: str, date: str, candidates: list[Candidate],
               interests: Interests, notes: list[str] = []) -> Report:
    notes = list(notes)
    items: tuple[RankedItem, ...] = ()
    if candidates:
        ctx = {"topics": list(interests.topics), "open_loops": list(interests.open_loops),
               "candidates": [{"url": c.url, "title": c.title, "summary": c.summary[:300],
                               "source": c.source} for c in candidates]}
        data = client.complete_json([
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": str(ctx)},
        ])
        by_url = {c.url: c for c in candidates}
        items = tuple(
            RankedItem(title=it.get("title", ""), url=it.get("url", ""),
                       one_liner=it.get("one_liner", ""), why_it_matters=it.get("why_it_matters", ""),
                       source=by_url.get(it.get("url", ""), Candidate("", "", "", "?")).source, lens=lens)
            for it in data.get("items", []) if it.get("url")
        )
    if not items:
        notes.insert(0, "今天这块没值得看的")
    return Report(lens=lens, date=date, items=items, notes=tuple(notes))
