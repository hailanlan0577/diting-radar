# src/diting/dig.py
from __future__ import annotations
import json
import subprocess
import time
from diting.models import Candidate, DigReport, Interests
from diting.signal.obsidian import collect_session_records
from diting.signal.distill import distill_interests
from diting.signal.dig_topics import select_dig_topic
from diting.sources.fetch import search_engine, fetch_text
from diting.crawl import enrich_bodies
from diting.deliver.dig_out import write_dig_to_vault
from diting.deliver.feishu import send_dig_notice

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


def run_dig(cfg, client, store, *, now_ts=None, search=None, fetch=None,
            feishu_run=subprocess.run) -> DigReport:
    """选题→多角度搜→抓正文→综合→Obsidian+飞书投递→投递成功后登记。

    无题/空报告/异常 → 不投递、不登记（precision-first）。
    """
    now_ts = now_ts if now_ts is not None else time.time()
    date = time.strftime("%Y-%m-%d", time.localtime(now_ts))
    search = search or search_engine
    fetch = fetch or fetch_text
    try:
        signals = collect_session_records(cfg.session_records_dir, cfg.lookback_days, now_ts)
        interests = distill_interests(client, signals) if signals else Interests((), (), (), ())
        topic = select_dig_topic(store, interests, cfg.dig_queue_path)
        if topic is None:
            return DigReport(topic="", date=date, markdown="", one_liner="", source_count=0)
        queries = generate_dig_queries(client, topic)
        seen: set[str] = set()
        cands: list[Candidate] = []
        for q in queries:
            for c in search(q):
                if c.url in seen:
                    continue
                seen.add(c.url)
                cands.append(c)
        cands = cands[:cfg.dig_max_sources]
        cands = enrich_bodies(cands, len(cands), cfg.known_antibot_domains, fetch=fetch)
        report = synthesize_dig(client, topic, date, cands)
    except Exception as e:
        print(f"[谛听 dig] 失败，跳过：{e}")
        return DigReport(topic="", date=date, markdown="", one_liner="", source_count=0)
    if report.is_empty():
        return report
    try:
        path = write_dig_to_vault(report, cfg.dig_vault_dir, now_ts)
        if send_dig_notice(report, cfg.feishu_target, path, run=feishu_run):
            store.mark_dug(report.topic)
    except Exception as e:
        print(f"[谛听 dig] 投递失败，未登记（下次重试）：{e}")
    return report
