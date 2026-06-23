"""项目雷达信号：读单个项目的 STATUS/ONBOARDING 文本 + 算内容 hash。"""
from __future__ import annotations
import hashlib
import os


def read_status_text(status_dir: str, match: str) -> str:
    """读 status_dir 下文件名含 match 的所有 .md，按文件名排序拼接。

    每篇前面带文件名（含项目名/话题，对蒸馏有用）。目录不存在/不可读 → 返 ""。
    """
    try:
        names = sorted(n for n in os.listdir(status_dir)
                       if n.endswith(".md") and match in n)
    except OSError:
        return ""
    parts: list[str] = []
    for name in names:
        try:
            with open(os.path.join(status_dir, name), "r", encoding="utf-8") as f:
                content = f.read()
        except OSError:
            continue
        parts.append(f"《{name[:-3]}》\n{content}")
    return "\n\n---\n\n".join(parts)


def status_hash(text: str) -> str:
    """内容 hash（sha256 十六进制）——用于判断某项目 STATUS 是否变了。"""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
