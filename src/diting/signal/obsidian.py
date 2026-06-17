# src/diting/signal/obsidian.py
from __future__ import annotations
import os
from diting.models import SignalItem


def collect_session_records(
    records_dir: str, lookback_days: int, now_ts: float
) -> list[SignalItem]:
    if not os.path.isdir(records_dir):
        return []
    cutoff = now_ts - lookback_days * 86400
    items: list[SignalItem] = []
    for name in os.listdir(records_dir):
        if not name.endswith(".md"):
            continue
        path = os.path.join(records_dir, name)
        try:
            mtime = os.path.getmtime(path)
            if mtime < cutoff:
                continue
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()
        except OSError:
            continue
        items.append(SignalItem(source="obsidian_session", text=text, mtime=mtime))
    items.sort(key=lambda i: i.mtime, reverse=True)
    return items
