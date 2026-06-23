# src/diting/novelty.py
from __future__ import annotations
from diting.models import Candidate

def filter_unpushed(candidates: list[Candidate], store) -> list[Candidate]:
    return [c for c in candidates if not store.is_pushed(c.url)]

def filter_unpushed_project(candidates: list[Candidate], store, slug: str) -> list[Candidate]:
    return [c for c in candidates if not store.is_project_pushed(slug, c.url)]

_SYSTEM = (
    "你在帮用户筛'对他是新的'信息。给你用户已经熟悉的背景，和一批候选。"
    "判断哪些候选对用户是**新的、值得看的**（不是他早就知道的）。"
    '严格输出 JSON：{"novel_urls": [".."]}，只放新的那些的 url。'
)

def judge_novelty(client, candidates: list[Candidate], known_context: str = "") -> list[Candidate]:
    if not candidates:
        return []
    listing = "\n".join(f"- {c.url} | {c.title} | {(c.body or c.summary)[:600]}" for c in candidates)
    data = client.complete_json([
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": f"用户已知背景：\n{known_context}\n\n候选：\n{listing}"},
    ])
    novel = set(data.get("novel_urls", []) or [])
    return [c for c in candidates if c.url in novel]
