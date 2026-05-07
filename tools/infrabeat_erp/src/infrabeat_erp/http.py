"""Sync httpx.Client factory for infrabeat-erp.

Per Phase 5 finding F3, FAC declares streaming=false on its MCP capabilities,
so all HTTP calls in 6B use sync httpx. No AsyncClient is used anywhere.
"""

import httpx


def make_client(
    base_url: str,
    access_token: str | None = None,
    timeout: float = 10.0,
) -> httpx.Client:
    """Build a sync httpx.Client with InfraBeat defaults.

    Sets User-Agent, Accept, and Content-Type headers on every request.
    Adds a Bearer Authorization header when access_token is non-empty.

    Args:
        base_url: Base URL for the target VM (e.g. "http://10.1.0.184").
        access_token: Optional OAuth access token; omitted when None or empty.
        timeout: Per-request timeout in seconds.

    Returns:
        Configured sync httpx.Client. Caller is responsible for closing it.
    """
    headers: dict[str, str] = {
        "User-Agent": "infrabeat-erp/0.1.0",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"

    return httpx.Client(base_url=base_url, headers=headers, timeout=timeout)
