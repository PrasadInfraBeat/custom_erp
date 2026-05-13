"""GitHub PAT storage via OS keyring (Phase 7a Sprint 2 Task 3).

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
