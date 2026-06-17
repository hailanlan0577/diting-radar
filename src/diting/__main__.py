# src/diting/__main__.py
from __future__ import annotations
import argparse
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
    cfg = load_config()
    if args.cmd == "run":
        store = StateStore(cfg.state_dir)
        report = run_report(args.lens, cfg, _client(cfg), store)
        print(f"[{report.lens}] {report.date}: {len(report.items)} 条" +
              ("" if report.items else " — 今天这块没值得看的"))
    elif args.cmd == "seed-profile":
        store = StateStore(cfg.state_dir)
        texts = [open(f, encoding="utf-8").read() for f in args.files]
        prof = seed_profile(_client(cfg), texts)
        store.save_profile(prof)
        print("关注清单已生成：", prof)


if __name__ == "__main__":
    main()
