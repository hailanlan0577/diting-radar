# src/diting/signal/obsidian.py
from __future__ import annotations
import os
import threading
from diting.models import SignalItem

# 谛听自己产出的文档关键词——读兴趣信号时排除，避免读自己的情报/深挖造成自循环。
_DITING_OUTPUT_KEYWORDS = ("谛听情报", "谛听深挖")

# 读单个信号目录的超时（秒）。Obsidian vault 在 iCloud 上，文件提供者(fileproviderd)
# 偶发抽风会让 os.listdir 的 opendir() 永久阻塞，拖垮整个无人值守进程。用守护线程隔离：
# 某目录读取超过此秒数就放弃、跳过它，绝不让整个谛听僵死（可用 DITING_DIR_TIMEOUT 覆盖）。
_LISTDIR_TIMEOUT = float(os.environ.get("DITING_DIR_TIMEOUT", "10"))


def _read_md_dir(d, cutoff, source, exclude_keywords, per_doc_chars, prepend_name):
    """实际读取逻辑（可能因 iCloud 阻塞，故由 _collect_md_dir 套超时调用）。

    目录不存在/不可读时 os.listdir 抛 OSError，由上层 _collect_md_dir 兜成空目录。
    """
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


def _collect_md_dir(d, cutoff, source, *, exclude_keywords=(),
                    per_doc_chars=None, prepend_name=False):
    """读单个目录下最近(mtime >= cutoff)改动的 .md，返回 SignalItem 列表（不排序）。

    per_doc_chars: 截断每篇正文取开头（None 不截断）。
    prepend_name: 把文件名(去 .md)放在正文前——文件名常含话题，对蒸馏很有用。
    exclude_keywords: 文件名含其中任一关键词则跳过。

    用守护线程套 _LISTDIR_TIMEOUT 超时：iCloud 抽风导致目录读取卡死时超时即跳过该目录
    （返回空），不让整个谛听僵死。目录不存在/不可读也按空目录处理。
    """
    result: dict = {}

    def work():
        try:
            result["items"] = _read_md_dir(d, cutoff, source, exclude_keywords,
                                           per_doc_chars, prepend_name)
        except OSError:
            result["items"] = []   # 目录不存在/不可读 → 当空目录

    t = threading.Thread(target=work, daemon=True)
    t.start()
    t.join(_LISTDIR_TIMEOUT)
    if "items" not in result:
        # 超时仍没读完：目录卡死（如 iCloud 抽风）→ 跳过，绝不拖垮整个进程
        return []
    return result["items"]


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
