# src/diting/__main__.py
from __future__ import annotations
import argparse
from pathlib import Path
from diting.config import load_config
from diting.llm import DeepSeekClient
from diting.state import StateStore
from diting.runner import run_report
from diting.signal.profile import seed_profile


def _client(cfg):
    return DeepSeekClient(cfg.deepseek_base_url, cfg.deepseek_api_key, cfg.deepseek_model)


def _run_ask(cfg, client, topic, mode, max_sources):
    """按主题聚焦搜索;无副作用:不碰 StateStore/去重库/投递,结果 return 文本。"""
    import time
    date = time.strftime("%Y-%m-%d")
    if mode == "dig":
        from diting.dig import generate_dig_queries, synthesize_dig
        from diting.sources.fetch import search_engine
        from diting.crawl import enrich_bodies
        queries = generate_dig_queries(client, topic)
        seen, cands = set(), []
        for q in queries:
            for c in search_engine(q):
                if c.url not in seen:
                    seen.add(c.url); cands.append(c)
        cands = cands[:max_sources]
        cands = enrich_bodies(cands, len(cands), cfg.known_antibot_domains)
        rep = synthesize_dig(client, topic, date, cands)
        if rep.is_empty():
            return f"没找到关于《{topic}》值得看的资料。"
        return rep.one_liner + "\n\n" + rep.markdown
    else:  # brief
        import os
        from diting.sources.arxiv import search_arxiv
        from diting.sources.hackernews import search_hn
        from diting.sources.github import search_github_repos
        from diting.sources.websearch import search_web
        from diting.crawl import enrich_bodies
        from diting.synthesize import synthesize
        from diting.deliver.feishu import format_feishu_message
        from diting.models import Interests
        gh = os.environ.get(cfg.github_token_env)
        cands = (search_arxiv(topic) + search_hn(topic)
                 + search_github_repos(topic, token=gh)
                 + search_web(topic, cfg.searxng_url))
        seen, uniq = set(), []
        for c in cands:
            if getattr(c, "url", None) and c.url not in seen:
                seen.add(c.url); uniq.append(c)
        uniq = enrich_bodies(uniq[:max_sources], cfg.fetch_top_n, cfg.known_antibot_domains)
        rep = synthesize(client, "research", date, uniq,
                         Interests((topic,), (), (), ()), notes=[])
        return format_feishu_message(rep)


def main():
    ap = argparse.ArgumentParser(prog="diting")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run"); r.add_argument("--lens", default="research")
    s = sub.add_parser("seed-profile"); s.add_argument("--from", dest="files", nargs="+", required=True)
    a = sub.add_parser("ask"); a.add_argument("topic")
    a.add_argument("--mode", default="dig", choices=["dig", "brief"])
    a.add_argument("--max-sources", type=int, default=10)
    args = ap.parse_args()
    try:
        cfg = load_config()
        client = _client(cfg)
    except (FileNotFoundError, RuntimeError) as e:
        raise SystemExit(f"配置/密钥错误：{e}")
    if args.cmd == "run":
        store = StateStore(cfg.state_dir)
        if args.lens == "dig":
            from diting.dig import run_dig
            report = run_dig(cfg, client, store)
            print(f"[dig] {report.date}: " +
                  (f"深挖《{report.topic}》{report.source_count} 篇来源"
                   if not report.is_empty() else "无新题/空，跳过"))
        elif args.lens == "project":
            from diting.project_radar import run_project_radar
            reports = run_project_radar(cfg, client, store)
            n = sum(1 for r in reports if not r.is_empty())
            print(f"[project] 跑了 {len(reports)} 个变更项目，{n} 个产出情报")
        else:
            report = run_report(args.lens, cfg, client, store)
            print(f"[{report.lens}] {report.date}: {len(report.items)} 条" +
                  ("" if report.items else " — 今天这块没值得看的"))
    elif args.cmd == "seed-profile":
        store = StateStore(cfg.state_dir)
        texts = [Path(f).read_text(encoding="utf-8") for f in args.files]
        prof = seed_profile(client, texts)
        store.save_profile(prof)
        print("关注清单已生成：", prof)
    elif args.cmd == "ask":
        print(_run_ask(cfg, client, args.topic, args.mode, args.max_sources))


if __name__ == "__main__":
    main()
