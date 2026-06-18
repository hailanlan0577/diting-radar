# src/diting/dig.py
from __future__ import annotations
import json
from diting.models import Candidate, DigReport

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


_DIG_SYNTH_SYSTEM = (
    "你是用户的私人技术情报研究员（precision-first，宁缺毋滥）。基于给定话题和抓取到的多篇来源正文，"
    "综合成一份结构化中文长资料 markdown。结构：## 概览 / ## 关键论文与项目（带链接+一句话价值）/ "
    "## 核心知识（分主题）/ ## 对你项目的直接建议 / ## 跨来源共识与分歧。只用提供的来源，不编造。"
    "另给一句话总括 one_liner。严格输出 JSON：{\"one_liner\": \"..\", \"markdown\": \"..完整 markdown..\"}"
)


def synthesize_dig(client, topic: str, date: str, candidates: list,
                   *, body_limit: int = 2000) -> DigReport:
    if not candidates:
        return DigReport(topic=topic, date=date, markdown="", one_liner="", source_count=0)
    sources = [{"title": c.title, "url": c.url, "text": (c.body or c.summary)[:body_limit]}
               for c in candidates]
    data = client.complete_json([
        {"role": "system", "content": _DIG_SYNTH_SYSTEM},
        {"role": "user", "content": json.dumps({"topic": topic, "sources": sources}, ensure_ascii=False)},
    ])
    return DigReport(
        topic=topic, date=date,
        markdown=(data.get("markdown") or "").strip(),
        one_liner=(data.get("one_liner") or "").strip(),
        source_count=len(candidates),
    )
