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
) -> list[Candidate]:
    """Check a GitHub repo's latest release and return a Candidate only when a new version appears."""
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
        return []

    tag = data.get("tag_name")
    if not tag:
        return []

    if tag == store.get_seen_version(repo):
        return []

    store.set_seen_version(repo, tag)

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
    ]
