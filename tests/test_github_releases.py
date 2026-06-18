# tests/test_github_releases.py
from unittest.mock import MagicMock
from diting.sources.github_releases import check_repo_release
from diting.state import StateStore


def _make_response(tag_name="v1.0.0", html_url="https://github.com/o/r/releases/tag/v1.0.0",
                   name="Release 1.0", body="Some release notes"):
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {
        "tag_name": tag_name,
        "html_url": html_url,
        "name": name,
        "body": body,
    }
    return resp


def _make_error_response():
    resp = MagicMock()
    resp.raise_for_status.side_effect = Exception("HTTP error")
    return resp


def test_first_sighting_returns_one_candidate_and_writes_snapshot(tmp_path):
    store = StateStore(str(tmp_path))
    mock_get = MagicMock(return_value=_make_response(tag_name="v1.0.0"))

    cands, tag = check_repo_release("owner/repo", store, get=mock_get)

    assert len(cands) == 1
    c = cands[0]
    assert "owner/repo" in c.title
    assert "v1.0.0" in c.title
    assert c.url == "https://github.com/o/r/releases/tag/v1.0.0"
    assert c.source == "github_release"
    assert tag == "v1.0.0"
    # snapshot NOT written by check_repo_release — deferred to post-delivery in runner
    assert store.get_seen_version("owner/repo") is None


def test_same_version_returns_empty(tmp_path):
    store = StateStore(str(tmp_path))
    store.set_seen_version("owner/repo", "v1.0.0")
    mock_get = MagicMock(return_value=_make_response(tag_name="v1.0.0"))

    cands, tag = check_repo_release("owner/repo", store, get=mock_get)

    assert cands == []
    assert tag is None


def test_newer_version_returns_candidate(tmp_path):
    store = StateStore(str(tmp_path))
    store.set_seen_version("owner/repo", "v1.0.0")
    mock_get = MagicMock(return_value=_make_response(tag_name="v2.0.0"))

    cands, tag = check_repo_release("owner/repo", store, get=mock_get)

    assert len(cands) == 1
    assert "v2.0.0" in cands[0].title
    assert tag == "v2.0.0"
    # snapshot still not written here — runner writes it post-delivery
    assert store.get_seen_version("owner/repo") == "v1.0.0"


def test_http_error_returns_empty(tmp_path):
    store = StateStore(str(tmp_path))
    mock_get = MagicMock(return_value=_make_error_response())

    cands, tag = check_repo_release("owner/repo", store, get=mock_get)

    assert cands == []
    assert tag is None
    assert store.get_seen_version("owner/repo") is None


def test_no_release_body_uses_name(tmp_path):
    store = StateStore(str(tmp_path))
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {
        "tag_name": "v1.0.0",
        "html_url": "https://github.com/o/r/releases/tag/v1.0.0",
        "name": "My Release",
        "body": None,
    }
    mock_get = MagicMock(return_value=resp)

    cands, tag = check_repo_release("owner/repo", store, get=mock_get)

    assert len(cands) == 1
    assert cands[0].summary == "My Release"


def test_body_truncated_to_300(tmp_path):
    store = StateStore(str(tmp_path))
    long_body = "x" * 500
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {
        "tag_name": "v1.0.0",
        "html_url": "https://github.com/o/r/releases/tag/v1.0.0",
        "name": "Release",
        "body": long_body,
    }
    mock_get = MagicMock(return_value=resp)

    cands, tag = check_repo_release("owner/repo", store, get=mock_get)

    assert len(cands[0].summary) == 300


def test_token_sent_as_auth_header(tmp_path):
    store = StateStore(str(tmp_path))
    mock_get = MagicMock(return_value=_make_response())

    check_repo_release("owner/repo", store, get=mock_get, token="secret-token")

    call_kwargs = mock_get.call_args
    headers = call_kwargs.kwargs.get("headers", {})
    assert headers.get("Authorization") == "Bearer secret-token"
