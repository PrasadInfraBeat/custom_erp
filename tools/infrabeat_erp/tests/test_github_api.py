"""Tests for GitHub API client (Task 3)."""
from __future__ import annotations

import asyncio

import httpx
import pytest
import respx

from infrabeat_erp.infrastructure.github_api import (
    GITHUB_API_BASE,
    GitHubAuthError,
    GitHubError,
    GitHubNotFoundError,
    GitHubRateLimitError,
    create_pull_request,
    get_check_runs,
    get_pull_request,
    merge_pull_request,
)


@pytest.fixture
def mock_pat(monkeypatch):
    monkeypatch.setattr(
        "infrabeat_erp.infrastructure.github_api.load_pat",
        lambda: "ghp_test_token",
    )


@respx.mock
def test_create_pull_request_returns_pr_number(mock_pat):
    respx.post(f"{GITHUB_API_BASE}/repos/owner/repo/pulls").mock(
        return_value=httpx.Response(201, json={"number": 42})
    )
    pr = asyncio.run(create_pull_request("owner", "repo", "head", "base", "title"))
    assert pr == 42


@respx.mock
def test_create_pull_request_raises_on_auth_error(mock_pat):
    respx.post(f"{GITHUB_API_BASE}/repos/owner/repo/pulls").mock(
        return_value=httpx.Response(401, json={"message": "Bad credentials"})
    )
    with pytest.raises(GitHubAuthError):
        asyncio.run(create_pull_request("owner", "repo", "head", "base", "title"))


@respx.mock
def test_get_check_runs_returns_list(mock_pat):
    respx.get(f"{GITHUB_API_BASE}/repos/owner/repo/commits/abc/check-runs").mock(
        return_value=httpx.Response(200, json={
            "check_runs": [
                {"name": "test", "status": "completed", "conclusion": "success"}
            ]
        })
    )
    runs = asyncio.run(get_check_runs("owner", "repo", "abc"))
    assert len(runs) == 1
    assert runs[0]["name"] == "test"


@respx.mock
def test_merge_pull_request_squash(mock_pat):
    respx.put(f"{GITHUB_API_BASE}/repos/owner/repo/pulls/42/merge").mock(
        return_value=httpx.Response(200, json={"merged": True, "sha": "abc"})
    )
    merged = asyncio.run(merge_pull_request("owner", "repo", 42, "squash"))
    assert merged is True


@respx.mock
def test_get_pull_request_returns_pr_data(mock_pat):
    respx.get(f"{GITHUB_API_BASE}/repos/owner/repo/pulls/42").mock(
        return_value=httpx.Response(200, json={"number": 42, "head": {"sha": "abc"}})
    )
    pr = asyncio.run(get_pull_request("owner", "repo", 42))
    assert pr["number"] == 42
    assert pr["head"]["sha"] == "abc"


@respx.mock
def test_404_raises_not_found(mock_pat):
    respx.get(f"{GITHUB_API_BASE}/repos/owner/repo/pulls/999").mock(
        return_value=httpx.Response(404, json={"message": "Not Found"})
    )
    with pytest.raises(GitHubNotFoundError):
        asyncio.run(get_pull_request("owner", "repo", 999))


@respx.mock
def test_rate_limit_raises(mock_pat):
    respx.get(f"{GITHUB_API_BASE}/repos/owner/repo/commits/abc/check-runs").mock(
        return_value=httpx.Response(
            403,
            headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1700000000"},
            json={"message": "rate limited"},
        )
    )
    with pytest.raises(GitHubRateLimitError):
        asyncio.run(get_check_runs("owner", "repo", "abc"))


@respx.mock
def test_500_raises_generic_github_error(mock_pat):
    respx.get(f"{GITHUB_API_BASE}/repos/owner/repo/pulls/42").mock(
        return_value=httpx.Response(500, text="server error")
    )
    with pytest.raises(GitHubError):
        asyncio.run(get_pull_request("owner", "repo", 42))
