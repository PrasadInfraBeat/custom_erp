"""Phase 7b Sprint 0 Task B - Tests for rollback orchestrator.

Sync test pattern (mirrors test_promote.py) - uses asyncio.run() instead of
pytest-asyncio, since that plugin is not in the installed plugin set.

Coverage:
- find_rollback_target: returns first parent SHA + tree; raises on invalid env;
  raises on branch-not-found (404); raises when commit has no parent
- do_rollback: production --confirm gate; dry_run short-circuit; full happy-path
  orchestration with mocked GitHub REST; raises when PAT missing;
  raises on merge conflict
"""
from __future__ import annotations

import asyncio
from unittest.mock import patch

import httpx
import pytest
import respx

from infrabeat_erp.application.rollback import (
    GITHUB_API_BASE,
    REPO_NAME,
    REPO_OWNER,
    RollbackError,
    RollbackResult,
    do_rollback,
    find_rollback_target,
    rollback_sync,
)


def _commit_payload(sha: str, parent_shas, tree_sha: str = "TREE_" + "0" * 35) -> dict:
    return {
        "sha": sha,
        "commit": {"tree": {"sha": tree_sha}, "message": "test"},
        "parents": [{"sha": p} for p in parent_shas],
    }


async def _find_target_with_new_client(env):
    async with httpx.AsyncClient() as client:
        return await find_rollback_target(env, client)


@pytest.fixture
def mock_pat():
    with patch("infrabeat_erp.application.rollback.load_pat", return_value="ghp_test_token_123"):
        yield


@pytest.fixture
def mock_pat_missing():
    from infrabeat_erp.infrastructure.pat_store import PatNotFound
    with patch("infrabeat_erp.application.rollback.load_pat", side_effect=PatNotFound("test: no PAT")):
        yield


# ============================================================================
# find_rollback_target unit tests
# ============================================================================

@respx.mock
def test_find_rollback_target_returns_first_parent():
    c2 = "c" * 40
    c1 = "1" * 40
    tree1 = "TREE_PARENT_" + "0" * 28
    respx.get(f"{GITHUB_API_BASE}/repos/{REPO_OWNER}/{REPO_NAME}/branches/staging").mock(
        return_value=httpx.Response(200, json={"commit": {"sha": c2}})
    )
    respx.get(f"{GITHUB_API_BASE}/repos/{REPO_OWNER}/{REPO_NAME}/commits/{c2}").mock(
        return_value=httpx.Response(200, json=_commit_payload(c2, [c1]))
    )
    respx.get(f"{GITHUB_API_BASE}/repos/{REPO_OWNER}/{REPO_NAME}/commits/{c1}").mock(
        return_value=httpx.Response(200, json=_commit_payload(c1, [], tree_sha=tree1))
    )
    current, target, target_tree = asyncio.run(_find_target_with_new_client("staging"))
    assert current == c2
    assert target == c1
    assert target_tree == tree1


def test_find_rollback_target_raises_on_invalid_env():
    with pytest.raises(RollbackError, match="invalid env"):
        asyncio.run(_find_target_with_new_client("dev"))


@respx.mock
def test_find_rollback_target_raises_on_branch_404():
    respx.get(f"{GITHUB_API_BASE}/repos/{REPO_OWNER}/{REPO_NAME}/branches/production").mock(
        return_value=httpx.Response(404, json={"message": "Branch not found"})
    )
    with pytest.raises(RollbackError, match="branch not found"):
        asyncio.run(_find_target_with_new_client("production"))


@respx.mock
def test_find_rollback_target_raises_when_no_parent():
    orphan = "0" * 40
    respx.get(f"{GITHUB_API_BASE}/repos/{REPO_OWNER}/{REPO_NAME}/branches/staging").mock(
        return_value=httpx.Response(200, json={"commit": {"sha": orphan}})
    )
    respx.get(f"{GITHUB_API_BASE}/repos/{REPO_OWNER}/{REPO_NAME}/commits/{orphan}").mock(
        return_value=httpx.Response(200, json=_commit_payload(orphan, []))
    )
    with pytest.raises(RollbackError, match="no parent"):
        asyncio.run(_find_target_with_new_client("staging"))


