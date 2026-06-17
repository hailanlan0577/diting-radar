# src/diting/crawl.py
from __future__ import annotations
from typing import Callable
from diting.models import Candidate

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
