# src/diting/project_radar.py
from __future__ import annotations
import time
from diting.signal.project_signal import read_status_text, status_hash
from diting.models import SignalItem, Report
from diting.signal.distill import distill_interests
from diting.query import generate_queries
from diting.crawl import run_crawl, enrich_bodies
from diting.novelty import filter_unpushed_project, judge_novelty
from diting.synthesize import synthesize
from diting.deliver.project_out import write_project_intel
from diting.runner import build_sources, build_known_context


def detect_changed_projects(cfg, store) -> list[tuple[str, str, str]]:
    """返回 STATUS 变更（或从没跑过）的项目 (slug, text, hash)。无 STATUS 文件的跳过。"""
    out: list[tuple[str, str, str]] = []
    for spec in cfg.project_radar_projects:
        text = read_status_text(cfg.project_radar_status_dir, spec.match)
        if not text:
            continue
        h = status_hash(text)
        if h != store.get_status_hash(spec.slug):
            out.append((spec.slug, text, h))
    return out


def run_project_radar(cfg, client, store, *, now_ts=None, sources=None,
                      enrich=enrich_bodies) -> list[Report]:
    """对每个 STATUS 变更的项目跑一遍 research 流水线，产出该项目专属情报。

    成功处理完一版 STATUS（含空结果）→ 更新 hash；异常 → 不更新、下次重试。
    """
    now_ts = now_ts if now_ts is not None else time.time()
    date = time.strftime("%Y-%m-%d", time.localtime(now_ts))
    reports: list[Report] = []
    for slug, text, h in detect_changed_projects(cfg, store):
        try:
            interests = distill_interests(client, [SignalItem("project_status", text, now_ts)])
            profile = store.load_profile()
            queries = generate_queries(client, "research", interests, profile)
            candidates, _notes = run_crawl(queries, sources or build_sources(cfg))
            candidates = enrich(candidates, cfg.fetch_top_n, cfg.known_antibot_domains)
            candidates = filter_unpushed_project(candidates, store, slug)
            candidates = judge_novelty(client, candidates, build_known_context(interests, profile))
            report = synthesize(client, "research", date, candidates, interests, [])
        except Exception as e:
            print(f"[谛听 project] {slug} 失败，跳过（hash 不更新，下次重试）：{e}")
            continue
        delivered = True
        if not report.is_empty():
            try:
                write_project_intel(slug, report, cfg.project_radar_output_dir)
                for it in report.items:
                    store.mark_project_pushed(slug, it.url)
            except Exception as e:
                print(f"[谛听 project] {slug} 投递失败，未更新 hash（下次重试）：{e}")
                delivered = False
        if delivered:
            store.set_status_hash(slug, h)
        reports.append(report)
    return reports
