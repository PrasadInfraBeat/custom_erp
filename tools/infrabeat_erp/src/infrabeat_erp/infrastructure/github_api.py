"""GitHub REST API client via httpx async (Phase 7a Sprint 2 Task 3).

Replaces gh CLI dependency for promote workflow. Uses PAT from pat_store.

Functions:
    create_pull_request(owner, repo, head, base, title, body) -> int
    get_check_runs(owner, repo, ref) -> list[dict]
    merge_pull_request(owner, repo, pr_number, merge_method="squash") -> bool
    get_pull_request(owner, repo, pr_number) -> dict

Error classes:
    GitHubError (base) / GitHubAuthError / GitHubRateLimitError / GitHubNotFoundError
"""
from __future__ import annotations

from typing import Optional

import httpx

from .pat_store import load_pat

GITHUB_API_BASE = "https://api.github.com"
DEFAULT_TIMEOUT = 30.0


class GitHubError(Exception):
    """Base GitHub API error."""


class GitHubAuthError(GitHubError):
    """401/403 - invalid PAT or insufficient scope."""


class GitHubRateLimitError(GitHubError):
    """429 or X-RateLimit-Remaining: 0."""


class GitHubNotFoundError(GitHubError):
    """404 from GitHub API."""


def _build_headers(pat: Optional[str] = None) -> dict:
    if pat is None:
        pat = load_pat()
    return {
        "Authorization": f"Bearer {pat}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _raise_for_status(response: httpx.Response) -> None:
    if response.status_code in (401, 403):
        if response.headers.get("X-RateLimit-Remaining") == "0":
            raise GitHubRateLimitError(
                f"Rate limit exceeded; resets at {response.headers.get('X-RateLimit-Reset')}"
            )
        raise GitHubAuthError(f"Auth failed: {response.status_code} {response.text[:200]}")
    if response.status_code == 404:
        raise GitHubNotFoundError(f"Not found: {response.url}")
    if response.status_code == 429:
        raise GitHubRateLimitError("429 rate limited")
    if response.status_code >= 400:
        raise GitHubError(f"GitHub API {response.status_code}: {response.text[:200]}")


class _NoopCtx:
    def __init__(self, client):
        self._client = client
    async def __aenter__(self):
        return self._client
    async def __aexit__(self, *a):
        return False


def _async_client(existing: Optional[httpx.AsyncClient]):
    if existing is not None:
        return _NoopCtx(existing)
    return httpx.AsyncClient()


async def create_pull_request(
    owner: str, repo: str, head: str, base: str, title: str, body: str = "",
    client: Optional[httpx.AsyncClient] = None,
) -> int:
    """Create a pull request. Returns PR number."""
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls"
    payload = {"head": head, "base": base, "title": title, "body": body}
    async with _async_client(client) as c:
        r = await c.post(url, json=payload, headers=_build_headers(), timeout=DEFAULT_TIMEOUT)
        _raise_for_status(r)
        return int(r.json()["number"])


async def get_check_runs(
    owner: str, repo: str, ref: str,
    client: Optional[httpx.AsyncClient] = None,
) -> list[dict]:
    """List check-runs for a commit ref."""
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/commits/{ref}/check-runs"
    async with _async_client(client) as c:
        r = await c.get(url, headers=_build_headers(), timeout=DEFAULT_TIMEOUT)
        _raise_for_status(r)
        return r.json().get("check_runs", [])


async def merge_pull_request(
    owner: str, repo: str, pr_number: int, merge_method: str = "squash",
    client: Optional[httpx.AsyncClient] = None,
) -> bool:
    """Merge a PR. Returns True on success."""
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}/merge"
    payload = {"merge_method": merge_method}
    async with _async_client(client) as c:
        r = await c.put(url, json=payload, headers=_build_headers(), timeout=DEFAULT_TIMEOUT)
        _raise_for_status(r)
        return r.json().get("merged", False)


async def get_pull_request(
    owner: str, repo: str, pr_number: int,
    client: Optional[httpx.AsyncClient] = None,
) -> dict:
    """Get PR details (incl. head.sha for check polling)."""
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}"
    async with _async_client(client) as c:
        r = await c.get(url, headers=_build_headers(), timeout=DEFAULT_TIMEOUT)
        _raise_for_status(r)
        return r.json()
