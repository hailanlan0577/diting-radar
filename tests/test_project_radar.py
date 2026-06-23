import types
import time
from diting.config import ProjectSpec
from diting.state import StateStore

_NOW = time.mktime(time.strptime("2026-06-23 11:00", "%Y-%m-%d %H:%M"))


def _radar_cfg(status_dir, out_dir, projects):
    return types.SimpleNamespace(
        project_radar_status_dir=str(status_dir),
        project_radar_output_dir=str(out_dir),
        project_radar_projects=projects,
        fetch_top_n=5, known_antibot_domains=(),
    )


def test_detect_changed_projects(tmp_path):
    from diting.project_radar import detect_changed_projects
    d = tmp_path / "ps"; d.mkdir()
    f = d / "macbook-ytst-STATUS.md"
    f.write_text("ytst v1", encoding="utf-8")
    cfg = _radar_cfg(d, tmp_path / "out", (ProjectSpec("ytst", "ytst"),))
    store = StateStore(str(tmp_path / "state"))

    # 从没跑过 → 入选
    changed = detect_changed_projects(cfg, store)
    assert [c[0] for c in changed] == ["ytst"]
    slug, text, h = changed[0]
    assert "ytst v1" in text

    # 记下 hash 后再检测 → 不入选
    store.set_status_hash(slug, h)
    assert detect_changed_projects(cfg, store) == []

    # STATUS 内容变了 → 又入选
    f.write_text("ytst v2 改了", encoding="utf-8")
    assert [c[0] for c in detect_changed_projects(cfg, store)] == ["ytst"]


def test_detect_skips_project_without_status_file(tmp_path):
    from diting.project_radar import detect_changed_projects
    d = tmp_path / "ps"; d.mkdir()  # 空目录，没有任何 STATUS
    cfg = _radar_cfg(d, tmp_path / "out", (ProjectSpec("ytst", "ytst"),))
    store = StateStore(str(tmp_path / "state"))
    assert detect_changed_projects(cfg, store) == []


from diting.models import Candidate


class _Router:
    """按 system prompt 关键词模拟 DeepSeek 各步。"""
    def complete_json(self, messages, **kw):
        s = messages[0]["content"]
        if "提炼" in s:                      # distill
            return {"topics": ["以图搜图 精排"], "entities": [], "open_loops": [], "decisions": []}
        if "科研雷达" in s:                  # generate_queries(lens=research)
            return {"queries": ["image retrieval rerank"]}
        if "对他是新的" in s:                # judge_novelty
            return {"novel_urls": ["http://a"]}
        if "私人技术情报员" in s:            # synthesize(lens=research)
            return {"items": [{"url": "http://a", "title": "论文A",
                               "one_liner": "x", "why_it_matters": "对 ytst 精排有用"}]}
        raise ValueError(f"unexpected prompt: {s[:40]}")


def test_run_project_radar_end_to_end(tmp_path):
    from diting.project_radar import run_project_radar
    d = tmp_path / "ps"; d.mkdir()
    (d / "macbook-ytst-STATUS.md").write_text("ytst 在做以图搜图精排", encoding="utf-8")
    out = tmp_path / "out"
    cfg = _radar_cfg(d, out, (ProjectSpec("ytst", "ytst"),))
    store = StateStore(str(tmp_path / "state"))
    reports = run_project_radar(
        cfg, _Router(), store, now_ts=_NOW,
        sources={"websearch": lambda q: [Candidate("论文A", "http://a", "摘要", "websearch")]},
        enrich=lambda cands, *a, **k: cands,
    )
    assert len(reports) == 1 and not reports[0].is_empty()
    text = (out / "ytst.md").read_text(encoding="utf-8")
    assert "[论文A](http://a) — 对 ytst 精排有用" in text
    assert store.is_project_pushed("ytst", "http://a")   # 投递成功后登记
    assert store.get_status_hash("ytst") is not None      # hash 更新


