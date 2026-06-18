import yaml
from diting.models import Interests
from diting.signal.dig_topics import select_dig_topic


class _Store:
    def __init__(self, dug=()):
        self._dug = set(dug)
    def is_dug(self, t):
        return t in self._dug


def _queue(tmp_path, items):
    p = tmp_path / "dig_queue.yaml"
    p.write_text(yaml.safe_dump(items, allow_unicode=True), encoding="utf-8")
    return str(p)


def test_select_prefers_queue(tmp_path):
    q = _queue(tmp_path, ["话题A", "话题B"])
    assert select_dig_topic(_Store(), Interests(("兴趣X",), (), (), ()), q) == "话题A"

def test_select_skips_dug_in_queue(tmp_path):
    q = _queue(tmp_path, ["话题A", "话题B"])
    assert select_dig_topic(_Store(dug={"话题A"}), Interests((), (), (), ()), q) == "话题B"

def test_select_falls_back_to_interests_when_queue_empty(tmp_path):
    q = _queue(tmp_path, [])
    assert select_dig_topic(_Store(), Interests(("兴趣X", "兴趣Y"), (), (), ()), q) == "兴趣X"

def test_select_returns_none_when_all_dug(tmp_path):
    assert select_dig_topic(_Store(dug={"兴趣X"}), Interests(("兴趣X",), (), (), ()), "/nonexistent") is None
