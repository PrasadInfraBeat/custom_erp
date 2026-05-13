"""Tests for promote orchestrator (Task 3)."""
from __future__ import annotations

import asyncio

import httpx
import pytest
import respx

from infrabeat_erp.application.promote import (
    PROMOTE_FLOW,
    REPO_NAME,
    REPO_OWNER,
    PromoteError,
    PromoteResult,
    do_promote,
)
from infrabeat_erp.infrastructure.github_api import GITHUB_API_BASE


@pytest.fixture
def mock_pat(monkeypatch):
    monkeypatch.setattr(
        "infrabeat_erp.infrastructure.github_api.load_pat",
        lambda: "ghp_test",
    )
    monkeypatch.setattr(
        "infrabeat_erp.application.promote.POLL_INTERVAL_SEC", 0,
    )


def test_promote_rejects_unknown_target():
    with pytest.raises(PromoteError, match="Unknown target"):
        asyncio.run(do_promote("foobar"))


@respx.mock
def test_promote_happy_path_staging(mock_pat):
    respx.post(f"{GITHUB_API_BASE}/repos/{REPO_OWNER}/{REPO_NAME}/pulls").mock(
        return_value=httpx.Response(201, json={"number": 100})
    )
    respx.get(f"{GITHUB_API_BASE}/repos/{REPO_OWNER}/{REPO_NAME}/pulls/100").mock(
        return_value=httpx.Response(200, json={"number": 100, "head": {"sha": "abc123"}})
    )
    respx.get(f"{GITHUB_API_BASE}/repos/{REPO_OWNER}/{REPO_NAME}/commits/abc123/check-runs").mock(
        return_value=httpx.Response(200, json={
            "check_runs": [
                {"name": "pytest", "status": "completed", "conclusion": "success"},
                {"name": "lint", "status": "completed", "conclusion": "success"},
            ]
        })
    )
    respx.put(f"{GITHUB_API_BASE}/repos/{REPO_OWNER}/{REPO_NAME}/pulls/100/merge").mock(
        return_value=httpx.Response(200, json={"merged": True, "sha": "merged_sha"})
    )
    result = asyncio.run(do_promote("staging"))
    assert isinstance(result, PromoteResult)
    assert result.target == "staging"
    assert result.source_branch == "dev"
    assert result.target_branch == "staging"
    assert result.pr_number == 100
    assert result.merged is True


@respx.mock
def test_promote_fails_when_ci_red(mock_pat):
    respx.post(f"{GITHUB_API_BASE}/repos/{REPO_OWNER}/{REPO_NAME}/pulls").mock(
        return_value=httpx.Response(201, json={"number": 100})
    )
    respx.get(f"{GITHUB_API_BASE}/repos/{REPO_OWNER}/{REPO_NAME}/pulls/100").mock(
        return_value=httpx.Response(200, json={"number": 100, "head": {"sha": "abc"}})
    )
    respx.get(f"{GITHUB_API_BASE}/repos/{REPO_OWNER}/{REPO_NAME}/commits/abc/check-runs").mock(
        return_value=httpx.Response(200, json={
            "check_runs": [
                {"name": "pytest", "status": "completed", "conclusion": "failure"}
            ]
        })
    )
    with pytest.raises(PromoteError, match="CI failed"):
        asyncio.run(do_promote("staging"))


@respx.mock
def test_promote_propagates_pr_creation_failure(mock_pat):
    respx.post(f"{GITHUB_API_BASE}/repos/{REPO_OWNER}/{REPO_NAME}/pulls").mock(
        return_value=httpx.Response(422, json={"message": "validation failed"})
    )
    with pytest.raises(PromoteError, match="PR creation failed"):
        asyncio.run(do_promote("staging"))


def test_promote_flow_constants():
    assert PROMOTE_FLOW == {
        "staging": ("dev", "staging"),
        "production": ("staging", "production"),
    }


# === L87 fix: _filter_failed_checks tests ===

from infrabeat_erp.application.promote import _filter_failed_checks


def test_filter_returns_empty_when_all_success():
    runs = [
        {"name": "lint", "status": "completed", "conclusion": "success"},
        {"name": "pytest", "status": "completed", "conclusion": "success"},
    ]
    assert _filter_failed_checks(runs) == []


def test_filter_passes_through_real_failures():
    runs = [
        {"name": "lint", "status": "completed", "conclusion": "success"},
        {"name": "pytest", "status": "completed", "conclusion": "failure"},
    ]
    result = _filter_failed_checks(runs)
    assert len(result) == 1
    assert result[0]["name"] == "pytest"


def test_filter_excludes_require_approving_review():
    runs = [
        {"name": "lint", "status": "completed", "conclusion": "success"},
        {"name": "Require approving review", "status": "completed", "conclusion": "failure"},
    ]
    assert _filter_failed_checks(runs) == []


def test_filter_excludes_review_check_case_insensitive():
    runs = [
        {"name": "REQUIRE APPROVING REVIEW", "status": "completed", "conclusion": "failure"},
        {"name": "require approving review", "status": "completed", "conclusion": "failure"},
    ]
    assert _filter_failed_checks(runs) == []


def test_filter_combines_real_failure_with_policy_gate():
    runs = [
        {"name": "Require approving review", "status": "completed", "conclusion": "failure"},
        {"name": "pytest", "status": "completed", "conclusion": "failure"},
    ]
    result = _filter_failed_checks(runs)
    assert len(result) == 1
    assert result[0]["name"] == "pytest"
def test_filter_skips_block_direct_pushes_policy_gate():
    """L94 fix: \'Block direct pushes to protected branches\' is a ruleset policy
    gate that always fails for orchestrator-driven promotes by design. Filter
    alongside \'Require approving review\' (L87) so only real CI failures block.
    """
    check_runs = [
        {"name": "Block direct pushes to protected branches", "status": "completed", "conclusion": "failure"},
        {"name": "Require approving review", "status": "completed", "conclusion": "failure"},
        {"name": "pytest", "status": "completed", "conclusion": "failure"},
        {"name": "lint", "status": "completed", "conclusion": "success"},
    ]
    failed = _filter_failed_checks(check_runs)
    failed_names = [cr["name"] for cr in failed]
    assert failed_names == ["pytest"], (
        f"Only non-policy-gate failures should be returned. Got: {failed_names}"
    )
