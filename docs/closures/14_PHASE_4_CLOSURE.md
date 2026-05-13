# Phase 4 Closure — Production Provisioning + FAC Across All Environments

**Date:** 2026-05-05
**Status:** CLOSED
**Predecessor:** Phase 3 (DocType + Skills + Hooks)
**Successor:** Phase 5 (MCP Integration via Skill-Based Architecture)

---

## Phase 4 Scope

| Block | Description | Status |
|---|---|---|
| c1 | Repo cleanup (PR #3 merged at 388b6dd) | DONE |
| c2 | SSH passwordless key auth across 3 VMs | DONE |
| c3 | Provision production VM (system pkgs, bench, custom_erp, production mode) | DONE |
| c4 | FAC install on production | DONE |
| c4b | FAC install on staging (scope discovered mid-phase) | DONE |
| c5 | MCP server registration | DEFERRED to Phase 5 |
| c6 | Closure documentation (this file) | DONE |

---

## Acceptance Criteria — All Met

1. All 3 VMs operational (dev .184, staging .185, prod .186)
2. custom_erp v0.0.1 deployed across all 3 with branch-appropriate site naming
3. FAC v2.4.1 installed on all 3 sites
4. HTTP 200 on homepage for all 3 endpoints
5. `bench --site <site> list-apps` reports 4 apps on staging and prod (frappe, erpnext, custom_erp, frappe_assistant_core); dev verified by pyproject.toml + version
6. `bench migrate` clean across all 3
7. GitHub branches dev/staging/production all at SHA 388b6dd

---

## Evidence — 3-VM Verification Snapshot

Captured 2026-05-05 15:59 IST.

~~~
================================================================
  PHASE 4 CLOSURE VERIFICATION - 3-VM SNAPSHOT
================================================================

--- DEV (10.1.0.184, bench user: frappe, site: erp.local) ---
-rw-rw-r-- 1 frappe frappe 4710 May  4 10:40 /home/frappe/frappe-bench/apps/frappe_assistant_core/pyproject.toml

FAC version: version = "2.4.1"
Branch:
Homepage HTTP: 200

--- STAGING (10.1.0.185, bench user: erpadmin, site: erp.staging) ---

frappe                15.107.0 version-15
erpnext               15.106.0 version-15
custom_erp            0.0.1    staging
frappe_assistant_core 2.4.1    main

Homepage HTTP: 200

--- PROD (10.1.0.186, bench user: erpadmin, site: erp.production) ---

frappe                15.107.1 version-15
erpnext               15.106.0 version-15
custom_erp            0.0.1    production
frappe_assistant_core 2.4.1    main

Homepage HTTP: 200

================================================================
~~~

---

## Final State Summary

| Property | Dev | Staging | Prod |
|---|---|---|---|
| IP | 10.1.0.184 | 10.1.0.185 | 10.1.0.186 |
| SSH user | erpadmin | erpadmin | erpadmin |
| Bench user | frappe | erpadmin | erpadmin |
| Bench path | /home/frappe/frappe-bench | /home/erpadmin/frappe-bench | /home/erpadmin/frappe-bench |
| Site | erp.local | erp.staging | erp.production |
| Branch | dev | staging | production |
| Mode | bench dev | production | production |
| FAC source | clinu/frappe_assistant_core | buildswithpaul/Frappe_Assistant_Core | clinu/frappe_assistant_core |
| FAC version | 2.4.1 | 2.4.1 | 2.4.1 |
| Frappe | 15.107.0 | 15.107.0 | 15.107.1 |
| ERPNext | 15.106.0 | 15.106.0 | 15.106.0 |

**Note:** Dev and Prod were installed before upstream URL was discovered. Functionally identical code at v2.4.1. Next FAC refresh should re-install both from `buildswithpaul/Frappe_Assistant_Core` for source-of-truth consistency (carried as TODO F1).

---

## Lessons Logged (L13-L23)

### L13: Empty __init__.py files cross-platform
Empty `__init__.py` files committed on Windows can fail to extract cleanly via git checkout on Linux. Always add minimal content like `# package marker`.

### L14: bench setup production needs Ansible/fail2ban
`bench setup production` requires fail2ban + Ansible packages and tries to install them via apt. On a clean Ubuntu 22.04 box without those, it errors out. Workaround: skip the wrapper, use `bench setup supervisor` + `bench setup nginx` manually, then enable services.

### L15: nginx log_format on Ubuntu 22.04
Ubuntu 22.04 nginx package does not define `log_format main` in nginx.conf. Frappe generated configs assume it. Fix: drop `/etc/nginx/conf.d/00-log-format.conf` with the `main` format definition before reloading nginx.

### L16: --skip-redis-config-generation harms production
`bench init --skip-redis-config-generation` leaves redis configs missing. Supervisor BACKOFF results when starting. Run `bench setup redis` after init to regenerate redis configs.

### L17: Frappe v15 redis topology
Frappe v15 uses redis_cache (port 13000) + redis_queue (port 11000) only. No separate redis_socketio (port 12000). Do not write health checks expecting it.

### L18: PowerShell pipe corrupts binary streams
`ssh A "tar c" | ssh B "tar x"` in PowerShell corrupts binary stdout via text-mangling on the wire. Always use SCP relay (file-based) for any binary transfer between remote hosts when laptop is the relay.

### L19: Default remote shell is dash, not bash
Ubuntu 22.04 erpadmin default shell is dash. Heredocs with `if/elif/else/fi` inline fail with cryptic syntax error messages. Use SCP-then-bash pattern (write script to file, scp, run via explicit `bash /tmp/script.sh`) for any non-trivial logic. Avoid backslash-pipe in inline regex patterns.

### L20: Verify which VM hosts a service before mirroring
The "FAC works on staging" assumption was anchored to dev migrate logs being mistaken for staging logs. The "Plugin system initialized: 1 plugins enabled, 17 tools available" line came from `[frappe_assistant_core.api.info:63]` — `info` there is a logger filename, not a method name. Always probe the actual filesystem before assuming layout.

### L21: FAC source of truth
Canonical FAC source is `https://github.com/buildswithpaul/Frappe_Assistant_Core` (upstream). `clinu/frappe_assistant_core` is a fork/mirror — same code at v2.4.1 but stale. Use upstream URL for all new installs.

### L22: FAC v2.4.x architecture forces a Phase boundary
FAC v2.4.x uses HTTP MCP + OAuth 2.0 with per-site dynamic MCP endpoint URLs (discoverable via Desk → FAC Admin). It cannot be naively dropped into `~/.claude.json` as a stdio MCP entry. Integration belongs in a Skill that wraps FAC HTTP API per-VM. Pushing this into Phase 4 would have meant a multi-day OAuth debugging detour. Phase 5 owns it cleanly.

### L23: PowerShell here-string + ssh + remote dash = unterminated quoted string
Inline backslash-pipe regex inside PowerShell here-string passed via `ssh remote "..."` hits remote dash with CRLF line endings, causing "Unterminated quoted string" mid-stream. Always use file-based bash with explicit `bash /tmp/script.sh` invocation for non-trivial discovery scripts.

---

## Open TODOs Carried Forward

- **T1:** `infrabeat-deploy` skill template sudo block needs rework
- **T2:** `infrabeat-smoke-test` uses HTTP Basic auth (Frappe v15 returns 401); migrate to cookie-based session pattern
- **T3:** Audit hooks env var capture untested
- **D1:** Vendor Invoice DocType never committed; lost during cleanup PR. Restore from feature branch.
- **D2:** Ping Check needs restoration to dev (rebase `feature/phase-3-test-doctype` onto new dev tip)
- **D3:** Customer Feedback has only stub controller; full implementation pending
- **F1:** Re-install FAC on dev and prod from upstream `buildswithpaul/Frappe_Assistant_Core` URL for source consistency
- **H1:** Production hardening: SSL/TLS, ufw firewall, automated backups, monitoring (Phase 6)
- **A1:** Convert bash provisioning scripts to Ansible playbooks (Phase 6)

---

## Phase 5 Entry Criteria

**Phase 5 mandate:** MCP Integration via Skill-Based Architecture.

### Design seed: the `infrabeat-erp-query` skill

Rather than registering FAC HTTP + OAuth endpoints directly in `~/.claude.json`, build a Claude Code Skill that:

1. Accepts a natural-language ERPNext query plus optional environment flag (dev/staging/prod)
2. Handles OAuth token exchange + caching internally (refresh tokens, secure local store)
3. Calls FAC MCP HTTP endpoint on the chosen VM
4. Returns formatted results to Claude Code

**Why a skill, not a direct claude.json entry:**
- Swappable transport (HTTP today, stdio tomorrow if FAC ships an stdio bridge)
- Swappable auth (OAuth today, API key tomorrow if FAC adds it)
- Per-VM execution context handled in the skill, not the client
- Matches existing `infrabeat-*` skill pattern
- One claude.json entry registers the skill, not three FAC servers

### Phase 5 prerequisites (before p5-c1 starts)

1. FAC installed on all 3 VMs — DONE (this phase)
2. FAC Admin Desk page rendered + endpoint URL captured per site (5-min browser task)
3. OAuth client registered for each site (3 separate Frappe API Client records)
4. Token storage strategy decided (suggested: encrypted file at `~/.config/infrabeat/tokens.json` with 0600 perms)

### Phase 5 proposed work blocks

| Block | Description |
|---|---|
| p5-c1 | OAuth client registration on all 3 sites |
| p5-c2 | `infrabeat-erp-query` skill scaffold + per-VM routing |
| p5-c3 | Token cache + refresh flow |
| p5-c4 | Smoke tests across 3 VMs |
| p5-c5 | Skill promotion to `~/.claude.json` |
| p5-c6 | Phase 5 closure doc |

---

## Phase 4 Audit Trail

- 2026-05-04: c1 PR #3 cleanup merged at 388b6dd
- 2026-05-04: c2 SSH keys deployed to all 3 VMs
- 2026-05-05: c3 production VM provisioned (system pkgs, bench, custom_erp, supervisor + nginx + redis manually)
- 2026-05-05: c3 verification — http://10.1.0.186 HTTP 200 in 0.37s
- 2026-05-05: c4 FAC v2.4.1 installed on prod from clinu mirror (upstream not yet discovered)
- 2026-05-05: Architectural reflection — staging FAC absence discovered, plan adjusted
- 2026-05-05: c4b FAC v2.4.1 installed on staging from upstream `buildswithpaul/Frappe_Assistant_Core`
- 2026-05-05: 3-VM verification snapshot captured
- 2026-05-05: c6 closure document committed (this file)

---

**Phase 4: CLOSED.**

All 3 VMs verified operational. Phase 5 entry criteria documented. Lessons L13-L23 logged.

— InfraBeat Portal Enterprise Center
