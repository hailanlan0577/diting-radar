# src/diting/signal/obsidian.py
from __future__ import annotations
import os
from diting.models import SignalItem

# 谛听自己产出的文档关键词——读兴趣信号时排除，避免读自己的情报/深挖造成自循环。
_DITING_OUTPUT_KEYWORDS = ("谛听情报", "谛听深挖")


def _collect_md_dir(d, cutoff, source, *, exclude_keywords=(),
                    per_doc_chars=None, prepend_name=False):
    """读单个目录下最近(mtime >= cutoff)改动的 .md，返回 SignalItem 列表（不排序）。

    per_doc_chars: 截断每篇正文取开头（None 不截断）。
    prepend_name: 把文件名(去 .md)放在正文前——文件名常含话题，对蒸馏很有用。
    exclude_keywords: 文件名含其中任一关键词则跳过。
    """
    if not os.path.isdir(d):
        return []
    items: list[SignalItem] = []
    for name in os.listdir(d):
        if not name.endswith(".md"):
            continue
        if any(k in name for k in exclude_keywords):
            continue
        path = os.path.join(d, name)
        try:
            mtime = os.path.getmtime(path)
            if mtime < cutoff:
                continue
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()
        except OSError:
            continue
        if per_doc_chars is not None:
            text = text[:per_doc_chars]
        if prepend_name:
            text = f"《{name[:-3]}》\n{text}"
        items.append(SignalItem(source=source, text=text, mtime=mtime))
    return items


def collect_session_records(records_dir, lookback_days, now_ts) -> list[SignalItem]:
    cutoff = now_ts - lookback_days * 86400
    items = _collect_md_dir(records_dir, cutoff, "obsidian_session")
    items.sort(key=lambda i: i.mtime, reverse=True)
    return items


def collect_documents(dirs, lookback_days, now_ts, *, max_docs=12,
                      per_doc_chars=1500,
                      exclude_keywords=_DITING_OUTPUT_KEYWORDS) -> list[SignalItem]:
    """读多个高价值项目目录下最近的 .md（设计/复盘/项目笔记等），作为兴趣信号补充。

    每篇截断 per_doc_chars 取开头 + 带文件名；排除谛听自产出；
    按 mtime 降序取最多 max_docs 篇（防内容量暴增挤爆蒸馏预算）。
    """
    cutoff = now_ts - lookback_days * 86400
    items: list[SignalItem] = []
    for d in dirs:
        items += _collect_md_dir(d, cutoff, "obsidian_doc",
                                 exclude_keywords=exclude_keywords,
                                 per_doc_chars=per_doc_chars, prepend_name=True)
    items.sort(key=lambda i: i.mtime, reverse=True)
    return items[:max_docs]
