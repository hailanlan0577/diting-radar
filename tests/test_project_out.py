from diting.models import Report, RankedItem
from diting.deliver.project_out import write_project_intel


def _report(date, items):
    ranked = tuple(RankedItem(title=t, url=u, one_liner="", why_it_matters=w,
                              source="websearch", lens="research") for t, u, w in items)
    return Report(lens="research", date=date, items=ranked, notes=())


def test_write_creates_with_frontmatter(tmp_path):
    out = str(tmp_path / "谛听项目情报")
    r = _report("2026-06-23", [("论文A", "http://a", "对 ytst 精排有用")])
    path = write_project_intel("ytst", r, out)
    assert path.endswith("ytst.md")
    text = open(path, encoding="utf-8").read()
    assert "type: progress-log" in text
    assert "title: 谛听项目情报 · ytst" in text
    assert "last_updated: 2026-06-23" in text
    assert "## 2026-06-23" in text
    assert "- [论文A](http://a) — 对 ytst 精排有用" in text


def test_write_prepends_newest_on_top(tmp_path):
    out = str(tmp_path / "谛听项目情报")
    write_project_intel("ytst", _report("2026-06-20", [("旧", "http://old", "旧理由")]), out)
    path = write_project_intel("ytst", _report("2026-06-23", [("新", "http://new", "新理由")]), out)
    text = open(path, encoding="utf-8").read()
    # 新日期小节在旧日期小节之上
    assert text.index("## 2026-06-23") < text.index("## 2026-06-20")
    # frontmatter 只有一份（title 只出现一次），last_updated 更到最新
    assert text.count("title: 谛听项目情报 · ytst") == 1
    assert "last_updated: 2026-06-23" in text
    assert "last_updated: 2026-06-20" not in text
    assert "- [新](http://new) — 新理由" in text
    assert "- [旧](http://old) — 旧理由" in text
