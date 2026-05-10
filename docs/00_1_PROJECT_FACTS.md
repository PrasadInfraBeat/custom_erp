# PROJECT_FACTS — InfraBeat Portal Enterprise Center

> **CRITICAL:** Every code generation, runbook step, deployment plan, or architectural decision Claude produces must respect these facts EXACTLY. Case-sensitivity matters. VM-specific details matter. These are environment truths that don't change between sessions.

> **Last reconciled 2026-05-10 (Phase 6D closure).** Three-VM architecture authoritative. Production VM (`10.1.0.186`) status flipped from "not provisioned" to "operational" per `15_PHASE_5_CLOSURE.md` §10. Dev and Staging FAC empirically at `2.0.0` (verified live this session); Production claimed `2.4.1` per Phase 5, pending re-verification in 6C.4. Phase 6D GitHub Actions pytest CI gate sealed at `dev` tip `98255b0`. Current dev tip: `<6E1_MERGE_SHA>` (Phase 6E.1 sanitization merge; backfilled post-merge). See `04_VM_INVENTORY.md` for per-VM operational detail; this file is the project-wide canonical truth. Document change log at end.

---

## 🖥️ Infrastructure — Three-VM Architecture

InfraBeat operates **three** environment VMs, all on subnet `10.1.0.0/24`. Each has different paths, users, sites, and risk profiles. Cross-VM mistakes are the #1 cause of failed deploys.

| Environment | IP | Role | Status | FAC version |
|---|---|---|---|---|
| 🟢 Dev (ERP0) | `10.1.0.184` | Daily development, hot-reload | ✅ OPERATIONAL | `2.0.0` (verified 2026-05-09) |
| 🟡 Staging (ERP2) | `10.1.0.185` | UAT, pre-production validation | ✅ OPERATIONAL (Stage 1A closed; Phase 6C verified) | `2.0.0` (verified 2026-05-09 — parity with dev) |
| 🔴 Production (ERP1) | `10.1.0.186` | Live business-critical | ✅ OPERATIONAL (Phase 5 verified; pending Phase 6C.4 re-verification) | `2.4.1` (per Phase 5 §10; **may be stale**, see FAC section) |

**For per-VM detail (SSH users, bench paths, site names, branch mapping, FAC State, safety rules) see `04_VM_INVENTORY.md` — that file is canonical.** This table is the project-wide summary only.

### Common to all three VMs

