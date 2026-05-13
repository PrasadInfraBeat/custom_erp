#!/usr/bin/env python3
"""
mcp_smoke_test.py - End-to-end smoke test of MCP connectivity to FAC.

Reads access_token from tools/infrabeat_erp/.secrets/<vm>_tokens.json
                                                    (from oauth_login.py)
Reads mcp_endpoint from OIDC discovery.

Sends MCP JSON-RPC sequence:
  1. initialize
  2. notifications/initialized
  3. tools/list

Saves the tool catalog to docs/phase5/fac_<vm>_tool_catalog.json
Prints summary table.

Pure stdlib.

Usage:
    python tools/infrabeat_erp/scripts/mcp_smoke_test.py
    python tools/infrabeat_erp/scripts/mcp_smoke_test.py --vm staging --base-url http://10.1.0.185
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# === Defaults =============================================================
DEFAULT_BASE = "http://10.1.0.184"
DEFAULT_VM = "dev"
PROTOCOL_VERSION = "2025-06-18"
CLIENT_NAME = "infrabeat-erp"
CLIENT_VERSION = "0.1.0"
TIMEOUT_SEC = 30


# === Helpers ==============================================================
def discover(base_url: str) -> dict:
    url = f"{base_url}/.well-known/openid-configuration"
    with urllib.request.urlopen(url, timeout=TIMEOUT_SEC) as resp:
        return json.loads(resp.read().decode("utf-8"))


def load_tokens(secrets_dir: Path, vm: str) -> dict:
    f = secrets_dir / f"{vm}_tokens.json"
    if not f.exists():
        raise SystemExit(
            f"ERROR tokens not found at {f}. Run oauth_login.py --vm {vm} first."
        )
    return json.loads(f.read_text(encoding="utf-8"))


def mcp_request(
    endpoint: str,
    token: str,
    method: str,
    params: dict | None = None,
    request_id: int | None = None,
    session_id: str | None = None,
) -> tuple[int, dict, dict]:
    """Send MCP JSON-RPC. Return (status, parsed_body, response_headers)."""
    body: dict = {"jsonrpc": "2.0", "method": method}
    if request_id is not None:
        body["id"] = request_id
    if params is not None:
        body["params"] = params

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "Authorization": f"Bearer {token}",
    }
    if session_id:
        headers["Mcp-Session-Id"] = session_id

    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(endpoint, data=data, method="POST", headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SEC) as resp:
            ct = resp.headers.get("Content-Type", "")
            raw = resp.read()
            resp_headers = {k: v for k, v in resp.headers.items()}

            if not raw:
                # 202 Accepted for notifications
                return resp.status, {}, resp_headers

            text = raw.decode("utf-8", errors="replace")

            if "text/event-stream" in ct:
                # Parse SSE: lines starting with "data: " contain JSON
                for line in text.splitlines():
                    if line.startswith("data: "):
                        try:
                            return resp.status, json.loads(line[6:]), resp_headers
                        except json.JSONDecodeError:
                            continue
                return resp.status, {}, resp_headers

            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                parsed = {"_raw_text": text[:500]}

            # Unwrap Frappe-style {"message": <jsonrpc>} only if inner looks like JSON-RPC
            if isinstance(parsed, dict) and isinstance(parsed.get("message"), dict):
                inner = parsed["message"]
                if any(k in inner for k in ("jsonrpc", "result", "error")):
                    parsed = inner
            return resp.status, parsed, resp_headers
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = {"_raw_text": raw[:500]}
        resp_headers = {k: v for k, v in (e.headers or {}).items()}
        return e.code, parsed, resp_headers


def get_session_id(headers: dict) -> str | None:
    for k, v in headers.items():
        if k.lower() == "mcp-session-id":
            return v
    return None


# === Main =================================================================
def main() -> int:
    ap = argparse.ArgumentParser(
        description="MCP smoke test against FAC's handle_mcp endpoint."
    )
    ap.add_argument("--base-url", default=DEFAULT_BASE)
    ap.add_argument("--vm", default=DEFAULT_VM,
                    choices=("dev", "staging", "production"))
    ap.add_argument("--secrets-dir", default="tools/infrabeat_erp/.secrets")
    ap.add_argument("--catalog-out", default="docs/phase5",
                    help="Directory to save tool catalog JSON")
    args = ap.parse_args()

    print("=" * 64)
    print(f"MCP smoke test ({args.vm})")
    print(f"  Base URL: {args.base_url}")
    print("=" * 64)

    secrets_dir = Path(args.secrets_dir)
    tokens = load_tokens(secrets_dir, args.vm)
    access_token = tokens.get("access_token")
    if not access_token:
        print("ERROR no access_token in tokens file")
        return 2
    print(f"  access_token: {access_token[:16]}... (loaded)")

    print("\n[0/3] OIDC discovery for mcp_endpoint...")
    disc = discover(args.base_url)
    mcp_endpoint = disc.get("mcp_endpoint")
    if not mcp_endpoint:
        print("ERROR mcp_endpoint missing from OIDC discovery")
        return 2
    print(f"  mcp_endpoint = {mcp_endpoint}")

    # 1. initialize
    print("\n[1/3] initialize...")
    init_params = {
        "protocolVersion": PROTOCOL_VERSION,
        "capabilities": {},
        "clientInfo": {"name": CLIENT_NAME, "version": CLIENT_VERSION},
    }
    status, resp, hdrs = mcp_request(
        mcp_endpoint, access_token, "initialize",
        params=init_params, request_id=1,
    )
    print(f"  HTTP {status}")
    if "error" in resp:
        print(f"  ERROR JSON-RPC error: {json.dumps(resp.get('error'), indent=2)}")
        return 3
    if status not in (200, 201):
        body_preview = json.dumps(resp, indent=2)[:800]
        print(f"  ERROR non-2xx response. Body:\n{body_preview}")
        return 3

    result = resp.get("result", {})
    server_info = result.get("serverInfo", {})
    server_caps = result.get("capabilities", {})
    server_proto = result.get("protocolVersion")
    print(f"  serverInfo:      {server_info.get('name')} v{server_info.get('version')}")
    print(f"  protocolVersion: {server_proto}")
    print(f"  capabilities:    "
          f"tools={bool(server_caps.get('tools'))} "
          f"resources={bool(server_caps.get('resources'))} "
          f"prompts={bool(server_caps.get('prompts'))} "
          f"logging={bool(server_caps.get('logging'))}")

    session_id = get_session_id(hdrs)
    if session_id:
        print(f"  Mcp-Session-Id:  {session_id}")

    # 2. notifications/initialized
    print("\n[2/3] notifications/initialized...")
    status, resp, _ = mcp_request(
        mcp_endpoint, access_token, "notifications/initialized",
        session_id=session_id,
    )
    print(f"  HTTP {status} (notification - no JSON-RPC response expected)")

    # 3. tools/list
    print("\n[3/3] tools/list...")
    status, resp, _ = mcp_request(
        mcp_endpoint, access_token, "tools/list",
        request_id=2, session_id=session_id,
    )
    print(f"  HTTP {status}")
    if "error" in resp:
        print(f"  ERROR JSON-RPC error: {json.dumps(resp.get('error'), indent=2)}")
        return 4
    if status not in (200, 201):
        body_preview = json.dumps(resp, indent=2)[:800]
        print(f"  ERROR non-2xx. Body:\n{body_preview}")
        return 4

    tools = resp.get("result", {}).get("tools", [])
    print(f"  Tools advertised: {len(tools)}")

    # Save catalog
    catalog_dir = Path(args.catalog_out)
    catalog_dir.mkdir(parents=True, exist_ok=True)
    catalog_file = catalog_dir / f"fac_{args.vm}_tool_catalog.json"
    catalog_file.write_text(json.dumps(tools, indent=2), encoding="utf-8")

    # Pretty-print catalog
    print()
    print("=" * 78)
    print(f"FAC Tool Catalog ({args.vm}) - {len(tools)} tools")
    print("=" * 78)
    for t in tools:
        name = t.get("name", "?")
        desc = (t.get("description") or "").replace("\n", " ").strip()
        if len(desc) > 60:
            desc = desc[:57] + "..."
        print(f"  {name:<36}  {desc}")
    print("=" * 78)
    print(f"\nCatalog saved: {catalog_file}")
    print("\nPhase 5 keystone proven: laptop -> OAuth Bearer -> FAC handle_mcp -> live tool catalog.")
    print("End-to-end MCP connectivity on dev VM is WORKING.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        sys.exit(130)
