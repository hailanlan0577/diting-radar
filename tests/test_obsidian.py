import os
from diting.signal.obsidian import collect_session_records, collect_documents


def test_collects_recent_md_only(tmp_path):
    recent = tmp_path / "今天.md"
    recent.write_text("搞了 LoRA 微调", encoding="utf-8")
    old = tmp_path / "上月.md"
    old.write_text("旧的", encoding="utf-8")
    now = 1_000_000.0
    os.utime(recent, (now, now))
    os.utime(old, (now - 40 * 86400, now - 40 * 86400))
    items = collect_session_records(str(tmp_path), lookback_days=5, now_ts=now)
    assert len(items) == 1
    assert "LoRA" in items[0].text
    assert items[0].source == "obsidian_session"


def test_missing_dir_degrades(tmp_path):
    assert collect_session_records(str(tmp_path / "nope"), 5, 1_000_000.0) == []


def test_collect_documents_reads_recent_with_filename(tmp_path):
    d1 = tmp_path / "项目"; d1.mkdir()
    doc = d1 / "2026-06-18 ytst 真推上线.md"
    doc.write_text("今天把以图搜图真推上线了", encoding="utf-8")
    old = d1 / "古老.md"; old.write_text("旧", encoding="utf-8")
    now = 1_000_000.0
    os.utime(doc, (now, now))
    os.utime(old, (now - 40 * 86400, now - 40 * 86400))
    items = collect_documents([str(d1)], lookback_days=14, now_ts=now)
    assert len(items) == 1
    assert items[0].source == "obsidian_doc"
    assert "ytst 真推上线" in items[0].text   # 文件名(含话题)带进来了
    assert "真推上线了" in items[0].text       # 正文也在


def test_collect_documents_excludes_diting_output(tmp_path):
    d = tmp_path / "Inbox"; d.mkdir()
    (d / "2026-06-18 谛听情报.md").write_text("谛听自己发的", encoding="utf-8")
    (d / "2026-06-18 谛听深挖 RAG.md").write_text("谛听自己挖的", encoding="utf-8")
    (d / "2026-06-18 我的笔记.md").write_text("我写的内容", encoding="utf-8")
    now = 1_000_000.0
    for f in d.iterdir():
        os.utime(f, (now, now))
    items = collect_documents([str(d)], lookback_days=14, now_ts=now)
    assert len(items) == 1                     # 排除两个谛听自产出，只剩我的笔记
    assert "我写的内容" in items[0].text


def test_collect_documents_truncates_long_doc(tmp_path):
    d = tmp_path / "复盘"; d.mkdir()
    (d / "长文.md").write_text("X" * 9999, encoding="utf-8")
    now = 1_000_000.0
    os.utime(d / "长文.md", (now, now))
    items = collect_documents([str(d)], lookback_days=14, now_ts=now, per_doc_chars=1500)
    assert len(items[0].text) < 1700           # 文件名前缀 + 截断正文，远小于 9999


def test_collect_documents_caps_count(tmp_path):
    d = tmp_path / "项目"; d.mkdir()
    now = 1_000_000.0
    for i in range(20):
        f = d / f"doc{i}.md"; f.write_text(f"内容{i}", encoding="utf-8")
        os.utime(f, (now - i, now - i))        # 不同 mtime，最新的在前
    items = collect_documents([str(d)], lookback_days=14, now_ts=now, max_docs=12)
    assert len(items) == 12


def test_collect_documents_missing_dir_ok(tmp_path):
    assert collect_documents([str(tmp_path / "nope")], 14, 1_000_000.0) == []


def test_collect_md_dir_skips_hanging_dir(tmp_path, monkeypatch):
    """目录读取卡死（如 iCloud 文件提供者抽风）时，超时跳过该目录，不拖垮整个进程。"""
    import time
    import diting.signal.obsidian as ob

    monkeypatch.setattr(ob, "_LISTDIR_TIMEOUT", 0.3)
    real_listdir = os.listdir

    def hanging_listdir(p):
        time.sleep(5)              # 模拟 iCloud opendir() 永久阻塞
        return real_listdir(p)

    monkeypatch.setattr(ob.os, "listdir", hanging_listdir)

    start = time.time()
    items = collect_session_records(str(tmp_path), lookback_days=5, now_ts=1_000_000.0)
    elapsed = time.time() - start

    assert items == []             # 卡住的目录被跳过，返回空
    assert elapsed < 2.0           # 超时(0.3s)就放弃，没傻等满 5 秒
