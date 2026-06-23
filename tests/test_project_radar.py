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
