# src/diting/sources/github_releases.py
from __future__ import annotations
import httpx
from diting.models import Candidate


def check_repo_release(
    repo: str,
    store,
    *,
    get=httpx.get,
    token: str | None = None,
) -> tuple[list[Candidate], str | None]:
    """Check a GitHub repo's latest release.

    Returns (candidates, tag) where tag is the new version string when a new
    release is found, or None otherwise.  The snapshot (versions.json) is NOT
    advanced here — the caller must call store.set_seen_version(repo, tag)
    AFTER successful delivery so that a failed delivery retries on the next run.
    """
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        resp = get(
            f"https://api.github.com/repos/{repo}/releases/latest",
            headers=headers,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return [], None

    tag = data.get("tag_name")
    if not tag:
        return [], None

    if tag == store.get_seen_version(repo):
        return [], None

    # Do NOT write set_seen_version here — deferred to post-delivery in runner.
    body: str = data.get("body") or ""
    name: str = data.get("name") or ""
    summary = body[:300] if body else name

    return [
        Candidate(
            title=f"{repo} 出新版 {tag}",
            url=data.get("html_url") or "",
            summary=summary,
            source="github_release",
        )
    ], tag
