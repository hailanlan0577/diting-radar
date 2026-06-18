# src/diting/signal/distill.py
from __future__ import annotations
from diting.models import SignalItem, Interests

_SYSTEM = (
    "你是一个帮用户提炼'最近在钻研什么'的助手。读用户最近的工作/会话记录，"
    "抽出他正在追的技术话题、用到的工具/项目实体、悬而未决的问题（TODO/卡点）、当天做出的决策。"
    "只保留技术相关的，忽略生活琐事。严格输出 JSON："
    '{"topics": [..], "entities": [..], "open_loops": [..], "decisions": [..]}'
)


def distill_interests(client, items: list[SignalItem], max_chars: int = 40000) -> Interests:
    corpus = "\n\n---\n\n".join(i.text for i in items)[:max_chars]
    data = client.complete_json([
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": f"以下是我最近的记录：\n\n{corpus}"},
    ])
    def tup(key): return tuple(data.get(key, []) or [])
    return Interests(topics=tup("topics"), entities=tup("entities"),
                     open_loops=tup("open_loops"), decisions=tup("decisions"))
