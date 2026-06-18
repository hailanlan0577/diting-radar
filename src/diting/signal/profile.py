# src/diting/signal/profile.py
from __future__ import annotations
from diting.models import Interests

_SEED_SYSTEM = (
    "从用户的配置/手册文本里，抽出他长期依赖的技术栈、工具/skill、长期关注的技术话题，"
    "以及他依赖的 GitHub 项目（owner/name 形式，如 ml-explore/mlx）。"
    "严格输出 JSON：{\"stack\": [..], \"tools\": [..], \"topics\": [..], \"repos\": [..]}"
)

def seed_profile(client, source_texts: list[str]) -> dict:
    corpus = "\n\n---\n\n".join(source_texts)[:24000]
    data = client.complete_json([
        {"role": "system", "content": _SEED_SYSTEM},
        {"role": "user", "content": corpus},
    ])
    return {"stack": list(data.get("stack", []) or []),
            "tools": list(data.get("tools", []) or []),
            "topics": list(data.get("topics", []) or []),
            "repos": list(data.get("repos", []) or [])}

def _merge(existing: list[str], extra) -> list[str]:
    out = list(existing)
    for x in extra:
        if x not in out:
            out.append(x)
    return out

def fatten_profile(profile: dict, interests: Interests) -> dict:
    return {
        "stack": _merge(profile.get("stack", []), []),
        "tools": _merge(profile.get("tools", []), interests.entities),
        "topics": _merge(profile.get("topics", []), interests.topics),
        "repos": list(profile.get("repos", [])),
    }
