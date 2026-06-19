#!/usr/bin/env python3
"""谛听 vault 预取：把 Obsidian (iCloud) 笔记里的「影子」(dataless) 文件拉回本地。

背景：vault 在 iCloud 上，「优化 Mac 储存空间」开着时旧笔记会被 evict 成占位符，
谛听读到时触发按需下载、偶遇 fileproviderd 抽风即永久阻塞（见 obsidian.py 的超时兜底）。
本脚本在每个镜头跑之前由 launchd 定时调用，提前把影子拉回本地，从源头降低卡死概率。

幂等、自带单文件超时、无影子时秒退；只读取(触发下载)、不修改任何文件。
"""
from __future__ import annotations
import os
import stat
import shutil
import subprocess
import threading
import time

SF_DATALESS = getattr(stat, "SF_DATALESS", 0x40000000)
VAULT = os.path.expanduser(
    "~/Library/Mobile Documents/iCloud~md~obsidian/Documents/claude"
)
HAVE_BRCTL = shutil.which("brctl") is not None
FILE_TIMEOUT = float(os.environ.get("DITING_PREFETCH_TIMEOUT", "30"))


def collect_dataless():
    """遍历 vault 收集所有「影子」.md 文件（os.lstat 只读元数据，不触发下载）。"""
    out = []
    for root, dirs, files in os.walk(VAULT):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("exports", "archive")]
        for f in files:
            if not f.endswith(".md"):
                continue
            p = os.path.join(root, f)
            try:
                if os.lstat(p).st_flags & SF_DATALESS:
                    out.append(p)
            except OSError:
                pass
    return out


def download(path):
    """触发单个文件下载，带超时（防 iCloud 抽风时整批卡死）。返回是否成功。"""
    done = {}

    def work():
        try:
            if HAVE_BRCTL:
                subprocess.run(["brctl", "download", path], timeout=FILE_TIMEOUT,
                               capture_output=True)
            with open(path, "rb") as f:
                f.read()
            done["ok"] = True
        except Exception:
            done["ok"] = False

    t = threading.Thread(target=work, daemon=True)
    t.start()
    t.join(FILE_TIMEOUT + 3)
    return done.get("ok", False)


def main():
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    files = collect_dataless()
    if not files:
        print(f"[prefetch] {ts}: 无影子，跳过")
        return
    ok = sum(1 for p in files if download(p))
    left = len(collect_dataless())
    print(f"[prefetch] {ts}: 拉回 {ok}/{len(files)}，剩余影子 {left}")


if __name__ == "__main__":
    main()
