#!/usr/bin/env python3
"""谛听 vault 预取：把 Obsidian (iCloud) 笔记里的「影子」(dataless) 文件拉回本地。

背景：vault 在 iCloud 上，新文件刚从别的设备同步过来 / 「优化储存」evict 的旧文件会变成
dataless 占位，谛听读到时触发按需下载、偶遇 iCloud 抽风即永久阻塞（见 obsidian.py 的超时兜底）。
本脚本由 launchd 在每个镜头跑之前定时调用，提前把影子拉回本地，从源头降低卡死概率。

幂等、自带单文件超时、失败隔几秒重试、无影子时秒退；只读取(触发下载)、不修改任何文件。
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
RETRIES = int(os.environ.get("DITING_PREFETCH_RETRIES", "2"))    # 失败重试次数
BACKOFF = float(os.environ.get("DITING_PREFETCH_BACKOFF", "5"))  # 重试间隔(秒)，给 iCloud 时间把内容传完


def _is_dataless(path):
    try:
        return bool(os.lstat(path).st_flags & SF_DATALESS)
    except OSError:
        return False


def collect_dataless():
    """遍历 vault 收集所有「影子」.md 文件（os.lstat 只读元数据，不触发下载）。"""
    out = []
    for root, dirs, files in os.walk(VAULT):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("exports", "archive")]
        for f in files:
            if f.endswith(".md") and _is_dataless(os.path.join(root, f)):
                out.append(os.path.join(root, f))
    return out


def _try_download_once(path):
    """触发一次下载，带超时。无异常返回 None，否则返回错误描述字符串。"""
    done = {}

    def work():
        try:
            if HAVE_BRCTL:
                subprocess.run(["brctl", "download", path], timeout=FILE_TIMEOUT,
                               capture_output=True)
            with open(path, "rb") as f:
                f.read()
            done["err"] = None
        except Exception as e:
            done["err"] = "%s: %s" % (type(e).__name__, e)

    t = threading.Thread(target=work, daemon=True)
    t.start()
    t.join(FILE_TIMEOUT + 3)
    if "err" not in done:
        return "超时(>%.0fs)" % (FILE_TIMEOUT + 3)
    return done["err"]


def download(path):
    """触发下载并确认实体化；瞬时态(新文件同步中)失败则隔 BACKOFF 秒重试 RETRIES 次。

    以「下载后是否仍是 dataless」为最终判据——brctl/read 不报错不代表内容真到位。
    返回 (是否成功实体化, 最后一次错误描述或 None)。
    """
    last_err = None
    for attempt in range(RETRIES + 1):
        err = _try_download_once(path)
        if not _is_dataless(path):
            return True, None
        last_err = err or "下载后仍是影子"
        if attempt < RETRIES:
            time.sleep(BACKOFF)
    return False, last_err


def main():
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    files = collect_dataless()
    if not files:
        print(f"[prefetch] {ts}: 无影子，跳过")
        return
    ok = 0
    failed = []
    for p in files:
        success, err = download(p)
        if success:
            ok += 1
        else:
            failed.append((os.path.relpath(p, VAULT), err))
    left = len(collect_dataless())
    msg = f"[prefetch] {ts}: 拉回 {ok}/{len(files)}，剩余影子 {left}"
    if failed:
        msg += "；未拉回：" + "; ".join(f"{rel}（{err}）" for rel, err in failed)
    print(msg)


if __name__ == "__main__":
    main()