def test_run_project_radar_skips_unchanged(tmp_path):
    from diting.project_radar import run_project_radar
    d = tmp_path / "ps"; d.mkdir()
    (d / "macbook-ytst-STATUS.md").write_text("ytst 状态", encoding="utf-8")
    out = tmp_path / "out"
    cfg = _radar_cfg(d, out, (ProjectSpec("ytst", "ytst"),))
    store = StateStore(str(tmp_path / "state"))
    # 第一次正常跑（用真 router）
    run_project_radar(cfg, _Router(), store, now_ts=_NOW,
                      sources={"websearch": lambda q: [Candidate("A", "http://a", "", "websearch")]},
                      enrich=lambda c, *a, **k: c)

    class _Boom:
        def complete_json(self, *a, **k):
            raise AssertionError("STATUS 没变不该再调模型")
    # STATUS 没变 → detect 返空 → 模型一次都不调
    reports = run_project_radar(cfg, _Boom(), store, now_ts=_NOW,
                                sources={"websearch": lambda q: []},
                                enrich=lambda c, *a, **k: c)
    assert reports == []


def test_run_project_radar_empty_updates_hash_no_file(tmp_path):
    from diting.project_radar import run_project_radar
    d = tmp_path / "ps"; d.mkdir()
    (d / "macbook-ytst-STATUS.md").write_text("ytst 状态", encoding="utf-8")
    out = tmp_path / "out"
    cfg = _radar_cfg(d, out, (ProjectSpec("ytst", "ytst"),))
    store = StateStore(str(tmp_path / "state"))

    class _Empty(_Router):
        def complete_json(self, messages, **kw):
            s = messages[0]["content"]
            if "对他是新的" in s:
                return {"novel_urls": []}          # 全判为旧 → 候选清零 → 空报告
            return super().complete_json(messages, **kw)

    reports = run_project_radar(cfg, _Empty(), store, now_ts=_NOW,
                                sources={"websearch": lambda q: [Candidate("A", "http://a", "", "websearch")]},
                                enrich=lambda c, *a, **k: c)
    assert len(reports) == 1 and reports[0].is_empty()
    assert not (out / "ytst.md").exists()           # 空 → 不写文件
    assert store.get_status_hash("ytst") is not None  # 但 hash 更新（别天天重爬）


def test_run_project_radar_isolates_project_failure(tmp_path):
    from diting.project_radar import run_project_radar
    d = tmp_path / "ps"; d.mkdir()
    # aaa 失败，bbb 成功
    (d / "macbook-aaa-STATUS.md").write_text("aaa 项目 FAILME 标记", encoding="utf-8")
    (d / "macbook-bbb-STATUS.md").write_text("bbb 正常项目", encoding="utf-8")
    out = tmp_path / "out"
    cfg = _radar_cfg(d, out, (ProjectSpec("aaa", "aaa"), ProjectSpec("bbb", "bbb")))
    store = StateStore(str(tmp_path / "state"))

    class _PartialFail(_Router):
        def complete_json(self, messages, **kw):
            s = messages[0]["content"]
            u = messages[1]["content"] if len(messages) > 1 else ""
            # distill 步：aaa 的 user 消息含 FAILME 则抛异常
            if "提炼" in s and "FAILME" in u:
                raise RuntimeError("boom")
            # 其它步：正常
            if "提炼" in s:
                return {"topics": ["x"], "entities": [], "open_loops": [], "decisions": []}
            if "科研雷达" in s:
                return {"queries": ["q"]}
            if "对他是新的" in s:
                return {"novel_urls": ["http://b"]}
            if "私人技术情报员" in s:
                return {"items": [{"url": "http://b", "title": "B",
                                   "one_liner": "", "why_it_matters": "对 bbb 有用"}]}
            raise ValueError(f"unexpected prompt: {s[:40]}")

    reports = run_project_radar(cfg, _PartialFail(), store, now_ts=_NOW,
                                sources={"websearch": lambda q: [Candidate("B", "http://b", "摘要", "websearch")]},
                                enrich=lambda c, *a, **k: c)

    # 异常不该冒出来，aaa 被隔离、skip、不进 reports；bbb 成功进去
    assert len(reports) == 1 and not reports[0].is_empty()

    # aaa 失败隔离：无输出文件、hash 未更新
    assert not (out / "aaa.md").exists()
    assert store.get_status_hash("aaa") is None

    # bbb 继续跑：有输出、hash 已更新
    assert (out / "bbb.md").exists()
    assert store.get_status_hash("bbb") is not None
    text = (out / "bbb.md").read_text(encoding="utf-8")
    assert "[B](http://b) — 对 bbb 有用" in text
