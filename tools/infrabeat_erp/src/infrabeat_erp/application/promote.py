"""Promote orchestrator (Phase 7a Sprint 2 Task 3).

Workflow:
1. Validate target ('staging' or 'production')
2. Determine source branch (dev for staging, staging for production)
3. Create PR via GitHub API
4. Poll CI check-runs every POLL_INTERVAL_SEC (timeout POLL_TIMEOUT_SEC)
5. On all green: squash-merge
6. Return PromoteResult

Replaces gh CLI dependency.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Literal

import httpx

from ..infrastructure import github_api

REPO_OWNER = "PrasadInfraBeat"
REPO_NAME = "custom_erp"

PROMOTE_FLOW = {
    "staging": ("dev", "staging"),
    "production": ("staging", "production"),
}

POLL_INTERVAL_SEC = 5
POLL_TIMEOUT_SEC = 600


class PromoteError(Exception):
    """Raised when promote workflow fails."""


@dataclass
class PromoteResult:
    target: str
    source_branch: str
    target_branch: str
    pr_number: int
    pr_url: str
    merged: bool
    duration_seconds: float
    check_runs_final: list[dict]


async def do_promote(
    target: str,
    title: str | None = None,
    body: str = "",
    client: httpx.AsyncClient | None = None,
) -> PromoteResult:
    """Promote source -> target via PR + CI poll + auto-merge."""
    if target not in PROMOTE_FLOW:
        raise PromoteError(
            f"Unknown target '{target}'. Use one of: {list(PROMOTE_FLOW.keys())}"
        )
    source, target_branch = PROMOTE_FLOW[target]
    pr_title = title or f"Promote {source} -> {target_branch}"
    t_start = asyncio.get_event_loop().time()

    own_client = client is None
    if own_client:
        client = httpx.AsyncClient()
    try:
        try:
            pr_number = await github_api.create_pull_request(
                REPO_OWNER, REPO_NAME, source, target_branch, pr_title, body, client=client,
            )
        except github_api.GitHubError as e:
            raise PromoteError(f"PR creation failed: {e}") from e

        pr_url = f"https://github.com/{REPO_OWNER}/{REPO_NAME}/pull/{pr_number}"

        pr_data = await github_api.get_pull_request(REPO_OWNER, REPO_NAME, pr_number, client=client)
        head_sha = pr_data["head"]["sha"]

        check_runs = await _poll_checks(head_sha, client)

        non_success = [
            cr for cr in check_runs
            if cr.get("status") == "completed"
            and cr.get("conclusion") not in ("success", "skipped", "neutral")
        ]
        if non_success:
            failed_names = [cr.get("name") for cr in non_success]
            raise PromoteError(f"CI failed on checks: {failed_names}")

        try:
            merged = await github_api.merge_pull_request(
                REPO_OWNER, REPO_NAME, pr_number, "squash", client=client,
            )
        except github_api.GitHubError as e:
            raise PromoteError(f"Merge failed: {e}") from e

        if not merged:
            raise PromoteError(f"Merge returned merged=false for PR #{pr_number}")

        duration = asyncio.get_event_loop().time() - t_start
        return PromoteResult(
            target=target,
            source_branch=source,
            target_branch=target_branch,
            pr_number=pr_number,
            pr_url=pr_url,
            merged=True,
            duration_seconds=duration,
            check_runs_final=check_runs,
        )
    finally:
        if own_client:
            await client.aclose()


async def _poll_checks(head_sha: str, client: httpx.AsyncClient) -> list[dict]:
    """Poll check-runs until all complete OR timeout."""
    t_start = asyncio.get_event_loop().time()
    while True:
        elapsed = asyncio.get_event_loop().time() - t_start
        if elapsed > POLL_TIMEOUT_SEC:
            raise PromoteError(f"CI poll timeout after {POLL_TIMEOUT_SEC}s")
        check_runs = await github_api.get_check_runs(
            REPO_OWNER, REPO_NAME, head_sha, client=client,
        )
        if check_runs and all(cr.get("status") == "completed" for cr in check_runs):
            return check_runs
        await asyncio.sleep(POLL_INTERVAL_SEC)
