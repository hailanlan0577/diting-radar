# src/diting/crawl.py
from __future__ import annotations
import dataclasses
from typing import Callable
from diting.models import Candidate
from diting.sources.fetch import fetch_text

def run_crawl(queries: list[str],
              sources: dict[str, Callable[[str], list[Candidate]]]
              ) -> tuple[list[Candidate], list[str]]:
    seen: set[str] = set()
    merged: list[Candidate] = []
    counts: dict[str, int] = {name: 0 for name in sources}
    for q in queries:
        for name, fn in sources.items():
            for cand in fn(q):
                counts[name] += 1
                if cand.url in seen:
                    continue
                seen.add(cand.url)
                merged.append(cand)
    notes = [f"{name} 没取到" for name, n in counts.items() if n == 0]
    return merged, notes


def enrich_bodies(candidates: list[Candidate], top_n: int,
                  antibot_domains: tuple[str, ...] = (), *, fetch=fetch_text) -> list[Candidate]:
    """对前 top_n 条候选抓正文填入 body；命中反爬域走无头隐身；抓不到保持原样。"""
    out: list[Candidate] = []
    for i, c in enumerate(candidates):
        if i < top_n:
            stealthy = any(d in c.url for d in antibot_domains)
            body = fetch(c.url, stealthy=stealthy)
            out.append(dataclasses.replace(c, body=body) if body else c)
        else:
            out.append(c)
    return out
