#!/usr/bin/env python3
"""
register_client.py - Register an OAuth Client on a Frappe + FAC instance
via RFC 7591 Dynamic Client Registration.

Targets a single Frappe site (default: dev VM at http://10.1.0.184).
Pure stdlib, no third-party deps, no venv required.

Usage:
    python tools/infrabeat_erp/scripts/register_client.py
    python tools/infrabeat_erp/scripts/register_client.py --vm staging --base-url http://10.1.0.185
    python tools/infrabeat_erp/scripts/register_client.py --dry-run

Output:
    Console: registration progress + response summary
    File:    tools/infrabeat_erp/.secrets/<vm>_client.json (gitignored)
"""

from __future__ import annotations

import argparse
import http.cookiejar
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# === Defaults =============================================================
DEFAULT_BASE = "http://10.1.0.184"
DEFAULT_VM = "dev"
DEFAULT_CLIENT_NAME = "infrabeat-erp"
DEFAULT_REDIRECT_URI = "http://localhost:8765/callback"
ADMIN_USER = "Administrator"
ADMIN_PASS = os.environ.get("ADMIN_PASSWORD")
if not ADMIN_PASS:
    raise SystemExit(
        "ADMIN_PASSWORD env var not set. Populate from keyring before running:\n"
        "  PowerShell: $env:ADMIN_PASSWORD = python -m keyring get infrabeat-vm-creds dev-admin-password\n"
        "  Bash:       export ADMIN_PASSWORD=$(python -m keyring get infrabeat-vm-creds dev-admin-password)\n"
        "See docs/04_VM_INVENTORY.md ?VM Credential Setup for keyring details."
    )
TIMEOUT_SEC = 15


# === HTTP helpers =========================================================
def discover(base_url: str) -> dict:
    """Fetch OIDC discovery; returns parsed metadata."""
    url = f"{base_url}/.well-known/openid-configuration"
    with urllib.request.urlopen(url, timeout=TIMEOUT_SEC) as resp:
        return json.loads(resp.read().decode("utf-8"))


def cookie_login_opener(base_url: str) -> urllib.request.OpenerDirector:
    """Establish authenticated session; return opener carrying the cookies."""
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    url = f"{base_url}/api/method/login"
    data = urllib.parse.urlencode(
        {"usr": ADMIN_USER, "pwd": ADMIN_PASS}
    ).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    with opener.open(req, timeout=TIMEOUT_SEC):
        pass
    return opener


def post_registration(
    endpoint: str,
    payload: dict,
    opener: urllib.request.OpenerDirector | None = None,
) -> tuple[int, dict, str]:
    """POST registration as JSON. Returns (status, parsed_body_dict, raw_text)."""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        endpoint,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    if opener is None:
        opener = urllib.request.build_opener()
    with opener.open(req, timeout=TIMEOUT_SEC) as resp:
        body = resp.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            parsed = {}
        # Frappe sometimes wraps responses in {"message": {...}}; unwrap.
        if isinstance(parsed, dict) and isinstance(parsed.get("message"), dict):
            parsed = parsed["message"]
        return resp.status, parsed, body


# === Main =================================================================
def main() -> int:
    ap = argparse.ArgumentParser(
        description="Register an OAuth Client via RFC 7591 dynamic registration."
    )
    ap.add_argument("--base-url", default=DEFAULT_BASE,
                    help=f"Frappe site base URL (default: {DEFAULT_BASE})")
    ap.add_argument("--vm", default=DEFAULT_VM,
                    choices=("dev", "staging", "production"),
                    help=f"VM label for output filename (default: {DEFAULT_VM})")
    ap.add_argument("--client-name", default=DEFAULT_CLIENT_NAME,
                    help=f"OAuth client name (default: {DEFAULT_CLIENT_NAME})")
    ap.add_argument("--redirect-uri", default=DEFAULT_REDIRECT_URI,
                    help=f"OAuth redirect URI (default: {DEFAULT_REDIRECT_URI})")
    ap.add_argument("--out-dir", default="tools/infrabeat_erp/.secrets",
                    help="Output directory for client JSON (gitignored)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print the request payload but do not send it")
    args = ap.parse_args()

    print("=" * 64)
    print(f"OAuth Client Registration ({args.vm})")
    print(f"  Base URL: {args.base_url}")
    print(f"  Client:   {args.client_name}")
    print(f"  Redirect: {args.redirect_uri}")
    print("=" * 64)

    # 1. Discover registration endpoint
    print("\n[1/3] OIDC discovery...")
    try:
        discovery = discover(args.base_url)
    except Exception as e:
        print(f"  ERROR discovery failed: {type(e).__name__}: {e}")
        return 2
    reg_endpoint = discovery.get("registration_endpoint")
    if not reg_endpoint:
        print("  ERROR registration_endpoint missing from OIDC discovery.")
        print(f"  Discovery keys: {sorted(discovery.keys())}")
        return 2
    print(f"  registration_endpoint = {reg_endpoint}")

    # 2. Build RFC 7591 payload
    payload = {
        "client_name": args.client_name,
        "redirect_uris": [args.redirect_uri],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",
        "scope": "all openid",
        "application_type": "native",
    }
    print("\n[2/3] Registration payload (RFC 7591):")
    print(json.dumps(payload, indent=2))
    if args.dry_run:
        print("\n--dry-run set; not sending. Exiting.")
        return 0

    # 3. POST. Try anonymous first; fall back to cookie session on 401/403.
    print("\n[3/3] POSTing registration (anonymous attempt)...")
    try:
        status, data, raw = post_registration(reg_endpoint, payload)
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            print(f"  HTTP {e.code} - registration requires auth. Logging in...")
            try:
                opener = cookie_login_opener(args.base_url)
            except Exception as login_err:
                print(f"  ERROR login failed: {type(login_err).__name__}: {login_err}")
                return 3
            print("  Retrying registration with session cookie...")
            try:
                status, data, raw = post_registration(reg_endpoint, payload, opener=opener)
            except urllib.error.HTTPError as e2:
                err = e2.read().decode("utf-8", errors="replace")
                print(f"  ERROR HTTP {e2.code}:\n{err}")
                return 4
        else:
            err = e.read().decode("utf-8", errors="replace")
            print(f"  ERROR HTTP {e.code}:\n{err}")
            return 4

    print(f"  HTTP {status}")
    if status not in (200, 201):
        print(f"  WARN unexpected status. Raw response:\n{raw}")
        return 5

    # Persist
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{args.vm}_client.json"
    out_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    print("\n" + "=" * 64)
    print("Registered. Response summary:")
    print(f"  client_id:                  {data.get('client_id', '<missing>')}")
    secret = data.get("client_secret")
    print(f"  client_secret:              {'<present>' if secret else '<none, public client>'}")
    print(f"  redirect_uris:              {data.get('redirect_uris')}")
    print(f"  grant_types:                {data.get('grant_types')}")
    print(f"  response_types:             {data.get('response_types')}")
    print(f"  scope:                      {data.get('scope')}")
    print(f"  token_endpoint_auth_method: {data.get('token_endpoint_auth_method')}")
    print(f"  client_id_issued_at:        {data.get('client_id_issued_at')}")
    print(f"\n  Saved: {out_file}")
    print("=" * 64)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        sys.exit(130)
