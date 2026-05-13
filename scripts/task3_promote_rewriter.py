"""Task 3: promote subcommand - replace gh CLI with httpx + PAT keyring.

Atomic, self-verifying per L74+L81. Every write is read back; ast.parse all files.
Run from repo root: python scripts/task3_promote_rewriter.py
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "tools" / "infrabeat_erp" / "src" / "infrabeat_erp"
TESTS = REPO / "tools" / "infrabeat_erp" / "tests"

PAT_STORE = SRC / "infrastructure" / "pat_store.py"
GITHUB_API = SRC / "infrastructure" / "github_api.py"
PROMOTE = SRC / "application" / "promote.py"
CLI_PY = SRC / "cli.py"
TEST_PAT = TESTS / "test_pat_store.py"
TEST_GH_API = TESTS / "test_github_api.py"
TEST_PROMOTE = TESTS / "test_promote.py"


PAT_STORE_PY = '''"""GitHub PAT storage via OS keyring (Phase 7a Sprint 2 Task 3).

Lighter than secrets_store.py: PAT is a single token, no Fernet wrap needed
(OS keyring is the encryption boundary).

Service: infrabeat-erp-github
Username: pat
"""
from __future__ import annotations

import keyring
import keyring.errors

KEYRING_SERVICE_GITHUB = "infrabeat-erp-github"
KEYRING_USERNAME_PAT = "pat"


class PatNotFound(Exception):
    """Raised when no GitHub PAT is stored."""


def store_pat(token: str) -> None:
    """Store a GitHub Personal Access Token in OS keyring."""
    if not token or not token.strip():
        raise ValueError("PAT cannot be empty")
    keyring.set_password(KEYRING_SERVICE_GITHUB, KEYRING_USERNAME_PAT, token.strip())


def load_pat() -> str:
    """Load the stored PAT. Raises PatNotFound if not set."""
    token = keyring.get_password(KEYRING_SERVICE_GITHUB, KEYRING_USERNAME_PAT)
    if not token:
        raise PatNotFound("GitHub PAT not stored. Run: infrabeat-erp github-pat set")
    return token


def has_pat() -> bool:
    """Return True if a PAT is stored."""
    return keyring.get_password(KEYRING_SERVICE_GITHUB, KEYRING_USERNAME_PAT) is not None


def clear_pat() -> bool:
    """Remove the stored PAT. Returns True if removed, False if not present."""
    try:
        keyring.delete_password(KEYRING_SERVICE_GITHUB, KEYRING_USERNAME_PAT)
        return True
    except keyring.errors.PasswordDeleteError:
        return False
'''


GITHUB_API_PY = '''"""GitHub REST API client via httpx async (Phase 7a Sprint 2 Task 3).

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
'''


PROMOTE_APP_PY = '''"""Promote orchestrator (Phase 7a Sprint 2 Task 3).

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
'''


TEST_PAT_PY = '''"""Tests for GitHub PAT keyring storage (Task 3)."""
from __future__ import annotations

import pytest

from infrabeat_erp.infrastructure.pat_store import (
    KEYRING_SERVICE_GITHUB,
    KEYRING_USERNAME_PAT,
    PatNotFound,
    clear_pat,
    has_pat,
    load_pat,
    store_pat,
)


def test_store_and_load_pat_roundtrip(monkeypatch):
    store = {}
    monkeypatch.setattr(
        "keyring.set_password",
        lambda svc, user, val: store.update({(svc, user): val}),
    )
    monkeypatch.setattr(
        "keyring.get_password",
        lambda svc, user: store.get((svc, user)),
    )
    store_pat("ghp_test_token_123")
    assert load_pat() == "ghp_test_token_123"


def test_load_pat_raises_when_missing(monkeypatch):
    monkeypatch.setattr("keyring.get_password", lambda svc, user: None)
    with pytest.raises(PatNotFound):
        load_pat()


def test_store_pat_rejects_empty():
    with pytest.raises(ValueError):
        store_pat("")
    with pytest.raises(ValueError):
        store_pat("   ")


def test_has_pat_returns_false_when_missing(monkeypatch):
    monkeypatch.setattr("keyring.get_password", lambda svc, user: None)
    assert has_pat() is False


def test_has_pat_returns_true_when_present(monkeypatch):
    monkeypatch.setattr("keyring.get_password", lambda svc, user: "ghp_xxx")
    assert has_pat() is True


def test_clear_pat_returns_true_when_removed(monkeypatch):
    monkeypatch.setattr("keyring.delete_password", lambda svc, user: None)
    assert clear_pat() is True


def test_clear_pat_returns_false_when_not_present(monkeypatch):
    import keyring.errors
    def raise_err(svc, user):
        raise keyring.errors.PasswordDeleteError("not found")
    monkeypatch.setattr("keyring.delete_password", raise_err)
    assert clear_pat() is False


def test_keyring_service_constants():
    assert KEYRING_SERVICE_GITHUB == "infrabeat-erp-github"
    assert KEYRING_USERNAME_PAT == "pat"
'''


TEST_GH_API_PY = '''"""Tests for GitHub API client (Task 3)."""
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
'''


TEST_PROMOTE_PY = '''"""Tests for promote orchestrator (Task 3)."""
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
'''


CLI_ADDITIONS = '''


# =============================================================================
# Task 3: github-pat group + promote command
# =============================================================================


@main.group(name="github-pat")
def github_pat():
    """Manage GitHub Personal Access Token for promote subcommand."""
    pass


@github_pat.command(name="set")
@click.option("--token", prompt="GitHub PAT (input hidden)", hide_input=True)
def github_pat_set(token):
    """Store a GitHub PAT in OS keyring."""
    from .infrastructure.pat_store import store_pat
    import sys as _sys
    try:
        store_pat(token)
        click.echo("OK: PAT stored in OS keyring (service=infrabeat-erp-github)")
    except ValueError as e:
        click.echo(f"ERROR: {e}", err=True)
        _sys.exit(1)


@github_pat.command(name="clear")
def github_pat_clear():
    """Remove the stored GitHub PAT."""
    from .infrastructure.pat_store import clear_pat
    if clear_pat():
        click.echo("OK: PAT removed from keyring")
    else:
        click.echo("INFO: no PAT was stored")


@github_pat.command(name="check")
def github_pat_check():
    """Check if a PAT is stored (does not display the token)."""
    from .infrastructure.pat_store import has_pat
    if has_pat():
        click.echo("PAT: stored")
    else:
        click.echo("PAT: not stored (run 'infrabeat-erp github-pat set')")


@main.command()
@click.argument("target", type=click.Choice(["staging", "production"]))
@click.option("--title", default=None, help="PR title (default: 'Promote <source> -> <target>')")
@click.option("--body", default="", help="PR body markdown")
@click.option("--confirm", is_flag=True, default=False, help="Required for production")
def promote(target, title, body, confirm):
    """Promote source -> target via PR + CI poll + squash-merge (replaces gh CLI)."""
    import asyncio as _asyncio
    import sys as _sys
    from .application.promote import do_promote, PromoteError

    if target == "production" and not confirm:
        click.echo("ERROR: --confirm required for production promotes", err=True)
        _sys.exit(1)

    click.echo(f"Promoting -> {target}... (may take 1-10 min for CI)")
    try:
        result = _asyncio.run(do_promote(target, title=title, body=body))
        click.echo(f"OK: PR #{result.pr_number} merged into {result.target_branch}")
        click.echo(f"     URL: {result.pr_url}")
        click.echo(f"     Duration: {result.duration_seconds:.1f}s")
    except PromoteError as e:
        click.echo(f"Promote FAILED: {e}", err=True)
        _sys.exit(1)
'''


def write_file(path: Path, content: str, label: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    after = path.read_text(encoding="utf-8")
    if after != content:
        print(f"FAIL: {label} write mismatch ({len(after)} != {len(content)})")
        sys.exit(2)
    try:
        ast.parse(content)
    except SyntaxError as e:
        print(f"FAIL: {label} ast.parse: {e}")
        sys.exit(3)
    print(f"  OK: {label} ({len(content)} bytes, {content.count(chr(10))} lines)")


def main():
    print(f"REPO: {REPO}")
    print("[1/4] Writing new modules...")
    write_file(PAT_STORE, PAT_STORE_PY, "infrastructure/pat_store.py")
    write_file(GITHUB_API, GITHUB_API_PY, "infrastructure/github_api.py")
    write_file(PROMOTE, PROMOTE_APP_PY, "application/promote.py")

    print("[2/4] Writing new test files...")
    write_file(TEST_PAT, TEST_PAT_PY, "tests/test_pat_store.py")
    write_file(TEST_GH_API, TEST_GH_API_PY, "tests/test_github_api.py")
    write_file(TEST_PROMOTE, TEST_PROMOTE_PY, "tests/test_promote.py")

    print("[3/4] Appending CLI additions...")
    cli_src = CLI_PY.read_text(encoding="utf-8")
    if "@main.group(name=\"github-pat\")" in cli_src:
        print("  cli.py already contains github-pat group (idempotent skip)")
    else:
        cli_src += CLI_ADDITIONS
        CLI_PY.write_text(cli_src, encoding="utf-8")
        re_read = CLI_PY.read_text(encoding="utf-8")
        for marker in [
            '@main.group(name="github-pat")',
            '@github_pat.command(name="set")',
            '@github_pat.command(name="clear")',
            '@github_pat.command(name="check")',
            'def promote(target',
        ]:
            if marker not in re_read:
                print(f"  FAIL: marker missing after append: {marker!r}")
                sys.exit(2)
        try:
            ast.parse(re_read)
        except SyntaxError as e:
            print(f"  FAIL: cli.py ast.parse: {e}")
            sys.exit(3)
        print(f"  OK: cli.py now {len(re_read)} bytes (5 new entry points)")

    print("[4/4] All files written and verified.")
    print("")
    print("Next: python -m pytest tools/infrabeat_erp/tests/ -q")


if __name__ == "__main__":
    main()