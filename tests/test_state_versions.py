# tests/test_state_versions.py
from diting.state import StateStore


def test_get_seen_version_initially_none(tmp_path):
    s = StateStore(str(tmp_path))
    assert s.get_seen_version("owner/repo") is None


def test_set_then_get_seen_version(tmp_path):
    s = StateStore(str(tmp_path))
    s.set_seen_version("owner/repo", "v1.2.3")
    assert s.get_seen_version("owner/repo") == "v1.2.3"


def test_set_multiple_repos(tmp_path):
    s = StateStore(str(tmp_path))
    s.set_seen_version("org/a", "v1.0")
    s.set_seen_version("org/b", "v2.0")
    assert s.get_seen_version("org/a") == "v1.0"
    assert s.get_seen_version("org/b") == "v2.0"
    assert s.get_seen_version("org/c") is None


def test_set_seen_version_overwrites(tmp_path):
    s = StateStore(str(tmp_path))
    s.set_seen_version("owner/repo", "v1.0")
    s.set_seen_version("owner/repo", "v2.0")
    assert s.get_seen_version("owner/repo") == "v2.0"


def test_versions_json_persists_across_instances(tmp_path):
    s1 = StateStore(str(tmp_path))
    s1.set_seen_version("owner/repo", "v3.0")

    s2 = StateStore(str(tmp_path))
    assert s2.get_seen_version("owner/repo") == "v3.0"


def test_corrupt_versions_json_degrades(tmp_path):
    import os
    s = StateStore(str(tmp_path))

    # Write invalid JSON to versions.json
    versions_file = os.path.join(str(tmp_path), "versions.json")
    with open(versions_file, "w") as f:
        f.write("{ this is not valid json ")

    # Should not raise, should degrade and return None
    assert s.get_seen_version("owner/repo") is None
