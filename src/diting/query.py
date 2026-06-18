# src/diting/query.py
from __future__ import annotations
import json
from diting.models import Interests

_LENS_PROMPT = {
    "research": "镜头=科研雷达。围绕用户的话题/卡点，生成用于在 arXiv/GitHub/HN 找"
                "'有没有更好的方法、最新论文、SOTA、best practice'的英文检索串。",
}

def generate_queries(client, lens: str, interests: Interests, profile: dict,
                     max_queries: int = 6) -> list[str]:
    lens_desc = _LENS_PROMPT.get(lens, _LENS_PROMPT["research"])
    sys = (lens_desc + " 每条是简短英文关键词组（3-6 个词），不要整句话——"
           "arXiv/HN/GitHub 是关键词检索，整句几乎搜不到。"
           '严格输出 JSON：{"queries": ["keyword phrase", ...]}')
    ctx = {"topics": list(interests.topics), "entities": list(interests.entities),
           "open_loops": list(interests.open_loops), "profile": profile}
    data = client.complete_json([
        {"role": "system", "content": sys},
        {"role": "user", "content": json.dumps(ctx, ensure_ascii=False)},
    ])
    return list(data.get("queries", []) or [])[:max_queries]
