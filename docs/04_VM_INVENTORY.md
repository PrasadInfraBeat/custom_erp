# VM_INVENTORY — InfraBeat Three-Environment Setup

> **CRITICAL:** Each VM has different paths, users, sites, and branches. Claude MUST reference this file before any deployment or remote operation. Cross-VM mistakes are the #1 cause of failed deploys.

> **Last reconciled 2026-05-09 (Phase 6C kickoff Step 4 + 6C.3 closure).** Production VM status flipped from "NOT YET PROVISIONED" to "FULLY OPERATIONAL" per `15_PHASE_5_CLOSURE.md` §10. FAC State subsection added to each VM. Staging FAC State now empirically verified: parity with dev (FAC `2.0.0`, MCP `2025-06-18`, 17 tools). Phase 6C.3 audit log infrastructure merged on `dev` at commit `5184710`. See Document Change Log at end.

---

## 🟢 Development VM (ERP0)

| Item | Value |
|---|---|
| **IP** | `10.1.0.184` |
| **Role** | Daily development, hot-reload coding |
| **Status** | ✅ FULLY OPERATIONAL |
| **OS** | Ubuntu 22.04.5 LTS |
| **SSH user** | `erpadmin` |
| **SSH password** | `Erpinfra@123` |
| **Bench path** | `/home/frappe/frappe-bench/` |
| **Bench user** | `frappe` |
| **Site name** | `erp.local` |
| **Web URL** | `http://10.1.0.184` |
| **Admin login** | `Administrator / admin123` |
| **MariaDB root** | `Erpinfra@123` |
| **Git branch** | `dev` (auto-deploys on push) |
| **Mode** | bench dev (`bench start`) |

### Apps Installed
- ✅ frappe v15
- ✅ erpnext v15
- ✅ frappe-assistant-core v2.0.0 (verified live 2026-05-09)
- ✅ custom_erp (active branch: `dev`)

### FAC State (verified 2026-05-09 via `infrabeat-erp smoke dev`)

