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
from diting.sources.github_releases import check_repo_release


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


def _collect_candidates(lens: str, cfg, client, store, interests: Interests,
                        profile: dict, sources) -> tuple[list, list[str], dict]:
    """Collect raw candidates for a given lens.

    trends: iterate watched repos through the release sentinel — no LLM query-gen.
    research/loops: generate queries then crawl.
    Returns (candidates, notes, pending) where pending maps repo -> new_tag for
    trends releases that have not yet been committed to the snapshot.
    """
    if lens == "trends":
        token = os.environ.get(cfg.github_token_env)
        candidates: list = []
        pending: dict[str, str] = {}
        for repo in profile.get("repos", []):
            cands, tag = check_repo_release(repo, store, token=token)
            candidates += cands
            if tag is not None:
                pending[repo] = tag
        notes: list[str] = [] if candidates else ["所有关注 repo 都没出新版"]
        return candidates, notes, pending

    # research / loops — original path
    queries = generate_queries(client, lens, interests, profile)
    candidates, notes = run_crawl(queries, sources or build_sources(cfg))
    return candidates, notes, {}


def run_report(lens, cfg, client, store, *, now_ts=None, sources=None,
               feishu_run=subprocess.run) -> Report:
    now_ts = now_ts if now_ts is not None else time.time()
    date = time.strftime("%Y-%m-%d", time.localtime(now_ts))
    degraded = False
    # pending maps repo -> new_tag for trends snapshots awaiting post-delivery commit.
    pending: dict[str, str] = {}
    try:
        signals = collect_session_records(cfg.session_records_dir, cfg.lookback_days, now_ts)
        interests = distill_interests(client, signals) if signals else Interests((), (), (), ())
        profile = fatten_profile(store.load_profile(), interests)
        store.save_profile(profile)
        candidates, notes, pending = _collect_candidates(
            lens, cfg, client, store, interests, profile,
            sources or build_sources(cfg),
        )
        candidates = filter_unpushed(candidates, store)
        # For trends the version diff IS the novelty signal; skip LLM novelty filter
        # to avoid accidentally dropping a genuinely-new release.
        if lens != "trends":
            candidates = judge_novelty(client, candidates, build_known_context(interests, profile))
        report = synthesize(client, lens, date, candidates, interests, notes)
    except Exception as e:
        report = Report(lens=lens, date=date, items=(),
                        notes=(f"⚠️ DeepSeek 暂时不可用，本次跳过：{e}",))
        degraded = True
    try:
        write_report_to_inbox(report, cfg.vault_inbox_dir, now_ts)
        if degraded or not report.is_empty():
            send_to_feishu(report, cfg.feishu_target, run=feishu_run)
        if not degraded:
            for it in report.items:
                store.mark_pushed(it.url, it.title)
            # Advance trends snapshots post-delivery (mirrors mark_pushed logic):
            # versions.json is only updated here so a failed delivery retries next run.
            for repo, tag in pending.items():
                store.set_seen_version(repo, tag)
    except Exception as e:
        print(f"[谛听] 投递失败，未标记已推送（下次重试）：{e}")
    return report
