from diting.state import StateStore

def test_pushed_dedup(tmp_path):
    s = StateStore(str(tmp_path))
    assert s.is_pushed("http://a") is False
    s.mark_pushed("http://a", "标题A")
    assert s.is_pushed("http://a") is True
    assert s.is_pushed("http://b") is False

def test_profile_roundtrip(tmp_path):
    s = StateStore(str(tmp_path))
    assert s.load_profile() == {"stack": [], "tools": [], "topics": [], "repos": []}
    s.save_profile({"stack": ["MLX"], "tools": ["graphify"], "topics": ["LoRA"]})
    assert s.load_profile()["stack"] == ["MLX"]

def test_dug_topics_roundtrip(tmp_path):
    from diting.state import StateStore
    s = StateStore(str(tmp_path / "state"))
    assert s.is_dug("RAG 新做法") is False
    s.mark_dug("RAG 新做法")
    assert s.is_dug("RAG 新做法") is True
    # 持久化：换一个 StateStore 实例仍记得
    s2 = StateStore(str(tmp_path / "state"))
    assert s2.is_dug("RAG 新做法") is True
