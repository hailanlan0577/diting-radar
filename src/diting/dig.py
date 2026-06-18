# src/diting/dig.py
from __future__ import annotations

_DIG_QUERY_SYSTEM = (
    "你在帮用户深挖一个技术话题。围绕给定话题，生成 4-6 个多角度英文检索关键词串，"
    "覆盖：综述/论文、最佳实践/实战经验、开源实现、常见坑/对比。每条是简短英文关键词组(3-6 词)，"
    "不要整句话。严格输出 JSON：{\"queries\": [\"keyword phrase\", ...]}"
)


def generate_dig_queries(client, topic: str, max_queries: int = 6) -> list[str]:
    data = client.complete_json([
        {"role": "system", "content": _DIG_QUERY_SYSTEM},
        {"role": "user", "content": topic},
    ])
    return list(data.get("queries", []) or [])[:max_queries]
