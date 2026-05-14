"""Phase 7b Sprint 1 Task 2 - auth_retry tests (L92 fix)."""
from __future__ import annotations

import time

import httpx
import pytest

from infrabeat_erp.application import auth_retry


# === TTL math =============================================================
def test_token_ttl_seconds_fresh_token():
    secrets = {"issued_at": time.time(), "expires_in": 3600}
    ttl = auth_retry.token_ttl_seconds(secrets)
    assert ttl is not None and 3500 < ttl <= 3600


def test_token_ttl_seconds_expired_token():
    secrets = {"issued_at": time.time() - 4000, "expires_in": 3600}
    ttl = auth_retry.token_ttl_seconds(secrets)
    assert ttl is not None and ttl < 0


def test_token_ttl_seconds_missing_fields_returns_none():
    assert auth_retry.token_ttl_seconds({}) is None
    assert auth_retry.token_ttl_seconds({"issued_at": 0}) is None
    assert auth_retry.token_ttl_seconds({"expires_in": 100}) is None


def test_needs_refresh_fresh_returns_false():
    secrets = {"issued_at": time.time(), "expires_in": 3600}
    assert auth_retry.needs_refresh(secrets, min_remaining_sec=60) is False


def test_needs_refresh_expired_returns_true():
    secrets = {"issued_at": time.time() - 4000, "expires_in": 3600}
    assert auth_retry.needs_refresh(secrets, min_remaining_sec=60) is True


def test_needs_refresh_missing_fields_returns_false():
    """Missing TTL info treated as fresh to avoid spurious relogin loops."""
    assert auth_retry.needs_refresh({}) is False


# === is_401 detection =====================================================
def test_is_401_httpx_status_error_401():
    req = httpx.Request("GET", "https://example.com")
    resp = httpx.Response(401, request=req)
    exc = httpx.HTTPStatusError("Unauthorized", request=req, response=resp)
    assert auth_retry.is_401(exc) is True


def test_is_401_httpx_status_error_non_401():
    req = httpx.Request("GET", "https://example.com")
    resp = httpx.Response(500, request=req)
    exc = httpx.HTTPStatusError("Server error", request=req, response=resp)
    assert auth_retry.is_401(exc) is False


def test_is_401_message_match_unauthorized():
    assert auth_retry.is_401(Exception("HTTP 401 Unauthorized")) is True


def test_is_401_non_auth_exception_returns_false():
    assert auth_retry.is_401(ValueError("some other error")) is False


# === call_with_relogin retry semantics ===================================
def test_call_with_relogin_happy_path_no_retry(monkeypatch):
    """Operation succeeds first try - relogin must not be called."""
    relogin_calls: list[str] = []
    monkeypatch.setattr(
        auth_retry, "trigger_relogin", lambda vm: relogin_calls.append(vm)
    )
    op_calls: list[int] = []

    def op():
        op_calls.append(1)
        return "result"

    assert auth_retry.call_with_relogin("dev", op) == "result"
    assert len(op_calls) == 1
    assert relogin_calls == []


def test_call_with_relogin_retries_on_401(monkeypatch):
    """On 401, relogin called once, then operation retried and succeeds."""
    req = httpx.Request("GET", "https://example.com")
    resp = httpx.Response(401, request=req)
    err = httpx.HTTPStatusError("Unauthorized", request=req, response=resp)

    op_calls: list[int] = []

    def op():
        op_calls.append(1)
        if len(op_calls) == 1:
            raise err
        return "result-after-retry"

    relogin_calls: list[str] = []
    monkeypatch.setattr(
        auth_retry, "trigger_relogin", lambda vm: relogin_calls.append(vm)
    )

    assert auth_retry.call_with_relogin("dev", op) == "result-after-retry"
    assert len(op_calls) == 2
    assert relogin_calls == ["dev"]


def test_call_with_relogin_propagates_non_401():
    """Non-401 exceptions are re-raised; no retry, no relogin."""

    def op():
        raise ValueError("not auth-related")

    with pytest.raises(ValueError, match="not auth-related"):
        auth_retry.call_with_relogin("dev", op)