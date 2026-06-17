import os
from diting.signal.obsidian import collect_session_records


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
