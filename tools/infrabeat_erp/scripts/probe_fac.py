#!/usr/bin/env python3
"""
FAC v2.4.x discovery probe (read-only).

Probes the dev VM (10.1.0.184, site erp.local) to surface:
  - Frappe ping responsiveness (baseline)
  - OAuth 2.0 Authorization Server metadata (RFC 8414)
  - OpenID Connect discovery
  - Frappe OAuth 2.0 endpoint reachability (4 standard endpoints)
  - Frappe Assistant Core (FAC) MCP endpoint paths (3 candidates)
  - OAuth Client DocType reachability
  - Cookie-based session login (T2 reference)

Output:
  - Human-readable summary to stdout
  - JSON artifact at docs/phase5/fac_v2.4.1_dev_probe.json
  - Exit 0 on probe completion (per-endpoint failures recorded, not fatal)

Pure stdlib (urllib, http.cookiejar, json). No venv required.

Usage from repo root:
    python tools\\infrabeat_erp\\scripts\\probe_fac.py
"""

from __future__ import annotations

import http.cookiejar
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# === Probe target =========================================================
DEV_BASE = "http://10.1.0.184"
DEV_SITE = "erp.local"
ADMIN_USER = "Administrator"
ADMIN_PASS = "admin123"
TIMEOUT_SEC = 10

# === Endpoints to probe ===================================================
# (label, method, path) - all GETs except cookie_login (handled separately)
PROBES: list[tuple[str, str, str]] = [
    ("ping",                          "GET", "/api/method/ping"),
    ("oauth_as_metadata_rfc8414",     "GET", "/.well-known/oauth-authorization-server"),
    ("openid_discovery",              "GET", "/.well-known/openid-configuration"),
    ("oauth_authorize_no_args",       "GET", "/api/method/frappe.integrations.oauth2.authorize"),
    ("oauth_token_no_args",           "GET", "/api/method/frappe.integrations.oauth2.get_token"),
    ("oauth_revoke_no_args",          "GET", "/api/method/frappe.integrations.oauth2.revoke_token"),
    ("oauth_openid_profile_no_args",  "GET", "/api/method/frappe.integrations.oauth2.openid_profile"),
    ("fac_mcp_assistant_path",        "GET", "/assistant/mcp"),
    ("fac_mcp_method_path",           "GET", "/api/method/frappe_assistant_core.api.mcp"),
    ("fac_assistant_root",            "GET", "/assistant"),
    ("oauth_client_list_unauth",      "GET", "/api/resource/OAuth Client"),
    ("oauth_client_meta_unauth",      "GET", "/api/method/frappe.client.get?doctype=DocType&name=OAuth%20Client"),
]


# === No-redirect opener so we SEE 302 responses as data ===================
class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Suppress automatic redirect following so probe sees the 302 itself."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # urllib raises HTTPError(code) instead of redirecting


# =========================================================================
# Probe helpers
# =========================================================================
def probe_endpoint(label: str, method: str, path: str, opener) -> dict:
    """Probe one HTTP endpoint, capture status + headers + body preview."""
    url = DEV_BASE + path
    result = {
        "label": label,
        "method": method,
        "url": url,
        "status": None,
        "content_type": None,
        "body_length": None,
        "body_preview": None,
        "redirect_location": None,
        "www_authenticate": None,
        "error": None,
    }
    try:
        req = urllib.request.Request(url, method=method)
        with opener.open(req, timeout=TIMEOUT_SEC) as resp:
            result["status"] = resp.status
            result["content_type"] = resp.headers.get("Content-Type", "")
            body = resp.read()
            result["body_length"] = len(body)
            result["body_preview"] = body.decode("utf-8", errors="replace")[:800]
    except urllib.error.HTTPError as e:
        result["status"] = e.code
        if e.headers:
            result["content_type"] = e.headers.get("Content-Type", "")
            result["redirect_location"] = e.headers.get("Location")
            result["www_authenticate"] = e.headers.get("WWW-Authenticate")
        try:
            body = e.read()
            result["body_length"] = len(body)
            result["body_preview"] = body.decode("utf-8", errors="replace")[:800]
        except Exception:
            pass
    except urllib.error.URLError as e:
        result["error"] = f"URLError: {e.reason}"
    except Exception as e:
        result["error"] = f"{type(e).__name__}: {e}"
    return result


def probe_cookie_login() -> dict:
    """Frappe v15 cookie session login. T2 reference: HTTP Basic returns 401, cookie auth works."""
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    url = DEV_BASE + "/api/method/login"
    data = urllib.parse.urlencode({"usr": ADMIN_USER, "pwd": ADMIN_PASS}).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")

    result = {
        "label": "cookie_login",
        "method": "POST",
        "url": url,
        "status": None,
        "sid_cookie_set": False,
        "cookie_names": [],
        "error": None,
    }
    try:
        with opener.open(req, timeout=TIMEOUT_SEC) as resp:
            result["status"] = resp.status
            for c in cj:
                result["cookie_names"].append(c.name)
                if c.name == "sid":
                    result["sid_cookie_set"] = True
    except urllib.error.HTTPError as e:
        result["status"] = e.code
    except Exception as e:
        result["error"] = f"{type(e).__name__}: {e}"
    return result


# =========================================================================
# Main
# =========================================================================
def main() -> int:
    started = datetime.now(timezone.utc).isoformat()
    print("=" * 72)
    print("FAC v2.4.x discovery probe")
    print(f"Target:  {DEV_BASE}  (site: {DEV_SITE})")
    print(f"Started: {started}")
    print("=" * 72)
    print()

    opener = urllib.request.build_opener(NoRedirectHandler())

    results: list[dict] = []
    for label, method, path in PROBES:
        r = probe_endpoint(label, method, path, opener)
        results.append(r)
        status_disp = str(r["status"]) if r["status"] is not None else "ERR"
        ct = (r["content_type"] or "")[:30]
        loc = f"  -> {r['redirect_location']}" if r.get("redirect_location") else ""
        err = f"  ! {r['error']}" if r.get("error") else ""
        print(f"  [{status_disp:>5}]  {label:<32}  {ct:<30}{loc}{err}")

    print()
    print("-" * 72)
    print("Cookie-based login probe (T2 reference)")
    print("-" * 72)
    login = probe_cookie_login()
    results.append(login)
    print(f"  status:          {login['status']}")
    print(f"  sid_cookie_set:  {login['sid_cookie_set']}")
    print(f"  cookies:         {login['cookie_names']}")
    if login.get("error"):
        print(f"  error:           {login['error']}")

    # === Write artifact ===================================================
    repo_root = Path(__file__).resolve().parents[3]
    out_path = repo_root / "docs" / "phase5" / "fac_v2.4.1_dev_probe.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    artifact = {
        "probe_version": "1",
        "target": DEV_BASE,
        "site": DEV_SITE,
        "started_utc": started,
        "completed_utc": datetime.now(timezone.utc).isoformat(),
        "probe_count": len(results),
        "results": results,
    }
    out_path.write_text(json.dumps(artifact, indent=2, ensure_ascii=False), encoding="utf-8")

    print()
    print("=" * 72)
    print(f"Artifact: {out_path}")
    print(f"Probes:   {len(results)}")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        sys.exit(130)
    except Exception as exc:
        print(f"\nProbe error: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)