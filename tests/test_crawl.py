from diting.models import Candidate
from diting.crawl import run_crawl

def test_crawl_merges_and_dedups():
    def src_a(q): return [Candidate(f"A-{q}", f"http://a/{q}", "", "a"),
                          Candidate("dup", "http://dup", "", "a")]
    def src_b(q): return [Candidate("dup", "http://dup", "", "b")]   # 同 URL 应被去重
    cands, notes = run_crawl(["q1", "q2"], {"a": src_a, "b": src_b})
    urls = [c.url for c in cands]
    assert urls.count("http://dup") == 1
    assert "http://a/q1" in urls and "http://a/q2" in urls
    assert notes == []

def test_crawl_notes_empty_source():
    def good(q): return [Candidate("x", "http://x", "", "good")]
    def empty(q): return []
    _, notes = run_crawl(["q"], {"good": good, "empty": empty})
    assert any("empty" in n for n in notes)
