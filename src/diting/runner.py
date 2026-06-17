# src/diting/runner.py
from __future__ import annotations
import os, time, subprocess
from diting.models import Interests, Report
from diting.signal.obsidian import collect_session_records
from diting.signal.distill import distill_interests
from diting.signal.profile import fatten_profile
from diting.query import generate_queries
from diting.crawl import run_crawl
from diting.novelty import filter_unpushed, judge_novelty
from diting.synthesize import synthesize
from diting.deliver.obsidian_out import write_report_to_inbox
from diting.deliver.feishu import send_to_feishu
from diting.sources.arxiv import search_arxiv
from diting.sources.hackernews import search_hn
from diting.sources.github import search_github_repos
from diting.sources.websearch import search_web


def build_sources(cfg) -> dict:
    gh_token = os.environ.get(cfg.github_token_env)
    return {
        "arxiv": lambda q: search_arxiv(q),
        "hackernews": lambda q: search_hn(q),
        "github": lambda q: search_github_repos(q, token=gh_token),
        "websearch": lambda q: search_web(q, cfg.searxng_url),
    }


def build_known_context(interests: Interests, profile: dict) -> str:
    return ("用户最近在搞：" + "、".join(interests.topics)
            + "；常用栈/工具：" + "、".join(profile.get("stack", []) + profile.get("tools", [])))


def run_report(lens, cfg, client, store, *, now_ts=None, sources=None,
               feishu_run=subprocess.run) -> Report:
    now_ts = now_ts if now_ts is not None else time.time()
    signals = collect_session_records(cfg.session_records_dir, cfg.lookback_days, now_ts)
    interests = distill_interests(client, signals) if signals else Interests((), (), (), ())
    profile = fatten_profile(store.load_profile(), interests)
    store.save_profile(profile)
    queries = generate_queries(client, lens, interests, profile)
    candidates, notes = run_crawl(queries, sources or build_sources(cfg))
    candidates = filter_unpushed(candidates, store)
    candidates = judge_novelty(client, candidates, build_known_context(interests, profile))
    date = time.strftime("%Y-%m-%d", time.localtime(now_ts))
    report = synthesize(client, lens, date, candidates, interests, notes)
    try:
        write_report_to_inbox(report, cfg.vault_inbox_dir, now_ts)
        send_to_feishu(report, cfg.feishu_target, run=feishu_run)
        for it in report.items:
            store.mark_pushed(it.url, it.title)
    except Exception as e:
        print(f"[谛听] 投递失败，未标记已推送（下次重试）：{e}")
    return report
