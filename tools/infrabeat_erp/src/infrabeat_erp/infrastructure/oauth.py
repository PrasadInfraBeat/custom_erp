"""OAuth 2.1 + PKCE + Dynamic Client Registration for infrabeat-erp.

Ports the Phase 5 register_client.py and oauth_login.py scripts into a typed,
packaged module. The flow is preserved exactly as proven against Frappe
Assistant Core on dev / staging / production VMs:

    1. Discover OIDC metadata at /.well-known/openid-configuration.
    2. POST RFC 7591 dynamic registration as a public native client
       (token_endpoint_auth_method="none", per Phase 5 decision D3).
    3. Authorization code grant with PKCE S256 method (no "plain" fallback).
    4. Refresh token grant.

All HTTP traffic flows through the sync httpx client factory in
infrabeat_erp.http (Phase 5 finding F3: FAC declares streaming=false, so
sync httpx is sufficient). The localhost callback always binds 127.0.0.1.
"""

import base64
import hashlib
import http.server
import secrets
import threading
import time
import urllib.parse
import webbrowser
from dataclasses import dataclass

from infrabeat_erp.infrastructure.http import make_client

DISCOVERY_PATH = "/.well-known/openid-configuration"
DEFAULT_REDIRECT_URI = "http://127.0.0.1:8765/callback"
CALLBACK_PATH = "/callback"
CALLBACK_HOST = "127.0.0.1"
CLIENT_NAME = "infrabeat-erp"
DEFAULT_SCOPE = "all openid"
CALLBACK_WAIT_SEC = 180.0

_SUCCESS_HTML = (
    "<!doctype html><html><head>"
    "<title>infrabeat-erp - OAuth Success</title></head>"
    "<body style=\"font-family:system-ui;max-width:560px;"
    "margin:6rem auto;padding:1rem\">"
    "<h2 style=\"color:#0a7d3a\">Authorization complete</h2>"
    "<p>You can close this tab and return to your terminal.</p>"
    "</body></html>"
)


# === Dataclasses ==========================================================
@dataclass(frozen=True)
class ClientRegistration:
    """Immutable record of a registered OAuth client."""

    client_id: str
    client_secret: str | None
    redirect_uri: str
    registration_endpoint: str


@dataclass(frozen=True)
class Tokens:
    """Immutable bundle of tokens returned from a token endpoint."""

    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int
    issued_at: float
    scope: str


# === Exceptions ===========================================================
class OAuthError(Exception):
    """Base class for all OAuth failures raised by this module."""


class RegistrationError(OAuthError):
    """Dynamic client registration failed."""


class LoginError(OAuthError):
    """Authorization code grant flow failed."""


class RefreshError(OAuthError):
    """Refresh token grant failed."""


class DiscoveryError(Exception):
    """Default exception when OIDC discovery fails outside an OAuth flow."""


# === Discovery cache ======================================================
_discovery_cache: dict = {}


def clear_discovery_cache() -> None:
    """Clear the in-process OIDC discovery metadata cache."""
    _discovery_cache.clear()


# === Private helpers ======================================================
def _generate_code_verifier() -> str:
    """Return a PKCE code_verifier per RFC 7636 (43-128 unreserved chars)."""
    return secrets.token_urlsafe(64)


def _pkce_challenge(verifier: str) -> str:
    """Return the S256 code_challenge: base64url(SHA-256(verifier)), unpadded."""
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def _generate_state() -> str:
    """Return a CSRF-safe state token (>=22 url-safe chars)."""
    return secrets.token_urlsafe(24)


def discover_oidc_metadata(
    base_url: str,
    *,
    error_cls: type[Exception] = DiscoveryError,
    cache: bool = True,
) -> dict:
    """Fetch OIDC discovery metadata; raise error_cls on HTTP failure.

    Results are memoized per base_url in a process-wide cache when
    cache=True (default). Use clear_discovery_cache() to invalidate.
    """
    if cache and base_url in _discovery_cache:
        return _discovery_cache[base_url]
    with make_client(base_url, access_token=None) as client:
        resp = client.get(DISCOVERY_PATH)
    if resp.status_code != 200:
        raise error_cls(
            f"metadata discovery failed: HTTP {resp.status_code}"
        )
    metadata = resp.json()
    if cache:
        _discovery_cache[base_url] = metadata
    return metadata


