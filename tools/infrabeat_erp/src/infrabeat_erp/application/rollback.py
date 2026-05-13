"""Phase 7b Sprint 0 Task B - Rollback orchestrator.

CLI: infrabeat-erp rollback {staging|production}

Strategy (PR-based, audit-trail-preserving, no force-push):
1. Read env branch tip C2 from GitHub
2. Walk to C2's first parent C1 (= pre-promote state)
3. Create a new commit via Git Data API with tree=C1.tree, parents=[C2]
   -- effectively reverts C2's changes while staying ahead of env tip
4. Create branch rollback/<env>-to-<C1_sha7>-<utc> pointing at this new commit
5. Open PR rollback-branch -> env
6. Admin-squash-merge (uses PAT admin rights, mirrors Phase 7a promote pattern)
7. Audit recorded automatically via CLI-level audit wrapper (subcommand=rollback)

Production requires --confirm gate (mirrors promote --confirm pattern).
"""
from __future__ import annotations

import asyncio
import datetime as dt
from dataclasses import dataclass
from typing import Optional

import httpx

from infrabeat_erp.infrastructure.pat_store import load_pat, PatNotFound

GITHUB_API_BASE = "https://api.github.com"
REPO_OWNER = "PrasadInfraBeat"
REPO_NAME = "custom_erp"


class RollbackError(Exception):
    """Raised when rollback orchestration fails."""


@dataclass(frozen=True)
class RollbackResult:
    env: str
    rolled_back_from_sha: str
    rolled_back_to_sha: str
    rollback_branch: str
    pr_number: int
    pr_url: str
    merge_sha: str


def _now_utc_stamp() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


async def _get_branch_tip(client: httpx.AsyncClient, branch: str) -> str:
    """Return the SHA at the tip of the given branch."""
    r = await client.get(
        f"{GITHUB_API_BASE}/repos/{REPO_OWNER}/{REPO_NAME}/branches/{branch}"
    )
    if r.status_code == 404:
        raise RollbackError(f"branch not found: {branch}")
    r.raise_for_status()
    return r.json()["commit"]["sha"]


async def _get_commit(client: httpx.AsyncClient, sha: str) -> dict:
    r = await client.get(
        f"{GITHUB_API_BASE}/repos/{REPO_OWNER}/{REPO_NAME}/commits/{sha}"
    )
    if r.status_code == 404:
        raise RollbackError(f"commit not found: {sha}")
    r.raise_for_status()
    return r.json()


async def _create_commit(
    client: httpx.AsyncClient,
    tree_sha: str,
    parent_shas: list,
    message: str,
) -> str:
    r = await client.post(
        f"{GITHUB_API_BASE}/repos/{REPO_OWNER}/{REPO_NAME}/git/commits",
        json={
            "message": message,
            "tree": tree_sha,
            "parents": parent_shas,
        },
    )
    r.raise_for_status()
    return r.json()["sha"]


async def _create_ref(client: httpx.AsyncClient, ref: str, sha: str) -> None:
    r = await client.post(
        f"{GITHUB_API_BASE}/repos/{REPO_OWNER}/{REPO_NAME}/git/refs",
        json={"ref": ref, "sha": sha},
    )
    if r.status_code == 422:
        raise RollbackError(f"ref creation rejected (already exists or invalid): {ref}")
    r.raise_for_status()


async def _create_pr(
    client: httpx.AsyncClient, title: str, head: str, base: str, body: str
) -> dict:
    r = await client.post(
        f"{GITHUB_API_BASE}/repos/{REPO_OWNER}/{REPO_NAME}/pulls",
        json={"title": title, "head": head, "base": base, "body": body},
    )
    r.raise_for_status()
    return r.json()


async def _merge_pr_squash(client: httpx.AsyncClient, pr_number: int) -> dict:
    r = await client.put(
        f"{GITHUB_API_BASE}/repos/{REPO_OWNER}/{REPO_NAME}/pulls/{pr_number}/merge",
        json={"merge_method": "squash"},
    )
    if r.status_code in (405, 409):
        raise RollbackError(
            f"PR #{pr_number} merge rejected (status={r.status_code}): "
            f"{r.json().get('message', 'no detail')}"
        )
    r.raise_for_status()
    return r.json()


