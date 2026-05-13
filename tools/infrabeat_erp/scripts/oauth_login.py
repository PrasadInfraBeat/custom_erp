#!/usr/bin/env python3
"""
oauth_login.py - OAuth 2.0 Authorization Code + PKCE flow against a Frappe + FAC
instance. Captures access_token + refresh_token, saves to local file.

Reads client_id (and optional client_secret fallback) from:
    tools/infrabeat_erp/.secrets/<vm>_client.json   (created by register_client.py)

Discovers OAuth endpoints via OIDC well-known.

Pure stdlib. No third-party deps.

Usage:
    python tools/infrabeat_erp/scripts/oauth_login.py
    python tools/infrabeat_erp/scripts/oauth_login.py --vm staging --base-url http://10.1.0.185

Output:
    Console: progress + token summary (truncated for safety)
    File:    tools/infrabeat_erp/.secrets/<vm>_tokens.json (gitignored)
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import http.server
import json
import secrets
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path
from queue import Empty, Queue

# === Defaults =============================================================
DEFAULT_BASE = "http://10.1.0.184"
DEFAULT_VM = "dev"
CALLBACK_HOST = "127.0.0.1"
CALLBACK_PORT = 8765
CALLBACK_PATH = "/callback"
TIMEOUT_SEC = 15
CALLBACK_WAIT_SEC = 180  # 3 min for user consent in browser

SUCCESS_HTML = """<!doctype html>
<html><head><title>infrabeat-erp - OAuth Success</title></head>
<body style="font-family:system-ui;max-width:560px;margin:6rem auto;padding:1rem">
<h2 style="color:#0a7d3a">Authorization complete</h2>
<p>You can close this tab and return to your terminal.</p>
</body></html>"""

ERROR_HTML_TPL = """<!doctype html>
<html><head><title>infrabeat-erp - OAuth Error</title></head>
<body style="font-family:system-ui;max-width:560px;margin:6rem auto;padding:1rem">
<h2 style="color:#c0392b">Authorization failed</h2>
<p>{message}</p>
<p>Return to your terminal for details.</p>
</body></html>"""


# === PKCE helpers =========================================================
def gen_pkce() -> tuple[str, str]:
    """Return (verifier, challenge) per RFC 7636. S256 method."""
    verifier = secrets.token_urlsafe(64)  # ~86 chars, URL-safe alphabet
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("ascii")).digest()
    ).rstrip(b"=").decode("ascii")
    return verifier, challenge


# === Discovery + client config ============================================
def discover(base_url: str) -> dict:
    url = f"{base_url}/.well-known/openid-configuration"
    with urllib.request.urlopen(url, timeout=TIMEOUT_SEC) as resp:
        return json.loads(resp.read().decode("utf-8"))


def load_client(secrets_dir: Path, vm: str) -> dict:
    f = secrets_dir / f"{vm}_client.json"
    if not f.exists():
        raise SystemExit(
            f"ERROR client config not found at {f}. "
            f"Run register_client.py --vm {vm} first."
        )
    return json.loads(f.read_text(encoding="utf-8"))


# === Localhost callback server ============================================
class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    queue: Queue  # set by factory in make_handler()

    def log_message(self, fmt, *args):
        # silence default access log on stderr
        pass

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != CALLBACK_PATH:
            self.send_response(404)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Not found.")
            return

        params = dict(urllib.parse.parse_qsl(parsed.query))
        if "error" in params:
            msg = params.get("error_description") or params["error"]
            body = ERROR_HTML_TPL.format(message=msg).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            self.queue.put(("error", params))
            return

        # success
        body = SUCCESS_HTML.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        self.queue.put(("ok", params))


def make_handler(q: Queue):
    """Return a handler class bound to the given queue."""
    return type("BoundCallbackHandler", (_CallbackHandler,), {"queue": q})


def start_callback_server(q: Queue) -> http.server.HTTPServer:
    handler = make_handler(q)
    srv = http.server.HTTPServer((CALLBACK_HOST, CALLBACK_PORT), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


# === Token exchange =======================================================
def exchange_code_for_tokens(
    token_endpoint: str,
    code: str,
    redirect_uri: str,
    client_id: str,
    code_verifier: str,
    client_secret: str | None = None,
) -> tuple[int, dict, str]:
    """POST authorization code + verifier; return (status, body_dict, raw_text)."""
    body = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "code_verifier": code_verifier,
    }
    if client_secret:
        body["client_secret"] = client_secret
    data = urllib.parse.urlencode(body).encode("utf-8")
    req = urllib.request.Request(
        token_endpoint,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SEC) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                parsed = {}
            if isinstance(parsed, dict) and isinstance(parsed.get("message"), dict):
                parsed = parsed["message"]
            return resp.status, parsed, raw
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = {}
        return e.code, parsed, raw


# === Main =================================================================
def main() -> int:
    ap = argparse.ArgumentParser(
        description="OAuth 2.0 Authorization Code + PKCE flow."
    )
    ap.add_argument("--base-url", default=DEFAULT_BASE)
    ap.add_argument("--vm", default=DEFAULT_VM,
                    choices=("dev", "staging", "production"))
    ap.add_argument("--secrets-dir", default="tools/infrabeat_erp/.secrets")
    ap.add_argument("--scope", default=None,
                    help="Override scope from client config")
    ap.add_argument("--no-browser", action="store_true",
                    help="Do not auto-open browser; print URL only")
    args = ap.parse_args()

    print("=" * 64)
    print(f"OAuth Authorization Code + PKCE flow ({args.vm})")
    print(f"  Base URL: {args.base_url}")
    print("=" * 64)

    secrets_dir = Path(args.secrets_dir)
    client = load_client(secrets_dir, args.vm)
    client_id = client["client_id"]
    client_secret = client.get("client_secret")
    redirect_uri = client["redirect_uris"][0]
    scope = args.scope or client.get("scope") or "all openid"
    print(f"  client_id:    {client_id}")
    print(f"  redirect_uri: {redirect_uri}")
    print(f"  scope:        {scope}")
    print()

    # 1. Discover endpoints
    print("[1/4] OIDC discovery...")
    disc = discover(args.base_url)
    auth_endpoint = disc["authorization_endpoint"]
    token_endpoint = disc["token_endpoint"]
    print(f"  authorization_endpoint = {auth_endpoint}")
    print(f"  token_endpoint         = {token_endpoint}")

    # 2. PKCE + state
    verifier, challenge = gen_pkce()
    state = secrets.token_urlsafe(16)
    print(f"\n[2/4] PKCE + state generated")
    print(f"  code_challenge = {challenge[:16]}... (S256)")
    print(f"  state          = {state}")

    # 3. Build auth URL, start callback server, open browser
    auth_params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scope,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    auth_url = f"{auth_endpoint}?{urllib.parse.urlencode(auth_params)}"

    callback_q: Queue = Queue()
    try:
        srv = start_callback_server(callback_q)
    except OSError as e:
        print(f"\n  ERROR cannot bind {CALLBACK_HOST}:{CALLBACK_PORT} - {e}")
        print(f"  Is port {CALLBACK_PORT} in use? Free it and retry.")
        return 2

    print(f"\n[3/4] Callback server listening at "
          f"http://{CALLBACK_HOST}:{CALLBACK_PORT}{CALLBACK_PATH}")
    print(f"  Authorization URL:")
    print(f"  {auth_url}")
    if args.no_browser:
        print("  --no-browser set; open the URL manually.")
    else:
        print("  Opening default browser...")
        webbrowser.open(auth_url, new=2)
    print(f"\n  Waiting for callback (up to {CALLBACK_WAIT_SEC}s)...")

    # 4. Wait for callback
    try:
        result_kind, params = callback_q.get(timeout=CALLBACK_WAIT_SEC)
    except Empty:
        srv.shutdown()
        print(f"\n  ERROR timeout - no callback received in {CALLBACK_WAIT_SEC}s.")
        print("  If you saw the consent screen, verify redirect_uri matches exactly.")
        return 3

    srv.shutdown()

    if result_kind == "error":
        print("\n  ERROR authorization failed:")
        print(f"  error:             {params.get('error')}")
        print(f"  error_description: {params.get('error_description')}")
        return 4

    callback_state = params.get("state")
    callback_code = params.get("code")
    if callback_state != state:
        print("\n  ERROR state mismatch (CSRF check failed)")
        print(f"  expected: {state}")
        print(f"  received: {callback_state}")
        return 5
    if not callback_code:
        print("\n  ERROR no 'code' parameter in callback")
        return 6

    print(f"  Got authorization code: {callback_code[:12]}... (state OK)")

    # 5. Exchange code for tokens
    print(f"\n[4/4] Exchanging code for tokens (PKCE-only first)...")
    status, tokens, raw = exchange_code_for_tokens(
        token_endpoint, callback_code, redirect_uri, client_id, verifier
    )
    if status not in (200, 201) and client_secret:
        print(f"  HTTP {status} on PKCE-only. Retrying with client_secret_post...")
        status, tokens, raw = exchange_code_for_tokens(
            token_endpoint, callback_code, redirect_uri, client_id, verifier,
            client_secret=client_secret,
        )

    if status not in (200, 201):
        print(f"  ERROR HTTP {status}")
        print(f"  Body: {raw[:800]}")
        return 7

    if not tokens.get("access_token"):
        print("  ERROR no access_token in response")
        print(f"  Body: {raw[:800]}")
        return 7

    # Persist
    tokens["_obtained_at"] = int(time.time())
    if "expires_in" in tokens:
        tokens["_expires_at"] = tokens["_obtained_at"] + int(tokens["expires_in"])
    out_file = secrets_dir / f"{args.vm}_tokens.json"
    out_file.write_text(json.dumps(tokens, indent=2), encoding="utf-8")

    print(f"  HTTP {status}, tokens received.")
    print()
    print("=" * 64)
    print("Tokens captured. Summary:")
    at = tokens["access_token"]
    print(f"  access_token:  {at[:24]}... ({len(at)} chars total, full token in file)")
    rt = tokens.get("refresh_token")
    if rt:
        print(f"  refresh_token: {rt[:24]}... ({len(rt)} chars total)")
    else:
        print(f"  refresh_token: <none>")
    print(f"  token_type:    {tokens.get('token_type')}")
    print(f"  expires_in:    {tokens.get('expires_in')}s")
    print(f"  scope:         {tokens.get('scope')}")
    print(f"\n  Saved: {out_file}")
    print("=" * 64)
    print("\nNext: mcp_smoke_test.py to talk MCP to FAC's handle_mcp endpoint.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        sys.exit(130)
