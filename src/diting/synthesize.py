# src/diting/synthesize.py
from __future__ import annotations
import json
from diting.models import Candidate, Interests, RankedItem, Report

_SYSTEM_RESEARCH = (
    "你是用户的私人技术情报员（precision-first，宁缺毋滥）。从候选里挑出真正值得他看的，"
    "排序，并为每条写：one_liner（一句话摘要）、why_it_matters（为什么对**他**重要——"
    "尽量关联到他最近做的事/卡点）。不够格的直接不要。**绝不硬凑**，宁可全部舍弃。"
    '严格输出 JSON：{"items": [{"url","title","one_liner","why_it_matters"}]}'
)

_SYSTEM_LOOPS = (
    "你是用户的私人技术情报员（precision-first，宁缺毋滥）。候选内容分两类："
    "（1）解法——帮助解决 open_loops 卡点的 how-to/best-practice；"
    "（2）反对证据——质疑用户 decisions 中某个决策的 drawbacks/failure/反例。"
    "为每条写：one_liner（一句话摘要）、why_it_matters——反对证据必须点名它质疑的是哪个 decision。"
    "不够格的直接不要。**绝不硬凑**，宁可全部舍弃。"
    '严格输出 JSON：{"items": [{"url","title","one_liner","why_it_matters"}]}'
)

_SYSTEM_BY_LENS: dict[str, str] = {
    "research": _SYSTEM_RESEARCH,
    "loops": _SYSTEM_LOOPS,
}

def synthesize(client, lens: str, date: str, candidates: list[Candidate],
               interests: Interests, notes: list[str] = []) -> Report:
    def _norm(u: str) -> str:
        return (u or "").rstrip("/")

    notes = list(notes)
    items: tuple[RankedItem, ...] = ()
    system = _SYSTEM_BY_LENS.get(lens, _SYSTEM_RESEARCH)
    if candidates:
        ctx = {"topics": list(interests.topics), "open_loops": list(interests.open_loops),
               "decisions": list(interests.decisions),
               "candidates": [{"url": c.url, "title": c.title, "summary": (c.body or c.summary)[:600],
                               "source": c.source} for c in candidates]}
        data = client.complete_json([
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(ctx, ensure_ascii=False)},
        ])
        by_url = {_norm(c.url): c for c in candidates}
        items = tuple(
            RankedItem(title=it.get("title", ""), url=it.get("url", ""),
                       one_liner=it.get("one_liner", ""), why_it_matters=it.get("why_it_matters", ""),
                       source=by_url.get(_norm(it.get("url", "")), Candidate("", "", "", "?")).source, lens=lens)
            for it in data.get("items", []) if it.get("url")
        )
    if not items:
        notes.insert(0, "今天这块没值得看的")
    return Report(lens=lens, date=date, items=items, notes=tuple(notes))
