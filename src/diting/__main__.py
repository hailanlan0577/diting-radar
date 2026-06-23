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


def main():
    ap = argparse.ArgumentParser(prog="diting")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run"); r.add_argument("--lens", default="research")
    s = sub.add_parser("seed-profile"); s.add_argument("--from", dest="files", nargs="+", required=True)
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


if __name__ == "__main__":
    main()