| Item | Value | Notes |
|---|---|---|
| OS | Ubuntu 22.04 LTS | (Dev confirmed `22.04.5`; staging/prod baseline same) |
| ERPNext | v15 | |
| Frappe Framework | v15 | |
| Python | 3.10 | Inside each VM's `frappe-bench/env/` |
| Node.js | 18.x | Required for asset builds |
| Database | MariaDB 10.6+ | Localhost on each VM |
| Redis (cache) | port 13000 | Frappe-managed; system `redis-server` MUST be masked (Stage 1A Gotcha #3) |
| Redis (queue) | port 11000 | |
| Web | port 80 (Nginx) → 8000 (Gunicorn) | Production mode (dev runs `bench start` instead) |
| SocketIO | port 9000 | Real-time updates |
| Network | `10.1.0.0/24` (VMs) ↔ `10.1.1.0/24` (laptop) via inter-subnet routing | VPN required for laptop access |

---

## 🏢 Organization Identity

| Item | Value |
|---|---|
| Company | InfraBeat |
| GitHub Org/User | `PrasadInfraBeat` |
| Primary repo | `github.com/PrasadInfraBeat/custom_erp` (PRIVATE) |
| Default branch | `dev` (NOT `main` — `main` was deleted per `05_GITHUB_WORKFLOW.md` v2) |
| Three branches only | `dev`, `staging`, `production` |
| Current `dev` tip | `5184710` (Phase 6C.3 audit log merge, PR #13, 2026-05-09) |
| Custom App Name | `custom_erp` |
| Module Name (case-sensitive!) | `Custom Erp` |
| Default Country | India |
| Default Currency | INR |
| Default Timezone | Asia/Kolkata |
| Fiscal Year Start | April 1 |

---

## 👥 System Users (use the right one for the right operation)

| User | Type | Use for |
|---|---|---|
| `erpadmin` | sudo / SSH login | Service management on all VMs (`sudo supervisorctl`), system installs (`apt install`), nginx config. **SSH login user on all three VMs.** |
| `frappe` | application user (Dev VM only) | Bench commands, git operations, DocType operations on **Dev VM only** (path `/home/frappe/frappe-bench/`) |
| `erpadmin` (as bench user) | application user (Staging + Prod) | Bench commands, git operations on **Staging and Production** (path `/home/erpadmin/frappe-bench/`) |
| `Administrator` | ERPNext super admin (in-app) | Full access in ERPNext UI; password stored per-VM in keyring service `infrabeat-vm-creds` (see `04_VM_INVENTORY.md` §VM Credential Setup). Rotated post-Phase 6E.1.5 to invalidate any historical exposure. |

**Switch users on Dev VM:** `sudo su - frappe` (real hyphen, NOT em-dash — paste-mangling has caused this to fail historically)

⚠ **The bench user differs across VMs.** Dev = `frappe`. Staging + Prod = `erpadmin`. Don't conflate.

---

## 📁 Critical Paths (per-VM bench root)

| VM | Bench root |
|---|---|
| Dev (.184) | `/home/frappe/frappe-bench/` |
| Staging (.185) | `/home/erpadmin/frappe-bench/` |
| Production (.186) | `/home/erpadmin/frappe-bench/` |

### Dev VM bench layout (representative — staging/prod mirror this under `erpadmin`)
```
~/frappe-bench/
├── apps/
│   ├── frappe/                        # Framework (don't touch)
│   ├── erpnext/                       # ERP modules (don't touch)
│   ├── frappe_assistant_core/         # FAC v2.0.0 on dev+staging / claimed v2.4.1 on prod (don't touch)
│   └── custom_erp/                    # OUR CUSTOM APP
│       ├── .git/
│       ├── .github/                   # CI workflows
│       ├── modules.txt                # ("Custom Erp" — case-sensitive)
│       ├── hooks.py
│       └── custom_erp/                # Module folder (NOTE: nested)
│           ├── __init__.py            # CRITICAL: must exist
│           ├── doctype/
│           │   ├── __init__.py        # CRITICAL: must exist
│           │   └── <doctype_name>/
│           │       ├── __init__.py    # CRITICAL: must exist
│           │       ├── <doctype>.json
│           │       ├── <doctype>.py
│           │       ├── <doctype>.js
│           │       └── test_<doctype>.py
│           └── pyproject.toml
└── sites/<site_name>/                 # erp.local | erp.staging | erp.production
```

---

## 🏷️ Module Name — Exact Casing Required

The ONLY correct module name is **`Custom Erp`**.

- ❌ `Custom ERP` — WRONG (uppercase ERP)
- ❌ `custom_erp` — WRONG (lowercase, no space)
- ❌ `Custom_Erp` — WRONG (underscore not space)
- ✅ `Custom Erp` — CORRECT (capital C, capital E, lowercase rp, single space)

Must match exactly in **three places**:
1. `apps/custom_erp/modules.txt` (file contents)
2. Each `<doctype>.json` `module` field
3. The `tabModule Def` row in MariaDB (`SELECT name, app_name FROM \`tabModule Def\` WHERE app_name='custom_erp';`)

If any of the three drift, Frappe silently 404s the DocType — no error, just "Page not found." Stage 1A burned hours on this.

---

## 📦 ERPNext Modules in Use

1. **Accounting** — Journal Entry, Payment Entry, Invoice
2. **Selling** — Customer, Quotation, Sales Order, Sales Invoice
3. **Buying** — Supplier, Purchase Order, Purchase Receipt, Purchase Invoice
4. **Stock/Inventory** — Item, Warehouse, Stock Entry, Batch, Serial No
5. **HR** — Employee, Attendance, Leave, Payroll, Appraisal
6. **Manufacturing** — BOM, Work Order, Production Plan
7. **CRM** — Lead, Opportunity, Communication, Campaign
8. **Projects** — Project, Task, Timesheet
9. **Assets** — Asset, Asset Maintenance, Asset Repair
10. **Quality** — Quality Inspection, Quality Procedure, Quality Goal
11. **Support** — Issue, Service Level Agreement
12. **Setup** — Company, Branch, Department, Designation
13. **Website** — Web Page, Blog, Website Settings
14. **Integrations** — Webhook, Connected App, OAuth Client (FAC consumes this)

Custom DocTypes live under `custom_erp` module, not under any of the above. Examples: `Customer Visit` (Stage 1A verified working), and others in flight per Phase 5 carryover (Vendor Invoice, Ping Check, Customer Feedback).

---

## 🤖 Frappe Assistant Core (FAC) — AI Integration Layer

FAC is the MCP-speaking server installed inside Frappe on each VM. It's how the laptop CLI (`infrabeat-erp`) and Claude Code talk to ERPNext.

| Aspect | Value |
|---|---|
| Tool count (live, dev + staging) | 17 (byte-equivalent catalog) |
| MCP protocol (Dev + Staging) | `2025-06-18` |
| MCP endpoint path | `/api/method/frappe_assistant_core.api.fac_endpoint.handle_mcp` (post-PR #11 hotfix; was previously `/assistant/mcp` — wrong) |
| OAuth flow | RFC 7591 dynamic registration + RFC 7636 PKCE S256 + browser authcode |
| OIDC discovery | `<base_url>/.well-known/openid-configuration` returns `mcp_endpoint` correctly |
| Token TTL | 3600s — no auto-refresh in CLI today; re-`login` required after expiry |
| Audit log | ✅ Active per Phase 6C.3 (PR #13, `5184710`) — every CLI invocation captures 9 fields to `<cwd>/.audit/<YYYY-MM-DD>.jsonl` |
| ⚠ Version drift | Dev = Staging = `2.0.0` (verified). Production claimed `2.4.1` per Phase 5, but Phase 6B established that `2.4.x` was stale on dev — same staleness may apply to prod. Phase 6C.4 will empirically resolve. |

**17 canonical tools (verified against dev AND staging 2026-05-09):**
`create_document` · `get_document` · `update_document` · `list_documents` · `delete_document` · `submit_document` · `search_documents` · `search_doctype` · `search_link` · `search` · `fetch` · `get_doctype_info` · `generate_report` · `report_list` · `report_requirements` · `run_workflow` · `get_pending_approvals`

`probe_fac` is **no longer present** in v2.0.0 (was in earlier FAC versions, removed).

---

## 🛡️ Security Defaults

- Always use **private** files for sensitive uploads (PII, contracts) — `private/files/` not `public/files/`
- Always check permissions in custom Python methods (`@frappe.whitelist()` with explicit role checks)
- Never log sensitive data (passwords, tokens, full credit card numbers, full SSN-equivalents)
- Backups stored in `~/frappe-bench/sites/<site>/private/backups/`
- API keys, GitHub PATs, FAC tokens **never** in code or git — currently on disk under `<cwd>/.secrets/<vm>.json` (CWD-relative, Phase 6C.1 will promote to OS keyring)
- Production VM access from `infrabeat-erp` CLI is **gated** — Phase 6C.2 introduces `--allow-production` and `--confirm DEPLOY` flags. **Do not run `infrabeat-erp <cmd> production` until 6C.2 lands on `dev`.**
- ✅ Phase 6C.3 introduces JSONL audit log at `<cwd>/.audit/<YYYY-MM-DD>.jsonl` capturing every CLI invocation (PR #13, merged at `5184710`). 9 fields: `timestamp_utc`, `user`, `cli_version`, `pid`, `subcommand`, `vm`, `args`, `exit_code`, `duration_ms`. Forensic-grade observability for every command run.
- Three-branch protection (per `05_GITHUB_WORKFLOW.md` v2): `dev` (default, feature PRs), `staging` (PRs from `dev` only), `production` (PRs from `staging` only + backup gate)

---

## 🚦 Production Mode Checklist (per VM)

Each VM in production mode (Staging + Production VMs always; Dev VM if not running `bench start`) must have these supervisor processes RUNNING. Verify via `sudo supervisorctl status`:

```
frappe-bench-redis:frappe-bench-redis-cache              RUNNING
frappe-bench-redis:frappe-bench-redis-queue              RUNNING
frappe-bench-web:frappe-bench-frappe-web                 RUNNING
frappe-bench-web:frappe-bench-node-socketio             RUNNING
frappe-bench-workers:frappe-bench-frappe-schedule        RUNNING
frappe-bench-workers:frappe-bench-frappe-default-worker-0 RUNNING
frappe-bench-workers:frappe-bench-frappe-short-worker-0   RUNNING
frappe-bench-workers:frappe-bench-frappe-long-worker-0    RUNNING
```

If anything is `BACKOFF` or `STOPPED`, see `00_2_GOTCHAS.md` (especially #3 Redis port conflict and #4 Stale Gunicorn on port 8000) or `OPERATIONS_GUIDE.md`.

**Dev VM** typically runs `bench start` (single-process dev mode) instead of supervisor. If switching dev to production mode, kill any stray gunicorn on port 8000 first (`sudo fuser -k 8000/tcp`).

---

## 🔄 Standard Operating Cadences

| Activity | Frequency | Owner |
|---|---|---|
| Backups (per VM) | Daily auto + before every deploy | Automated (Phase 7+ `infrabeat-backup` skill); manual `bench backup --with-files` until then |
| Log review | Weekly | Tech lead |
| Security patches | Monthly | erpadmin |
| ERPNext upgrades | Quarterly (test in staging first) | Tech lead |
| Staging refresh from prod | Monthly | erpadmin |
| API key / PAT rotation | Every 90 days | Tech lead |
| FAC version reconciliation (dev/staging vs prod drift) | Phase 6E target | Tech lead |
| Audit log retention check | Monthly | Manual until Phase 6E adds `audit prune` subcommand |

---

## 📋 Authoritative Project State Summary (as of 2026-05-09)

**Phase status:**
- Phase 5 (stdlib script baseline): ✅ Sealed (`15_PHASE_5_CLOSURE.md`)
- Phase 6A–6B (typed Python CLI): ✅ Sealed (`16_PHASE_6B_CLOSURE.md`)
- Phase 6C.3 (JSONL audit log): ✅ **Merged on `dev` at `5184710` (PR #13, 2026-05-09)**
- Phase 6C.2 (production guards: `--allow-production`, `--confirm DEPLOY`): 🟡 Next sub-phase
- Phase 6C.1 (keyring promotion): ⏳ Planned after 6C.2
- Phase 6C.4 (closure smoke against staging + prod FAC re-verification): ⏳ Planned after 6C.1
- Phase 6D (CI integration via GitHub Actions for pytest): ✅ **SEALED** (`docs/closures/18_PHASE_6D_CLOSURE.md`)
- Phase 6E (custom skills + L40 endpoint discovery debt retirement + FAC version reconciliation + `.secrets/` and `.audit/` user-home migration): ⏳ Planned
- Phase 7 (InfraBeat Console TUI): ⏳ Planned (per `12_INFRABEAT_CONSOLE_SPEC.md`)

**Working `infrabeat-erp` CLI subcommands** (all read-only; verified live on dev + staging; every invocation auto-audited):
- `register <vm>` — RFC 7591 OAuth client registration
- `login <vm>` — RFC 7636 PKCE auth code flow
- `smoke <vm> [--json]` — MCP `initialize` + `tools/list`
- `query <vm> <doctype> [--filter k=v]... [--limit N] [--json]` — list documents
- `get <vm> <doctype> <name> [--json]` — fetch single document
- `describe <vm> <doctype> [--json]` — show schema
- `search <vm> <text> [--limit N] [--json]` — full-text search

**Coming in remaining Phase 6C sub-phases:**
- `--allow-production` global flag (6C.2)
- `--confirm DEPLOY` interactive prompt (6C.2)
- `migrate-secrets` — move `.secrets/<vm>.json` → OS keyring (6C.1)

**Test posture:** 52 tests collected, 51 passing, 1 skipped (POSIX-only `secrets_store` mode-bit test, correctly bypassed on Windows). Audit module added 5 tests in 6C.3; existing 46 unchanged. Live integration smoke per `16_PHASE_6B_CLOSURE.md` §11 + this session's verification of dev + staging.

**Branch protection:** 5-check CI on every PR (block direct pushes, Python lint, JSON validate, secret scan, require approving review). The `Require approving review` check shows as "failing/pending" until the solo developer self-approves — that's the lifecycle, not a CI bug. PR #13 (6C.3 merge) all 5 checks green. Advisory CI pytest gate active on PRs to all three branches (Phase 6D, PR #19; not platform-enforced — see `docs/closures/18_PHASE_6D_CLOSURE.md` §7 for enforcement posture and Phase 6E path).

**Known debt:**
- Test runs write audit records to `<repo-root>/.audit/<today>.jsonl` because existing CliRunner-based tests in `test_cli.py` don't `chdir` to `tmp_path`. Cosmetic only (`.gitignore` covers it; never committed). Phase 6E user-home migration of `.audit/` eliminates structurally.
- `~/.ssh/github_pat` referenced in `05_GITHUB_WORKFLOW.md` does not exist on the laptop. Either create the file or update the doc. Phase 6C.1 keyring will be the right home.
- `gh` CLI installed on laptop (v2.92.0) but device-flow auth not completed in this session — `gh pr create` blocked, browser fallback used for PR #13.

---

## 📜 Document Change Log

| Date | Change | Source of truth |
|---|---|---|
| 2026-05-09 | Reconciled during Phase 6C kickoff Step 4. Production VM status flipped from "NOT YET PROVISIONED" to "OPERATIONAL". | `15_PHASE_5_CLOSURE.md` §10 |
| 2026-05-09 | Three-VM architecture made authoritative throughout (replaces any single-VM legacy phrasing). | `04_VM_INVENTORY.md` reconciled same day |
| 2026-05-09 | FAC version table added (Dev `2.0.0`, Staging TBD pending Step 5, Prod `2.4.1` pending re-verification). | `infrabeat-erp smoke dev` live + Phase 5 §10 |
| 2026-05-09 | Phase 6C kickoff Step 5: Staging FAC empirically verified at `2.0.0`/17 tools — byte-equivalent with dev. Updated infrastructure table from "TBD" to verified value. Reframed prod claim with stale-claim caveat. | `infrabeat-erp smoke staging` live output |
| 2026-05-09 | Added 17-tool canonical catalog (`probe_fac` removed). | `infrabeat-erp smoke dev` + `infrabeat-erp smoke staging` |
| 2026-05-09 | Added MCP endpoint path post-PR #11 hotfix. | `16_PHASE_6B_CLOSURE.md` §3, §8 Debt 1 |
| 2026-05-09 | Added `infrabeat-erp` CLI subcommand inventory + Phase 6C upcoming additions. | `16_PHASE_6B_CLOSURE.md` §4, §9 |
| 2026-05-09 | Added 5-check CI lifecycle clarification (the "approving review" check is solo-dev self-approval, not a CI bug). | Live PR #12 + PR #13 inspection 2026-05-09 |
| 2026-05-09 | Network topology updated (laptop subnet `10.1.1.0/24` vs VMs `10.1.0.0/24` via inter-subnet routing). | Network probe 2026-05-09 |
| 2026-05-09 | **Phase 6C.3 audit log merged on `dev` at `5184710` (PR #13).** Added FAC State audit-capture rows per VM. Updated security defaults bullet. Updated phase status. Added 9-field audit record schema. Test count 46→51. Documented test-pollution debt for Phase 6E. | PR #13 squash merge |
| 2026-05-10 | **🟢 Phase 6D SEALED. Advisory CI pytest gate active (workflow runs but does not block merge — free private repo limitation). Phase 6E will path to real enforcement via repo-public + credentials sanitization.** Workflow `.github/workflows/python-tests.yml` runs on every PR to `dev`/`staging`/`production`. Coverage gate at 70%. Test count unchanged at 70 passed / 1 skipped. | PR #19 + `docs/closures/18_PHASE_6D_CLOSURE.md` + `docs/closures/18_PHASE_6D_CLOSURE.md §7` |
| 2026-05-10 | **Phase 6E.1 SEALED.** Plaintext legacy admin password reference in System Users table sanitized to keyring placeholder. Authoritative credential setup documented in `04_VM_INVENTORY.md` §VM Credential Setup. | PR #<TBD> |

---
