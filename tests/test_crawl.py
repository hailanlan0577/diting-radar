from diting.models import Candidate
from diting.crawl import run_crawl, enrich_bodies

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


def test_enrich_bodies_fetches_top_n_only():
    cands = [Candidate(f"t{i}", f"http://u{i}", "", "websearch") for i in range(4)]
    calls = []
    def fake_fetch(url, *, stealthy=False): calls.append(url); return "正文-" + url
    out = enrich_bodies(cands, top_n=2, fetch=fake_fetch)
    assert calls == ["http://u0", "http://u1"]
    assert out[0].body == "正文-http://u0"
    assert out[2].body == ""           # top_n 之外不抓

def test_enrich_bodies_uses_stealthy_for_antibot_domain():
    cands = [Candidate("t", "https://zhuanlan.zhihu.com/p/1", "", "websearch")]
    seen = {}
    def fake_fetch(url, *, stealthy=False): seen["stealthy"] = stealthy; return "正文"
    enrich_bodies(cands, top_n=1, antibot_domains=("zhihu.com",), fetch=fake_fetch)
    assert seen["stealthy"] is True

def test_enrich_bodies_keeps_original_when_fetch_empty():
    cands = [Candidate("t", "http://u", "原摘要", "websearch")]
    out = enrich_bodies(cands, top_n=1, fetch=lambda url, *, stealthy=False: "")
    assert out[0].body == "" and out[0].summary == "原摘要"
