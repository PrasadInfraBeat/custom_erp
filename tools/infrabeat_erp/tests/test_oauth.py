"""Tests for infrabeat_erp.oauth (Phase 6B.2)."""

import dataclasses
import re
import socket
import threading
import time
import urllib.request

import httpx
import pytest
import respx

from infrabeat_erp.oauth import (
    ClientRegistration,
    LoginError,
    RefreshError,
    RegistrationError,
    Tokens,
    _CallbackHandler,
    _generate_code_verifier,
    _generate_state,
    _pkce_challenge,
    clear_discovery_cache,
    refresh,
    register_client,
)


@pytest.fixture(autouse=True)
def _clear_discovery_cache_between_tests():
    clear_discovery_cache()
    yield
    clear_discovery_cache()

BASE_URL = "http://erp.test"
METADATA_URL = f"{BASE_URL}/.well-known/openid-configuration"
REG_ENDPOINT = f"{BASE_URL}/oauth/register"
AUTH_ENDPOINT = f"{BASE_URL}/oauth/authorize"
TOKEN_ENDPOINT = f"{BASE_URL}/oauth/token"

METADATA_JSON = {
    "registration_endpoint": REG_ENDPOINT,
    "authorization_endpoint": AUTH_ENDPOINT,
    "token_endpoint": TOKEN_ENDPOINT,
}

VERIFIER_CHARSET = re.compile(r"^[A-Za-z0-9\-._~]+$")


def _client() -> ClientRegistration:
    return ClientRegistration(
        client_id="cid",
        client_secret=None,
        redirect_uri="http://127.0.0.1:8765/callback",
        registration_endpoint=REG_ENDPOINT,
    )


@respx.mock
def test_register_client_success() -> None:
    respx.get(METADATA_URL).mock(
        return_value=httpx.Response(200, json=METADATA_JSON)
    )
    respx.post(REG_ENDPOINT).mock(
        return_value=httpx.Response(200, json={"client_id": "test-client-abc"})
    )
    result = register_client(BASE_URL)
    assert result.client_id == "test-client-abc"
    assert result.client_secret is None
    assert result.redirect_uri == "http://127.0.0.1:8765/callback"
    assert result.registration_endpoint == REG_ENDPOINT


@respx.mock
def test_register_client_metadata_failure() -> None:
    respx.get(METADATA_URL).mock(return_value=httpx.Response(404))
    with pytest.raises(RegistrationError) as exc:
        register_client(BASE_URL)
    msg = str(exc.value)
    assert "404" in msg or "metadata" in msg


@respx.mock
def test_register_client_registration_failure() -> None:
    respx.get(METADATA_URL).mock(
        return_value=httpx.Response(200, json=METADATA_JSON)
    )
    respx.post(REG_ENDPOINT).mock(
        return_value=httpx.Response(400, text="invalid redirect_uri")
    )
    with pytest.raises(RegistrationError) as exc:
        register_client(BASE_URL)
    assert "invalid redirect_uri" in str(exc.value)


def test_pkce_code_verifier_format() -> None:
    samples = [_generate_code_verifier() for _ in range(5)]
    for v in samples:
        assert 43 <= len(v) <= 128
        assert VERIFIER_CHARSET.match(v) is not None
    assert len(set(samples)) == 5


def test_pkce_challenge_known_vector() -> None:
    verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
    expected = "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"
    assert _pkce_challenge(verifier) == expected


def test_state_parameter_unique() -> None:
    a = _generate_state()
    b = _generate_state()
    assert a != b
    assert len(a) >= 22
    assert len(b) >= 22


@respx.mock
def test_refresh_success() -> None:
    respx.get(METADATA_URL).mock(
        return_value=httpx.Response(200, json=METADATA_JSON)
    )
    respx.post(TOKEN_ENDPOINT).mock(
        return_value=httpx.Response(
            200,
            json={
                "access_token": "new-access",
                "refresh_token": "new-refresh",
                "token_type": "Bearer",
                "expires_in": 3600,
                "scope": "read write",
            },
        )
    )
    before = time.time()
    tokens = refresh(BASE_URL, _client(), "old-refresh")
    assert tokens.access_token == "new-access"
    assert tokens.refresh_token == "new-refresh"
    assert tokens.token_type == "Bearer"
    assert tokens.expires_in == 3600
    assert abs(tokens.issued_at - before) < 2.0


@respx.mock
def test_refresh_invalid_grant() -> None:
    respx.get(METADATA_URL).mock(
        return_value=httpx.Response(200, json=METADATA_JSON)
    )
    respx.post(TOKEN_ENDPOINT).mock(
        return_value=httpx.Response(400, json={"error": "invalid_grant"})
    )
    with pytest.raises(RefreshError) as exc:
        refresh(BASE_URL, _client(), "old-refresh")
    assert "invalid_grant" in str(exc.value)


def test_tokens_dataclass_immutable() -> None:
    t = Tokens(
        access_token="a",
        refresh_token="r",
        token_type="Bearer",
        expires_in=1,
        issued_at=0.0,
        scope="",
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        t.access_token = "X"  # type: ignore[misc]


def test_callback_handler_captures_code() -> None:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()

    handler = _CallbackHandler(port)
    thread = threading.Thread(target=handler.serve, daemon=True)
    thread.start()
    try:
        urllib.request.urlopen(
            f"http://127.0.0.1:{port}/callback?code=test_code&state=test_state",
            timeout=5,
        ).read()
        code, state = handler.wait_for_code(timeout=5.0)
        assert code == "test_code"
        assert state == "test_state"
    finally:
        handler.shutdown()
        thread.join(timeout=5.0)
        assert not thread.is_alive()
