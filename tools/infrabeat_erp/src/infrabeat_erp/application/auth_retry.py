"""Auth retry helper for infrabeat-erp.

Phase 7b Sprint 1 Task 2 (L92): when an MCP/HTTP call returns 401 (token
expired and not auto-refreshed at the http layer), this module triggers
the existing CLI 'infrabeat-erp login <vm>' subcommand as a subprocess
and retries the original operation once.

Also exposes token-TTL inspection helpers used by doctor.check_token_ttl.
The TTL helpers are pure math over the secrets dict shape returned by
secrets_store.load_secrets - no I/O, no side effects.
"""
from __future__ import annotations

import subprocess
import time
from typing import Callable, TypeVar

import httpx

T = TypeVar("T")


class AuthRetryError(Exception):
    """Raised when the relogin subprocess fails or the retry path errors."""


# === Pure helpers (used by doctor + smoke) ================================
def token_ttl_seconds(secrets: dict) -> int | None:
    """Return remaining seconds before access_token expires.

    None if the secrets dict lacks issued_at or expires_in. Negative value
    means the token expired that many seconds ago.
    """
    issued_at = secrets.get("issued_at")
    expires_in = secrets.get("expires_in")
    if issued_at is None or expires_in is None:
        return None
    return int(issued_at + expires_in - time.time())


def needs_refresh(secrets: dict, min_remaining_sec: int = 60) -> bool:
    """Return True if the cached token has less than min_remaining_sec TTL.

    Returns False when TTL info is missing (we treat unknown as fresh to
    avoid spurious relogin loops).
    """
    ttl = token_ttl_seconds(secrets)
    if ttl is None:
        return False
    return ttl < min_remaining_sec


# === 401 detection ========================================================
def is_401(exc: BaseException) -> bool:
    """Best-effort detection of HTTP 401 across httpx and MCP exception types.

    Checks (in order):
      1. httpx.HTTPStatusError.response.status_code == 401
      2. exc.status_code attribute == 401 (custom MCP exception convention)
      3. Class name in {AuthenticationError, MCPAuthenticationError}
      4. Message contains '401' or 'unauthorized' (case-insensitive)
    """
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code == 401
    if getattr(exc, "status_code", None) == 401:
        return True
    if type(exc).__name__ in ("AuthenticationError", "MCPAuthenticationError"):
        return True
    msg = str(exc).lower()
    return "401" in msg or "unauthorized" in msg


# === Re-login + retry wrapper =============================================
def trigger_relogin(vm_alias: str) -> None:
    """Invoke 'infrabeat-erp login <vm>' as a subprocess.

    The CLI login subcommand handles OAuth authorization code + PKCE flow
    (opens browser, waits for callback, persists fresh tokens). On
    success the new token bundle is in the keyring/secrets store.

    Raises AuthRetryError on non-zero exit.
    """
    proc = subprocess.run(
        ["infrabeat-erp", "login", vm_alias],
        capture_output=False,
        check=False,
    )
    if proc.returncode != 0:
        raise AuthRetryError(
            f"relogin subprocess for {vm_alias!r} failed (exit={proc.returncode})"
        )


def call_with_relogin(vm_alias: str, operation: Callable[[], T]) -> T:
    """Call operation; on 401 trigger relogin and retry exactly once.

    Re-raises non-401 exceptions immediately. Re-raises AuthRetryError
    from trigger_relogin without wrapping. Retries operation once after a
    successful relogin; if that retry also 401s, the second 401 is
    propagated (not retried) to avoid infinite loops.
    """
    try:
        return operation()
    except Exception as exc:
        if not is_401(exc):
            raise
        trigger_relogin(vm_alias)
        return operation()