# src/diting/project_radar.py
from __future__ import annotations
from diting.signal.project_signal import read_status_text, status_hash


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