def _unwrap(body: object) -> dict:
    """Frappe sometimes wraps responses in {"message": {...}}; unwrap once."""
    if isinstance(body, dict) and isinstance(body.get("message"), dict):
        return body["message"]
    if isinstance(body, dict):
        return body
    return {}


class _CallbackHandler:
    """Localhost HTTP server that captures one OAuth authorization callback.

    Bind 127.0.0.1:<port> on construction; serve() blocks until shutdown().
    wait_for_code() returns (code, state) once the callback arrives, or
    raises LoginError on error response or timeout.
    """

    def __init__(self, port: int) -> None:
        self.port = port
        self._event = threading.Event()
        self._params: dict[str, str] = {}
        self._server = http.server.HTTPServer(
            (CALLBACK_HOST, port), _make_request_handler(self)
        )

    def serve(self) -> None:
        """Block, serving HTTP until shutdown() is called from another thread."""
        self._server.serve_forever()

    def _record(self, params: dict[str, str]) -> None:
        self._params = params
        self._event.set()

    def wait_for_code(self, timeout: float) -> tuple[str, str]:
        """Wait up to timeout seconds; return (code, state) or raise LoginError."""
        if not self._event.wait(timeout=timeout):
            raise LoginError(
                f"timeout after {timeout}s waiting for OAuth callback"
            )
        if "error" in self._params:
            msg = self._params.get("error_description") or self._params["error"]
            raise LoginError(f"authorization failed: {msg}")
        return self._params.get("code", ""), self._params.get("state", "")

    def shutdown(self) -> None:
        """Stop serve_forever() and release the bound socket."""
        self._server.shutdown()
        self._server.server_close()


def _make_request_handler(captor: _CallbackHandler) -> type:
    """Build a BaseHTTPRequestHandler subclass bound to captor."""

    class _Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: object) -> None:
            return

        def do_GET(self) -> None:
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path != CALLBACK_PATH:
                self.send_response(404)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(b"Not found.")
                return
            params = dict(urllib.parse.parse_qsl(parsed.query))
            body = _SUCCESS_HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            captor._record(params)

    return _Handler


# === Public API ===========================================================
def register_client(
    base_url: str,
    redirect_uri: str = DEFAULT_REDIRECT_URI,
) -> ClientRegistration:
    """Register a public native OAuth client via RFC 7591 dynamic registration.

    Discovers the registration_endpoint via OIDC well-known metadata, then
    POSTs the registration payload with token_endpoint_auth_method="none"
    (Phase 5 decision D3: public client, no secret at runtime).

    Args:
        base_url: Frappe site base URL (e.g. "http://10.1.0.184").
        redirect_uri: Callback URL the client will use during login.

    Returns:
        A frozen ClientRegistration carrying the issued client_id,
        an always-None client_secret, the redirect_uri, and the discovered
        registration_endpoint.

    Raises:
        RegistrationError: On any discovery or registration failure.
    """
    metadata = discover_oidc_metadata(base_url, error_cls=RegistrationError)
    reg_endpoint = metadata.get("registration_endpoint")
    if not reg_endpoint:
        raise RegistrationError(
            "registration_endpoint missing from OIDC metadata"
        )

    payload = {
        "client_name": CLIENT_NAME,
        "redirect_uris": [redirect_uri],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",
        "scope": DEFAULT_SCOPE,
        "application_type": "native",
    }

    with make_client(base_url, access_token=None) as client:
        resp = client.post(reg_endpoint, json=payload)

    if resp.status_code not in (200, 201):
        raise RegistrationError(
            f"client registration rejected: HTTP {resp.status_code}: "
            f"{resp.text[:200]}"
        )

    body = _unwrap(resp.json())
    if "client_id" not in body:
        raise RegistrationError(
            f"client_id missing from registration response: {resp.text[:200]}"
        )

    return ClientRegistration(
        client_id=body["client_id"],
        client_secret=None,
        redirect_uri=redirect_uri,
        registration_endpoint=reg_endpoint,
    )