# ============================================================================
# do_rollback orchestration tests
# ============================================================================

def test_do_rollback_production_requires_confirm(mock_pat):
    with pytest.raises(RollbackError, match="production rollback requires --confirm"):
        asyncio.run(do_rollback(env="production", confirm=False))


def test_do_rollback_raises_when_pat_missing(mock_pat_missing):
    with pytest.raises(RollbackError, match="github PAT missing"):
        asyncio.run(do_rollback(env="staging"))


@respx.mock
def test_do_rollback_dry_run_does_not_create_commit_or_pr(mock_pat):
    c2 = "c" * 40
    c1 = "1" * 40
    tree1 = "TREE_" + "1" * 35
    respx.get(f"{GITHUB_API_BASE}/repos/{REPO_OWNER}/{REPO_NAME}/branches/staging").mock(
        return_value=httpx.Response(200, json={"commit": {"sha": c2}})
    )
    respx.get(f"{GITHUB_API_BASE}/repos/{REPO_OWNER}/{REPO_NAME}/commits/{c2}").mock(
        return_value=httpx.Response(200, json=_commit_payload(c2, [c1]))
    )
    respx.get(f"{GITHUB_API_BASE}/repos/{REPO_OWNER}/{REPO_NAME}/commits/{c1}").mock(
        return_value=httpx.Response(200, json=_commit_payload(c1, [], tree_sha=tree1))
    )
    create_commit_route = respx.post(
        f"{GITHUB_API_BASE}/repos/{REPO_OWNER}/{REPO_NAME}/git/commits"
    )
    create_pr_route = respx.post(
        f"{GITHUB_API_BASE}/repos/{REPO_OWNER}/{REPO_NAME}/pulls"
    )

    result = asyncio.run(do_rollback(env="staging", dry_run=True))

    assert isinstance(result, RollbackResult)
    assert result.env == "staging"
    assert result.rolled_back_from_sha == c2
    assert result.rolled_back_to_sha == c1
    assert "DRY_RUN" in result.rollback_branch
    assert result.pr_number == 0
    assert result.merge_sha == "DRY_RUN"
    assert not create_commit_route.called
    assert not create_pr_route.called


@respx.mock
def test_do_rollback_full_happy_path(mock_pat):
    c2 = "c" * 40
    c1 = "1" * 40
    tree1 = "TREE_" + "1" * 35
    new_commit = "n" * 40
    merge_sha = "m" * 40
    pr_number = 99

    respx.get(f"{GITHUB_API_BASE}/repos/{REPO_OWNER}/{REPO_NAME}/branches/staging").mock(
        return_value=httpx.Response(200, json={"commit": {"sha": c2}})
    )
    respx.get(f"{GITHUB_API_BASE}/repos/{REPO_OWNER}/{REPO_NAME}/commits/{c2}").mock(
        return_value=httpx.Response(200, json=_commit_payload(c2, [c1]))
    )
    respx.get(f"{GITHUB_API_BASE}/repos/{REPO_OWNER}/{REPO_NAME}/commits/{c1}").mock(
        return_value=httpx.Response(200, json=_commit_payload(c1, [], tree_sha=tree1))
    )
    respx.post(f"{GITHUB_API_BASE}/repos/{REPO_OWNER}/{REPO_NAME}/git/commits").mock(
        return_value=httpx.Response(201, json={"sha": new_commit})
    )
    respx.post(f"{GITHUB_API_BASE}/repos/{REPO_OWNER}/{REPO_NAME}/git/refs").mock(
        return_value=httpx.Response(201, json={"ref": "refs/heads/rollback/staging-to-1111111-foo"})
    )
    respx.post(f"{GITHUB_API_BASE}/repos/{REPO_OWNER}/{REPO_NAME}/pulls").mock(
        return_value=httpx.Response(201, json={
            "number": pr_number,
            "html_url": f"https://github.com/{REPO_OWNER}/{REPO_NAME}/pull/{pr_number}",
        })
    )
    respx.put(
        f"{GITHUB_API_BASE}/repos/{REPO_OWNER}/{REPO_NAME}/pulls/{pr_number}/merge"
    ).mock(return_value=httpx.Response(200, json={"sha": merge_sha, "merged": True}))

    result = asyncio.run(do_rollback(env="staging"))

    assert result.env == "staging"
    assert result.rolled_back_from_sha == c2
    assert result.rolled_back_to_sha == c1
    assert result.rollback_branch.startswith("rollback/staging-to-1111111-")
    assert result.pr_number == pr_number
    assert result.pr_url.endswith(f"/pull/{pr_number}")
    assert result.merge_sha == merge_sha