| Field | Value |
|---|---|
| FAC version | `2.0.0` |
| MCP protocol | `2025-06-18` |
| Tool count | **17** |
| OAuth registration | RFC 7591 dynamic registration accepted |
| OAuth flow | RFC 7636 PKCE S256 + browser-based authcode flow working |
| MCP endpoint | `/api/method/frappe_assistant_core.api.fac_endpoint.handle_mcp` (post-PR #11 hotfix) |
| OIDC discovery | `/.well-known/openid-configuration` returns `mcp_endpoint` correctly |
| Token TTL | 3600s (no auto-refresh — re-`login` required after expiry) |
| Audit log capture | ✅ Active per Phase 6C.3 (PR #13, merged at `5184710`) |

**17 tools enumerated:** `create_document`, `get_document`, `update_document`, `list_documents`, `delete_document`, `submit_document`, `search_documents`, `search_doctype`, `search_link`, `search`, `fetch`, `get_doctype_info`, `generate_report`, `report_list`, `report_requirements`, `run_workflow`, `get_pending_approvals`. (`probe_fac` is **no longer present** in v2.0.0 — was in earlier FAC versions, removed.)

### Path Conventions on Dev
```
~/frappe-bench/                                    (bench root, /home/frappe)
├── apps/custom_erp/custom_erp/
│   ├── modules.txt                                ("Custom Erp")
│   ├── hooks.py
│   └── custom_erp/                                (module folder, NOTE: nested)
│       ├── __init__.py
│       └── doctype/
│           ├── __init__.py
│           └── customer_visit/
│               ├── customer_visit.json
│               ├── customer_visit.py
│               ├── customer_visit.js
│               └── __init__.py
└── sites/erp.local/
```

---

## 🟡 Staging VM (ERP2)

| Item | Value |
|---|---|
| **IP** | `10.1.0.185` |
| **Role** | UAT, pre-production validation |
| **Status** | ✅ FULLY OPERATIONAL (Stage 1A closed; Phase 6C kickoff verified) |
| **OS** | Ubuntu 22.04 LTS |
| **SSH user** | `erpadmin` |
| **SSH password** | `Erpinfra@123` |
| **Bench path** | `/home/erpadmin/frappe-bench/` ⚠ DIFFERENT FROM DEV |
| **Bench user** | `erpadmin` ⚠ DIFFERENT FROM DEV |
| **Site name** | `erp.staging` ⚠ DIFFERENT FROM DEV |
| **Web URL** | `http://10.1.0.185` |
| **Admin login** | `Administrator / admin123` |
| **Git branch** | `staging` (manual promote from dev) |
| **Mode** | Production (nginx + supervisor) |

### Apps Installed
- ✅ frappe v15
- ✅ erpnext v15
- ✅ frappe-assistant-core v2.0.0 (verified live 2026-05-09 — parity with dev)
- ✅ custom_erp (active branch: `staging`)

### FAC State (verified 2026-05-09 via `infrabeat-erp smoke staging`)

| Field | Value |
|---|---|
| FAC version | `2.0.0` (parity with dev) |
| MCP protocol | `2025-06-18` (parity with dev) |
| Tool count | **17** (byte-equivalent catalog with dev) |
| OAuth registration | RFC 7591 dynamic registration accepted (`client_id=v6cfdr10i3` issued) |
| OAuth flow | RFC 7636 PKCE S256 + browser-based authcode flow working |
| Token TTL | 3600s |
| Audit log capture | ✅ Active per Phase 6C.3 (PR #13, merged at `5184710`) |

**Architectural note:** Dev and Staging are byte-equivalent at the FAC layer. Production is the outlier per `15_PHASE_5_CLOSURE.md` §10 (claimed `2.4.1`). Phase 6C.4 closure smoke (after 6C.2 guards land) will empirically resolve whether the prod claim is current or stale.

### Verified Working (Stage 1A Closure)
- Customer Visit DocType end-to-end
- All supervisor services RUNNING
- Redis on Frappe ports (11000, 13000), system redis disabled (per Stage 1A Gotcha #3)
- API returns 200 for Customer Visit endpoints
- Browser CRUD verified

---

## 🔴 Production VM (ERP1)

| Item | Value |
|---|---|
| **IP** | `10.1.0.186` |
| **Role** | Live production, business-critical |
| **Status** | ✅ FULLY OPERATIONAL (Phase 5 verified — pending Phase 6C.4 re-verification) |
| **OS** | Ubuntu 22.04 LTS |
| **SSH user** | `erpadmin` |
| **SSH password** | `Erpinfra@123` ⚠ ROTATE BEFORE FIRST WRITE OPERATION |
| **Bench path** | `/home/erpadmin/frappe-bench/` (mirrors staging) |
| **Bench user** | `erpadmin` |
| **Site name** | `erp.production` |
| **Web URL** | `http://10.1.0.186` |
| **Admin login** | `Administrator / admin123` (rotate before first write) |
| **Git branch** | `production` (manual promote from staging + backup gate) |
| **Mode** | Production (nginx + supervisor) |

### Apps Installed
- ✅ frappe v15
- ✅ erpnext v15
- ✅ frappe-assistant-core v2.4.1 (per `15_PHASE_5_CLOSURE.md` §10 — version claim PENDING re-verification in 6C.4 since dev's `2.4.x` claim was stale before Phase 6B re-verified to `2.0.0`; the `2.4.1` prod claim may be similarly stale)
- ⚠ custom_erp — **first promotion not yet performed** (production branch awaits first staging-to-prod promotion)

### FAC State (per `15_PHASE_5_CLOSURE.md` §10, claim PENDING re-verification)

| Field | Value |
|---|---|
| FAC version | `2.4.1` (per Phase 5; **may be stale**, see note above) |
| MCP protocol | Not re-tested since Phase 5 |
| Tool count | 17 (matched dev as of Phase 5; staging now confirmed identical catalog) |
| OAuth registration | Anonymous registration accepts HTTP 201 |
| OAuth flow | Not re-tested since Phase 5 |

> **⚠ HARD GATE — DO NOT TALK TO PRODUCTION VM FROM `infrabeat-erp` UNTIL PHASE 6C.2 LANDS.**
>
> Phase 6C.2 introduces the `--allow-production` global flag and `--confirm DEPLOY` interactive gate. Until those guards are merged on `dev`, running any `infrabeat-erp` command against `production` is an unguarded operation against a live business-critical system. The CLI today has **no built-in protection** distinguishing production from dev/staging.
>
> First live re-verification of production FAC state is scheduled for **Phase 6C.4 closure smoke**, after 6C.1 (keyring) + 6C.2 (guards) + 6C.3 (audit) have all merged. **6C.3 is now merged** (PR #13, `5184710`); 6C.2 is the next sub-phase.

> **⚠ FAC VERSION DRIFT.** Dev + Staging both run `2.0.0`. Production claimed at `2.4.1` per Phase 5, but that claim predates Phase 6B's discovery that `2.4.x` was stale on dev. The 17-tool catalog matched as of Phase 5 (and we've re-confirmed dev=staging today). Phase 6C.4 should empirically capture production's actual FAC version. Phase 6E may need to align all three VMs to a single version.

### Production Safety Rules
1. **NEVER deploy to prod without backup first** — automatic via `infrabeat-backup` skill (Phase 7+) or manual `bench backup --with-files` for now
2. **NEVER push directly to `production` branch** — must come via PR from `staging`
3. **Smoke tests MUST pass** post-deploy or auto-rollback fires (Phase 7+)
4. **Audit log entry required** for every prod change — ✅ Phase 6C.3 (PR #13, `5184710`) provides JSONL audit log infrastructure capturing every CLI invocation
5. **Confirmation gate**: User must type `DEPLOY` to confirm prod actions — Phase 6C.2 will introduce `--confirm DEPLOY` interactive prompt
6. **Production guard flag**: User must pass `--allow-production` to any command targeting prod — Phase 6C.2 will introduce the global flag

---

## 🚨 Cross-VM Differences (DON'T MIX UP)

| Aspect | Dev | Staging | Production |
|---|---|---|---|
| Bench path | `/home/frappe/frappe-bench/` | `/home/erpadmin/frappe-bench/` | `/home/erpadmin/frappe-bench/` |
| Bench user | `frappe` | `erpadmin` | `erpadmin` |
| Site name | `erp.local` | `erp.staging` | `erp.production` |
| Branch | `dev` | `staging` | `production` |
| Mode | bench dev | production | production |
| FAC version | `2.0.0` (verified) | `2.0.0` (verified — parity with dev) | `2.4.1` (Phase 5 claim, pending re-verification) |
| Audit log capture | ✅ Active | ✅ Active | ✅ Will activate on first prod-targeted CLI run after 6C.2 guards land |
| Risk tolerance | High (break freely) | Low (careful) | Zero (mandatory backup + 6C.2 guards) |

---

## 🌐 Network Topology

- All 3 VMs on subnet `10.1.0.0/24`
- Laptop on `10.1.1.0/24` reaching VMs via inter-subnet routing (verified 2026-05-09; the inter-subnet router is a third-party reliability factor independent of VM health — transient ConnectTimeouts can originate at the router)
- Internal network (VPN required for external access)
- Inter-VM SSH: must be configured with key trust (currently password-based)
- GitHub access: outbound HTTPS allowed

---

## 🔐 SSH Key Trust Plan

Target state:
```
laptop → dev (key auth)
laptop → staging (key auth)
laptop → production (key auth)
staging → dev (key auth, for cross-checks)
staging → production (key auth, for backup orchestration)
```

Current state:
- Password auth only (must migrate to keys)
- ⚠ `~/.ssh/github_pat` referenced in `05_GITHUB_WORKFLOW.md` does not exist on the laptop (verified 2026-05-09 during `gh` auth setup). Either create the file or update the workflow doc. Phase 6C.1 keyring promotion is the right home for this PAT alongside FAC tokens — one credential store, one access pattern.
- `gh` CLI installed (v2.92.0) but device-flow auth not completed in this session — to use `gh pr create` etc. in future sub-phases, complete `gh auth login` once.

---

## 📍 Quick Reference for Claude Code

When Claude sees:
- "deploy to dev" → SSH to `erpadmin@10.1.0.184`, work in `/home/frappe/frappe-bench/`, site `erp.local`, branch `dev`
- "deploy to staging" → SSH to `erpadmin@10.1.0.185`, work in `/home/erpadmin/frappe-bench/`, site `erp.staging`, branch `staging`
- "deploy to production" → SSH to `erpadmin@10.1.0.186`, work in `/home/erpadmin/frappe-bench/`, site `erp.production`, branch `production`, BACKUP FIRST, **and as of Phase 6C.2 verify `--allow-production` and `--confirm DEPLOY` were both passed**

When Claude is using `infrabeat-erp` CLI:
- All commands look up secrets in `<cwd>/.secrets/<vm>.json` — **stay in `~/Projects/custom_erp`** for the entire workflow until Phase 6C.1 promotes secrets to OS keyring
- Token TTL is 3600s — re-run `infrabeat-erp login <vm>` if you see HTTP 401 (this is expected stale-token behavior, not infrastructure rot)
- Every invocation is captured in `<cwd>/.audit/<YYYY-MM-DD>.jsonl` per Phase 6C.3 — review with `Get-Content .audit/*.jsonl` for forensic analysis
- Never invoke any `infrabeat-erp` command against `production` until Phase 6C.2 guards are merged on `dev`

---

## 📜 Document Change Log

| Date | Change | Source of truth |
|---|---|---|
| 2026-05-09 | Reconciled during Phase 6C kickoff Step 4. Production VM status flipped from "NOT YET PROVISIONED" to "FULLY OPERATIONAL". | `15_PHASE_5_CLOSURE.md` §10 |
| 2026-05-09 | Added FAC State subsection to Dev VM with empirical values: FAC `2.0.0`, MCP `2025-06-18`, 17 tools, OAuth verified. | `infrabeat-erp smoke dev` live output |
| 2026-05-09 | Added FAC State subsection to Production VM: FAC `2.4.1`, 17 tools, anonymous OAuth registration HTTP 201. Marked for re-verification in Phase 6C.4 with stale-claim caveat. | `15_PHASE_5_CLOSURE.md` §10 |
| 2026-05-09 | Phase 6C kickoff Step 5: empirically verified Staging FAC at `2.0.0`/`2025-06-18`/17 tools — byte-equivalent catalog with dev. Replaced TBD placeholder with verified values. Updated cross-VM differences table. | `infrabeat-erp smoke staging` live output |
| 2026-05-09 | Added FAC version drift warning (Dev/Staging `2.0.0` vs Production claimed `2.4.1`) — Phase 6E candidate for resolution. Reframed prod claim as "pending re-verification" since `2.4.x` was stale on dev before Phase 6B. | Comparison of Phase 5 + Phase 6B + Phase 6C kickoff data |
| 2026-05-09 | Added Phase 6C.2 hard gate for production VM access via CLI — no `infrabeat-erp` against prod until guards merge. | `16_PHASE_6B_CLOSURE.md` §9 |
| 2026-05-09 | **Phase 6C.3 merged on `dev` at commit `5184710` (PR #13).** Audit log infrastructure active for every CLI invocation. Updated FAC State tables to reflect audit capture. Updated production safety rule #4. | PR #13 squash merge |
| 2026-05-09 | Added laptop subnet (`10.1.1.0/24`) note in Network Topology — inter-subnet routing observation. | Network probe 2026-05-09 |
| 2026-05-09 | Flagged `~/.ssh/github_pat` does-not-exist drift vs `05_GITHUB_WORKFLOW.md`. Noted `gh` CLI installed but device-flow auth incomplete. | Filesystem check 2026-05-09 |

---