def login_authcode_pkce(
    base_url: str,
    client: ClientRegistration,
    callback_port: int = 8765,
) -> Tokens:
    """Run the OAuth 2.0 authorization-code-with-PKCE flow.

    Generates a PKCE verifier + S256 challenge and a CSRF state token,
    builds the authorization URL, opens it in the user's default browser,
    and waits on a localhost callback server bound to 127.0.0.1:<port>.
    Verifies state on return and exchanges the code for tokens.

    Args:
        base_url: Frappe site base URL.
        client: Registered client from register_client().
        callback_port: Port to bind the localhost callback on.

    Returns:
        A frozen Tokens record. issued_at is set to time.time().

    Raises:
        LoginError: On state mismatch, callback timeout, error response,
            or a non-success HTTP status from the token endpoint.
    """
    metadata = discover_oidc_metadata(base_url, error_cls=LoginError)
    auth_endpoint = metadata["authorization_endpoint"]
    token_endpoint = metadata["token_endpoint"]

    verifier = _generate_code_verifier()
    challenge = _pkce_challenge(verifier)
    state = _generate_state()

    auth_params = {
        "response_type": "code",
        "client_id": client.client_id,
        "redirect_uri": client.redirect_uri,
        "scope": DEFAULT_SCOPE,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    auth_url = f"{auth_endpoint}?{urllib.parse.urlencode(auth_params)}"

    handler = _CallbackHandler(callback_port)
    thread = threading.Thread(target=handler.serve, daemon=True)
    thread.start()

    try:
        webbrowser.open(auth_url, new=2)
        code, returned_state = handler.wait_for_code(timeout=CALLBACK_WAIT_SEC)
        if returned_state != state:
            raise LoginError(
                f"state mismatch: expected {state[:8]}..., "
                f"got {returned_state[:8]}..."
            )

        with make_client(base_url, access_token=None) as http_client:
            resp = http_client.post(
                token_endpoint,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": client.redirect_uri,
                    "client_id": client.client_id,
                    "code_verifier": verifier,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

        if resp.status_code not in (200, 201):
            raise LoginError(
                f"token exchange failed: HTTP {resp.status_code}: "
                f"{resp.text[:200]}"
            )

        body = _unwrap(resp.json())
        if "access_token" not in body:
            raise LoginError(
                f"access_token missing from token response: {resp.text[:200]}"
            )

        return Tokens(
            access_token=body["access_token"],
            refresh_token=body.get("refresh_token", ""),
            token_type=body.get("token_type", "Bearer"),
            expires_in=int(body.get("expires_in", 0)),
            issued_at=time.time(),
            scope=body.get("scope", ""),
        )
    finally:
        handler.shutdown()
        thread.join(timeout=5.0)


def refresh(
    base_url: str,
    client: ClientRegistration,
    refresh_token: str,
) -> Tokens:
    """Exchange a refresh_token for a fresh access_token.

    Re-discovers the token_endpoint via OIDC metadata, then POSTs the
    grant_type=refresh_token form to it with the registered client_id.

    Args:
        base_url: Frappe site base URL.
        client: Registered client whose client_id is sent with the request.
        refresh_token: The refresh_token previously issued.

    Returns:
        A frozen Tokens record. issued_at is set to time.time().

    Raises:
        RefreshError: On any discovery or refresh failure.
    """
    metadata = discover_oidc_metadata(base_url, error_cls=RefreshError)
    token_endpoint = metadata["token_endpoint"]

    with make_client(base_url, access_token=None) as http_client:
        resp = http_client.post(
            token_endpoint,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": client.client_id,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    if resp.status_code not in (200, 201):
        raise RefreshError(
            f"refresh failed: HTTP {resp.status_code}: {resp.text[:200]}"
        )

    body = _unwrap(resp.json())
    if "access_token" not in body:
        raise RefreshError(
            f"access_token missing from refresh response: {resp.text[:200]}"
        )

    return Tokens(
        access_token=body["access_token"],
        refresh_token=body.get("refresh_token", refresh_token),
        token_type=body.get("token_type", "Bearer"),
        expires_in=int(body.get("expires_in", 0)),
        issued_at=time.time(),
        scope=body.get("scope", ""),
    )
