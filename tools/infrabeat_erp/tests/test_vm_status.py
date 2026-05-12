"""Tests for VM status polling (Sprint 1 Task 4, spec C2).

Mocks SshAdapter so tests run without real network calls.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from infrabeat_erp.application.vm_status_poller import (
    _build_status_query,
    _parse_status,
    poll_all,
    poll_vm,
)
from infrabeat_erp.domain.vm_status import VmStatus


def test_vm_status_age_seconds_near_zero():
    now = datetime.now(timezone.utc)
    s = VmStatus(name="dev", host="10.1.0.184", timestamp=now, reachable=True)
    assert s.age_seconds(now) == 0.0


def test_vm_status_is_stale_when_old():
    now = datetime.now(timezone.utc)
    past = now - timedelta(seconds=60)
    s = VmStatus(name="dev", host="10.1.0.184", timestamp=past, reachable=True)
    assert s.is_stale(max_age_seconds=30) is True


def test_build_status_query_uses_repo_path():
    q = _build_status_query("/some/path/apps/custom_erp")
    assert "cd /some/path/apps/custom_erp" in q
    assert "git rev-parse --abbrev-ref HEAD" in q
    assert "git log -1 --format=%ct" in q


def test_parse_status_with_valid_output():
    now = datetime(2026, 5, 11, 12, 0, 0, tzinfo=timezone.utc)
    # last_ts = 1 hour before now in UTC
    last_ts = int(now.timestamp() - 3600)
    output = f"""BRANCH=dev
COMMIT=abc1234
LAST_COMMIT_TS={last_ts}"""
    s = _parse_status("dev", "10.1.0.184", now, output)
    assert s.reachable is True
    assert s.branch == "dev"
    assert s.commit_short == "abc1234"
    assert s.last_commit_age_seconds == 3600


def test_parse_status_treats_NA_as_none():
    now = datetime.now(timezone.utc)
    output = "BRANCH=NA\nCOMMIT=NA\nLAST_COMMIT_TS=0"
    s = _parse_status("dev", "10.1.0.184", now, output)
    assert s.branch is None
    assert s.commit_short is None
    assert s.last_commit_age_seconds is None


def test_poll_vm_returns_unreachable_on_exception():
    class FailingAdapter:
        async def exec(self, host, user, command, timeout=10):
            raise ConnectionError("simulated network error")

    s = asyncio.run(poll_vm(FailingAdapter(), "dev", "10.1.0.184", "erpadmin"))
    assert s.reachable is False
    assert "ConnectionError" in (s.error or "")


def test_poll_vm_returns_degraded_on_nonzero_exit():
    class BadExitAdapter:
        async def exec(self, host, user, command, timeout=10):
            return 1, "", "permission denied"

    s = asyncio.run(poll_vm(BadExitAdapter(), "dev", "10.1.0.184", "erpadmin"))
    assert s.reachable is True
    assert "exit 1" in (s.error or "")


def test_poll_all_returns_one_status_per_vm():
    now = datetime.now(timezone.utc)

    class SuccessAdapter:
        async def exec(self, host, user, command, timeout=10):
            return 0, f"BRANCH=dev\nCOMMIT=abc1234\nLAST_COMMIT_TS={int(now.timestamp())}\n", ""

    vms = [
        {"name": "dev", "host": "10.1.0.184", "user": "erpadmin"},
        {"name": "staging", "host": "10.1.0.185", "user": "erpadmin"},
    ]
    results = asyncio.run(poll_all(SuccessAdapter(), vms))
    assert len(results) == 2
    assert all(r.reachable for r in results)
    assert all(r.branch == "dev" for r in results)
