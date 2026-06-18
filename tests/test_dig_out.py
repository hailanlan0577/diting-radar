import os, time
from diting.models import DigReport
from diting.deliver.dig_out import write_dig_to_vault

_NOW = time.mktime(time.strptime("2026-06-18 20:00", "%Y-%m-%d %H:%M"))

def test_write_dig_creates_reference_manual(tmp_path):
    report = DigReport(topic="RAG 新做法", date="2026-06-18",
                       markdown="## 概览\n正文内容", one_liner="一句话", source_count=3)
    path = write_dig_to_vault(report, str(tmp_path / "谛听深挖"), _NOW)
    assert os.path.exists(path)
    assert path.endswith("2026-06-18 谛听深挖 RAG 新做法.md")
    text = open(path, encoding="utf-8").read()
    assert "type: reference-manual" in text
    assert "title: 2026-06-18 谛听深挖 · RAG 新做法" in text
    assert "## 概览\n正文内容" in text

def test_write_dig_sanitizes_slash_in_topic(tmp_path):
    report = DigReport(topic="A/B 测试", date="2026-06-18",
                       markdown="x", one_liner="y", source_count=1)
    path = write_dig_to_vault(report, str(tmp_path / "d"), _NOW)
    # 话题里的 / 不能变成路径分隔符
    assert os.path.basename(path) == "2026-06-18 谛听深挖 A／B 测试.md"