@respx.mock
def test_do_rollback_production_with_confirm_dry_run(mock_pat):
    c2 = "c" * 40
    c1 = "1" * 40
    tree1 = "TREE_" + "1" * 35

    respx.get(f"{GITHUB_API_BASE}/repos/{REPO_OWNER}/{REPO_NAME}/branches/production").mock(
        return_value=httpx.Response(200, json={"commit": {"sha": c2}})
    )
    respx.get(f"{GITHUB_API_BASE}/repos/{REPO_OWNER}/{REPO_NAME}/commits/{c2}").mock(
        return_value=httpx.Response(200, json=_commit_payload(c2, [c1]))
    )
    respx.get(f"{GITHUB_API_BASE}/repos/{REPO_OWNER}/{REPO_NAME}/commits/{c1}").mock(
        return_value=httpx.Response(200, json=_commit_payload(c1, [], tree_sha=tree1))
    )

    result = asyncio.run(do_rollback(env="production", confirm=True, dry_run=True))
    assert result.env == "production"
    assert result.rolled_back_to_sha == c1


@respx.mock
def test_do_rollback_raises_on_merge_conflict(mock_pat):
    c2 = "c" * 40
    c1 = "1" * 40
    tree1 = "TREE_" + "1" * 35
    new_commit = "n" * 40

    respx.get(f"{GITHUB_API_BASE}/repos/{REPO_OWNER}/{REPO_NAME}/branches/staging").mock(
        return_value=httpx.Response(200, json={"commit": {"sha": c2}})
    )
    respx.get(f"{GITHUB_API_BASE}/repos/{REPO_OWNER}/{REPO_NAME}/commits/{c2}").mock(
        return_value=httpx.Response(200, json=_commit_payload(c2, [c1]))
    )
    respx.get(f"{GITHUB_API_BASE}/repos/{REPO_OWNER}/{REPO_NAME}/commits/{c1}").mock(
        return_value=httpx.Response(200, json=_commit_payload(c1, [], tree_sha=tree1)),
    )
    respx.post(f"{GITHUB_API_BASE}/repos/{REPO_OWNER}/{REPO_NAME}/git/commits").mock(
        return_value=httpx.Response(201, json={"sha": new_commit})
    )
    respx.post(f"{GITHUB_API_BASE}/repos/{REPO_OWNER}/{REPO_NAME}/git/refs").mock(
        return_value=httpx.Response(201, json={"ref": "refs/heads/rollback/staging-to-1111111-foo"})
    )
    respx.post(f"{GITHUB_API_BASE}/repos/{REPO_OWNER}/{REPO_NAME}/pulls").mock(
        return_value=httpx.Response(201, json={
            "number": 42,
            "html_url": "https://github.com/x/y/pull/42",
        })
    )
    respx.put(
        f"{GITHUB_API_BASE}/repos/{REPO_OWNER}/{REPO_NAME}/pulls/42/merge"
    ).mock(return_value=httpx.Response(409, json={"message": "Merge conflict"}))

    with pytest.raises(RollbackError, match="merge rejected"):
        asyncio.run(do_rollback(env="staging"))


def test_rollback_sync_is_callable():
    """rollback_sync exists and is callable (full path validated by other tests)."""
    assert callable(rollback_sync)