async def find_rollback_target(env: str, client: httpx.AsyncClient) -> tuple:
    """Identify the rollback target.

    Returns (current_tip_sha, target_sha, target_tree_sha).
    Raises RollbackError on invalid env, branch-not-found, or no-parent.
    """
    if env not in ("staging", "production"):
        raise RollbackError(f"invalid env (must be staging or production): {env}")
    current_sha = await _get_branch_tip(client, env)
    current = await _get_commit(client, current_sha)
    parents = current.get("parents", [])
    if not parents:
        raise RollbackError(
            f"branch {env} tip {current_sha[:7]} has no parent - cannot rollback"
        )
    # First parent = the env's prior tip (squash-merge target OR merge-commit branch side)
    target_sha = parents[0]["sha"]
    target = await _get_commit(client, target_sha)
    target_tree_sha = target["commit"]["tree"]["sha"]
    return current_sha, target_sha, target_tree_sha


async def do_rollback(
    env: str,
    confirm: bool = False,
    dry_run: bool = False,
    admin: bool = True,
) -> RollbackResult:
    """Execute rollback orchestration for the given env."""
    if env == "production" and not confirm:
        raise RollbackError("production rollback requires --confirm")

    try:
        pat = load_pat()
    except PatNotFound as exc:
        raise RollbackError(f"github PAT missing - run: infrabeat-erp github-pat set ({exc})") from exc

    headers = {
        "Authorization": f"Bearer {pat}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    timeout = httpx.Timeout(30.0)

    async with httpx.AsyncClient(headers=headers, timeout=timeout) as client:
        current_sha, target_sha, target_tree_sha = await find_rollback_target(env, client)
        short_target = target_sha[:7]
        short_current = current_sha[:7]
        rollback_branch = f"rollback/{env}-to-{short_target}-{_now_utc_stamp()}"
        commit_message = (
            f"Rollback {env}: revert from {short_current} to {short_target}"
        )

        if dry_run:
            return RollbackResult(
                env=env,
                rolled_back_from_sha=current_sha,
                rolled_back_to_sha=target_sha,
                rollback_branch=rollback_branch + " (DRY_RUN)",
                pr_number=0,
                pr_url="DRY_RUN",
                merge_sha="DRY_RUN",
            )

        new_commit_sha = await _create_commit(
            client,
            tree_sha=target_tree_sha,
            parent_shas=[current_sha],
            message=commit_message,
        )
        await _create_ref(
            client, ref=f"refs/heads/{rollback_branch}", sha=new_commit_sha
        )

        pr = await _create_pr(
            client,
            title=commit_message,
            head=rollback_branch,
            base=env,
            body=(
                f"Automated rollback of `{env}` from `{short_current}` to `{short_target}`.\n\n"
                f"Generated by `infrabeat-erp rollback {env}`.\n\n"
                f"- Current tip: `{current_sha}`\n"
                f"- Rollback target: `{target_sha}`\n"
                f"- Strategy: PR-based revert via Git Data API (no force-push)\n"
            ),
        )
        pr_number = pr["number"]
        pr_url = pr["html_url"]

        merge_result = await _merge_pr_squash(client, pr_number)
        merge_sha = merge_result.get("sha", "")

        return RollbackResult(
            env=env,
            rolled_back_from_sha=current_sha,
            rolled_back_to_sha=target_sha,
            rollback_branch=rollback_branch,
            pr_number=pr_number,
            pr_url=pr_url,
            merge_sha=merge_sha,
        )


def rollback_sync(
    env: str,
    confirm: bool = False,
    dry_run: bool = False,
    admin: bool = True,
) -> RollbackResult:
    """Synchronous wrapper for CLI use."""
    return asyncio.run(
        do_rollback(env=env, confirm=confirm, dry_run=dry_run, admin=admin)
    )
