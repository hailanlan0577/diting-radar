from diting.signal.project_signal import read_status_text, status_hash


def test_read_status_text_matches_and_concats(tmp_path):
    d = tmp_path / "ps"; d.mkdir()
    (d / "macbook-ytst-STATUS.md").write_text("ytst 状态正文", encoding="utf-8")
    (d / "macbook-ytst-ONBOARDING.md").write_text("ytst 交接正文", encoding="utf-8")
    (d / "macbook-lbc-STATUS.md").write_text("别的项目", encoding="utf-8")
    (d / "ignore.txt").write_text("非 md", encoding="utf-8")
    text = read_status_text(str(d), "ytst")
    assert "ytst 状态正文" in text
    assert "ytst 交接正文" in text
    assert "别的项目" not in text          # 不匹配的项目不进来
    assert "非 md" not in text             # 非 .md 不读
    # 文件名作为标题带进去（含话题，对蒸馏有用）
    assert "macbook-ytst-STATUS" in text


def test_read_status_text_missing_dir_returns_empty(tmp_path):
    assert read_status_text(str(tmp_path / "nope"), "ytst") == ""


def test_read_status_text_no_match_returns_empty(tmp_path):
    d = tmp_path / "ps"; d.mkdir()
    (d / "macbook-lbc-STATUS.md").write_text("x", encoding="utf-8")
    assert read_status_text(str(d), "ytst") == ""


def test_status_hash_stable_and_sensitive():
    assert status_hash("abc") == status_hash("abc")     # 同内容同 hash
    assert status_hash("abc") != status_hash("abd")     # 内容变 hash 变
    assert len(status_hash("abc")) == 64                 # sha256 十六进制
