# PROJECT_FACTS — InfraBeat Portal Enterprise Center

> **CRITICAL:** Every code generation, runbook step, deployment plan, or architectural decision Claude produces must respect these facts EXACTLY. Case-sensitivity matters. VM-specific details matter. These are environment truths that don't change between sessions.

> **Last reconciled 2026-05-10 (Phase 6E FULLY SEALED — both enforcement and debt-retirement tracks).** Phase 6E added composed protections across the platform: squash-only merge enforcement (Phase 6E.0), plaintext credential sanitization across 7 files (PR #21), three-VM credential rotation to 24-char keyring-backed values (Phase 6E.1.5), laptop OS keyring populated with 9 keys across 3 services (Phase 6E.1.5b), repo flipped public (Phase 6E.2), branch ruleset Active with 6 required CI checks + 5 protective rules (Phase 6E.3), dynamic OIDC endpoint discovery (PR #24), PR template universalized (PR #25), audit-log migration to user-home (PR #26), dedicated master-key keyring service (PR #27), OAuth token auto-refresh (PR #28), and a custom `infrabeat-erp-query` Claude Code skill (PR #29). Pytest baseline grew 70-75 monotonically across the track. **Plaintext credentials in repo: ZERO. Plaintext credentials usable against any VM: ZERO.** Current `dev` tip: **`cf3a83c`** (PR #30 — Phase 6E.4+ debt-retirement closure docs merge). See `04_VM_INVENTORY.md` for per-VM operational detail, `18_PHASE_6D_CLOSURE.md` for CI gate inventory, `19_PHASE_6E_CLOSURE.md` for enforcement-track inventory + lessons L53-L65, and `20_PHASE_6E_DEBT_RETIREMENT_CLOSURE.md` for debt-retirement-track inventory + lessons L66-L68.

---

## Infrastructure - Three-VM Architecture

InfraBeat operates **three** environment VMs, all on subnet `10.1.0.0/24`. Each has different paths, users, sites, and risk profiles. Cross-VM mistakes are the #1 cause of failed deploys.

| Environment | IP | Role | Status | FAC version |
|---|---|---|---|---|
| Dev (ERP0) | `10.1.0.184` | Daily development, hot-reload | OPERATIONAL | `2.0.0` (re-verified Phase 6E.4 close 2026-05-10) |
| Staging (ERP2) | `10.1.0.185` | UAT, pre-production validation | OPERATIONAL (Stage 1A closed; Phase 6C.4 verified 2026-05-09) | `2.0.0` (verified 2026-05-09) |
| Production (ERP1) | `10.1.0.186` | Live business-critical | OPERATIONAL (Phase 5 verified, Phase 6C.4 re-verified 2026-05-09) | **`2.0.0`** (empirically verified 2026-05-09) |

**Three-VM byte-equivalent catalog confirmed at Phase 6C close.** The 17-tool catalog is identical across dev, staging, and production. No drift. **Phase 6E architecture validated empirically on dev VM only (Phase 6E.4 close smoke); cross-VM smoke on staging and production deferred to Phase 7+ as outstanding debt.**

**For per-VM detail see `04_VM_INVENTORY.md`.** This table is the project-wide summary only.

### Common to all three VMs

| Item | Value | Notes |
|---|---|---|
| OS | Ubuntu 22.04 LTS | (Dev confirmed `22.04.5`; staging/prod baseline same) |
| ERPNext | v15 | |
| Frappe Framework | v15 | |
| Python | 3.10 | Inside each VMs `frappe-bench/env/` |
| Node.js | 18.x | Required for asset builds |
| Database | MariaDB 10.6+ | Localhost on each VM |
| Redis (cache) | port 13000 | Frappe-managed; system `redis-server` MUST be masked (Stage 1A Gotcha #3) |
| Redis (queue) | port 11000 | |
| Web | port 80 (Nginx) - 8000 (Gunicorn) | Production mode (dev runs `bench start` instead) |
| SocketIO | port 9000 | Real-time updates |
| Network | `10.1.0.0/24` (VMs) - `10.1.1.0/24` (laptop) via inter-subnet routing | VPN required for laptop access; transient ConnectTimeouts at the router are documented (lesson L48) |

---

## Organization Identity

| Item | Value |
|---|---|
| Company | InfraBeat |
| GitHub Org/User | `PrasadInfraBeat` |
| Primary repo | `github.com/PrasadInfraBeat/custom_erp` (**PUBLIC** as of Phase 6E.2) |
| Default branch | `dev` (NOT `main` - `main` was deleted per `05_GITHUB_WORKFLOW.md` v2) |
| Three branches only | `dev`, `staging`, `production` |
| Branch ruleset | **Active** (Phase 6E.3) - "Protected branches (dev/staging/production)" with 6 required CI checks + 5 protective rules (Restrict deletions, Require linear history, Require PR before merging, Require status checks to pass, Block force pushes) |
| Merge convention | **Squash-only enforced at repo level** (Phase 6E.0) - `Allow merge commits` and `Allow rebase merging` disabled; default squash commit message = "Pull request title and description"; head branches auto-deleted on merge |
| **Current `dev` tip** | **`cf3a83c`** (PR #30 - Phase 6E.4+ debt-retirement closure docs merge) |
| Custom App Name | `custom_erp` |
| Module Name (case-sensitive!) | `Custom Erp` |
| Default Country | India |
| Default Currency | INR |
| Default Timezone | Asia/Kolkata |
| Fiscal Year Start | April 1 |

---

## System Users (use the right one for the right operation)

| User | Type | Use for |
|---|---|---|
| `erpadmin` | sudo / SSH login | Service management on all VMs (`sudo supervisorctl`), system installs (`apt install`), nginx config. **SSH login user on all three VMs.** SSH password rotated Phase 6E.1.5 to 24-char keyring-backed value (`infrabeat-vm-creds/<vm>-ssh`). |
| `frappe` | application user (Dev VM only) | Bench commands, git operations, DocType operations on **Dev VM only** (path `/home/frappe/frappe-bench/`) |
| `erpadmin` (as bench user) | application user (Staging + Prod) | Bench commands, git operations on **Staging and Production** (path `/home/erpadmin/frappe-bench/`) |
| `Administrator` | ERPNext super admin (in-app) | Full access in ERPNext UI. Password rotated Phase 6E.1.5 to 24-char keyring-backed value (`infrabeat-vm-creds/<vm>-admin`). |

**Switch users on Dev VM:** `sudo su - frappe` (real hyphen, NOT em-dash - paste-mangling has caused this to fail historically)

**The bench user differs across VMs.** Dev = `frappe`. Staging + Prod = `erpadmin`. Dont conflate.

---

## Critical Paths (per-VM bench root)

| VM | Bench root |
|---|---|
| Dev (.184) | `/home/frappe/frappe-bench/` |
| Staging (.185) | `/home/erpadmin/frappe-bench/` |
| Production (.186) | `/home/erpadmin/frappe-bench/` |

---

## Module Name - Exact Casing Required

The ONLY correct module name is **`Custom Erp`**.

- `Custom ERP` - WRONG (uppercase ERP)
- `custom_erp` - WRONG (lowercase, no space)
- `Custom_Erp` - WRONG (underscore not space)
- `Custom Erp` - CORRECT (capital C, capital E, lowercase rp, single space)

Must match exactly in **three places**:
1. `apps/custom_erp/modules.txt` (file contents)
2. Each `<doctype>.json` `module` field
3. The `tabModule Def` row in MariaDB

If any of the three drift, Frappe silently 404s the DocType - no error, just "Page not found." Stage 1A burned hours on this.

---

## Frappe Assistant Core (FAC) - Live State

FAC is the MCP-speaking server installed inside Frappe on each VM. **Phase 6C.4 empirically confirmed all 3 VMs at perfect parity. Phase 6E.4 close re-confirmed dev VM only; cross-VM re-validation deferred to Phase 7+.**

| Aspect | Value |
|---|---|
| FAC version (all 3 VMs) | **`2.0.0`** (verified 2026-05-09; dev re-verified 2026-05-10) |
| Tool count (all 3 VMs) | **17** (byte-equivalent catalog) |
| MCP protocol (all 3 VMs) | **`2025-06-18`** |
| MCP endpoint path | `/api/method/frappe_assistant_core.api.fac_endpoint.handle_mcp` (post-PR #11 hotfix); **now read dynamically from OIDC `mcp_endpoint` per Phase 6E.4 (PR #24)** - hardcoded constant retained as fallback with `DeprecationWarning` |
| OAuth flow | RFC 7591 dynamic registration + RFC 7636 PKCE S256 + browser authcode |
| OIDC discovery | `<base_url>/.well-known/openid-configuration` returns `mcp_endpoint` correctly; **consumed at runtime per Phase 6E.4** |
| Token TTL | 3600s - **auto-refresh via `TokenRefreshAuth(httpx.Auth)` per Phase 6E.9 (PR #28)**; re-`login` only required when refresh-token also expired (rare) |
| Audit log | Active per Phase 6C.3 (PR #13, `5184710`); **migrated to user-home `~/.infrabeat-erp/audit/<YYYY-MM-DD>.jsonl` per Phase 6E.6 (PR #26)**; legacy `<cwd>/.audit/` paths still readable via fallback chain |
| Production guard | Active per Phase 6C.2 (PR #14, `c45fc38`) - `--allow-production` flag required for any production-targeted command |
| Keyring storage | Active per Phase 6C.1 (PR #16, `42b1d07`); **master key separated to dedicated `infrabeat-erp-master/master` service per Phase 6E.8 (PR #27)** with 5-step backward-compatible resolution + auto-migration |
| Custom Claude Code skills | `infrabeat-smoke-test` + `infrabeat-erp-query` (Phase 6E.10, PR #29) - Claude Code routes ERPNext data questions through CLI subcommands |
| `gh` CLI device-flow auth | Completed Phase 6E.7 - `gh pr create` and `gh api repos/.../rulesets` both work without browser fallback |

**17 canonical tools (verified against ALL 3 VMs in Phase 6C.4):**
`create_document` - `get_document` - `update_document` - `list_documents` - `delete_document` - `submit_document` - `search_documents` - `search_doctype` - `search_link` - `search` - `fetch` - `get_doctype_info` - `generate_report` - `report_list` - `report_requirements` - `run_workflow` - `get_pending_approvals`

`probe_fac` is **no longer present** in v2.0.0.

---

## Security Defaults

- Always use **private** files for sensitive uploads (PII, contracts) - `private/files/` not `public/files/`
- Always check permissions in custom Python methods (`@frappe.whitelist()` with explicit role checks)
- Never log sensitive data (passwords, tokens, full credit card numbers)
- Backups stored in `~/frappe-bench/sites/<site>/private/backups/`
- API keys, GitHub PATs, FAC tokens **never** in code or git - stored across **three dedicated OS keyring services** on laptop:
  - `infrabeat-erp` - OAuth tokens (one entry per VM: `dev`, `staging`, `production`)
  - `infrabeat-erp-master` - Fernet master key for encrypted-JSON fallback (Phase 6E.8 separation, PR #27)
  - `infrabeat-vm-creds` - 9 VM passwords (3 VMs x {ssh, mariadb-root, admin}), all 24-char rotated values (Phase 6E.1.5)
- **Plaintext credentials in repo: ZERO** as of Phase 6E.1 sanitization (PR #21 covered 7 files including legacy Phase 5 helper scripts, MD docs, and audit log examples).
- **Plaintext credentials usable against any VM: ZERO** as of Phase 6E.1.5 rotation. Old `Erpinfra@123` (visible in pre-rotation git history) no longer authorizes anything anywhere.
- Production VM access via `infrabeat-erp` CLI is **gated** per Phase 6C.2 (PR #14, `c45fc38`): `--allow-production` global flag required (refusal fires in <20ms, before any network I/O).
- Phase 6C.3 (PR #13, `5184710`) provides JSONL audit log; **Phase 6E.6 (PR #26) migrated to user-home** at `~/.infrabeat-erp/audit/<YYYY-MM-DD>.jsonl` capturing every CLI invocation (9 fields).
- Repo `.gitignore` (PR #15, `fc0e7ce`) excludes operational helper scripts at repo root: `/apply_*.py`, `/fix_*.py`, `/phase*_prompt.md`.
- **Repo flipped public** Phase 6E.2 - eliminates GitHub free-tier private-repo restriction on required status checks. Long-term-optimized choice ($0 recurring cost; ERPNext community norm).
- **Branch ruleset Active** Phase 6E.3 - `dev`/`staging`/`production` enforce 6 required CI checks plus 5 protective rules. PR #21 was the first PR ever subject to real enforcement.
- **Squash-only merge** Phase 6E.0 - repo settings disabled merge commits and rebase merging; squash is the only merge type available in PR UI.
- **Token auto-refresh** Phase 6E.9 (PR #28) - `TokenRefreshAuth(httpx.Auth)` transparently handles 401 - `oauth.refresh` - replay with new bearer.

---

## Authoritative Project State Summary (as of 2026-05-10 - Phase 6E FULLY SEALED, both tracks)

**Phase status:**
- Phase 5 (stdlib script baseline): Sealed (`15_PHASE_5_CLOSURE.md`)
- Phase 6A-6B (typed Python CLI): Sealed (`16_PHASE_6B_CLOSURE.md`)
- Phase 6C (defense-in-depth: audit + guards + keyring): Sealed (`17_PHASE_6C_CLOSURE.md`)
- Phase 6D (CI integration via GitHub Actions for pytest): **SEALED** (`18_PHASE_6D_CLOSURE.md`)
  - PR #19 `98255b0` - `.github/workflows/python-tests.yml` + `[test]` extras + 70-pytest CI on every PR to `dev`/`staging`/`production`
  - Coverage gate at 70%
- Phase 6E (enforcement track + debt retirement track): **FULLY SEALED** (`19_PHASE_6E_CLOSURE.md`, `20_PHASE_6E_DEBT_RETIREMENT_CLOSURE.md`)
  - **Enforcement track (PRs #21, #22):** 6E.0 squash-only; 6E.1 sanitization (7 files); 6E.1.5 VM credential rotation (9 unique 24-char passwords); 6E.1.5b laptop keyring populated; 6E.2 repo flipped public; 6E.3 branch ruleset Active
  - **Debt retirement track (PRs #24-#29 + closure doc #30):** 6E.4 dynamic OIDC (PR #24, L40 closed); 6E.5 PR template (PR #25, L49 closed); 6E.6 audit user-home (PR #26, L50 closed); 6E.7 gh CLI auth; 6E.8 master key dedicated (PR #27); 6E.9 token auto-refresh (PR #28); 6E.10 custom skill (PR #29)
- Phase 7 (InfraBeat Console TUI per `12_INFRABEAT_CONSOLE_SPEC.md` + `12.1_INFRABEAT_CONSOLE_SPEC_REVIEW.md`): **Active scope** - spec review identifies 5 BLOCKERS, 5 HIGH-priority, 4 MEDIUM-priority decisions. Phase 7a MVP = C0-C5 + C7-audit (~25h); Phase 7b follow-on = C6/C8/C9/C10/C11/C12 (~16h).

**Working `infrabeat-erp` CLI subcommands** (8 total - all auto-audited; production-targeted ops gated by `--allow-production`; secrets in OS keyring; token auto-refresh transparent):
`register`, `login`, `smoke`, `query`, `get`, `describe`, `search`, `migrate-secrets`

**Test posture:** **75 passing, 1 skipped**. Phase 6E grew baseline +5 monotonically (70-72-73-75). Zero test regressions across 11 PRs.

**Branch protection (Phase 6E.3 ruleset Active):** **6 required CI checks** on every PR to `dev`/`staging`/`production` plus 5 protective rules. **PR #21 was the first PR ever subject to real enforcement.**

**Custom Claude Code skills:** `infrabeat-smoke-test` + `infrabeat-erp-query` (Phase 6E.10).

**Outstanding debt (deferred to Phase 7+):**
- Lint expansion (ruff or flake8 beyond current Python lint check)
- mypy integration for typed modules
- Legacy Phase 5 script audit (`probe_fac.py`, `register_client.py` - sanitized in 6E.1; deletion-vs-keep decision pending)
- `audit-prune` subcommand
- **Cross-VM smoke validation on staging + production** - Phase 6E architecture validated only on dev so far
- `.git_commit_msg.tmp` `.gitignore` entry (L67 mitigation)
- Token expiry pre-flight check
- Concurrent-call refresh deduplication

---

## Document Change Log

| Date | Change | Source of truth |
|---|---|---|
| 2026-05-09 | Phase 6C close: production VM operational; FAC drift resolved; 3 protections composed. | `17_PHASE_6C_CLOSURE.md` |
| 2026-05-10 | **Phase 6D SEALED (PR #19, `98255b0`).** GitHub Actions pytest CI gate added. | `18_PHASE_6D_CLOSURE.md` |
| 2026-05-10 | **Phase 6E enforcement track SEALED (PRs #21, #22 at `38047c6`).** Squash-only + sanitization + rotation + public flip + ruleset. Lessons L53-L65. | `19_PHASE_6E_CLOSURE.md` |
| 2026-05-10 | **Phase 6E debt retirement SEALED (PRs #24-#29 + closure doc #30 at `cf3a83c`).** L40/L49/L50 closed; master-key dedicated; token auto-refresh; custom skill; gh CLI auth. Pytest 70-75. Lessons L66-L68. | `20_PHASE_6E_DEBT_RETIREMENT_CLOSURE.md` |
| 2026-05-10 | **B5 reconciliation: this document and `04_VM_INVENTORY.md` reconciled through Phase 6E close.** Placeholder `<6E_CLOSURE_MERGE_SHA>` resolved to `cf3a83c`; stale prod FAC claim (`2.4.1`) corrected to `2.0.0` parity; Phase 6E.4+ content added; outstanding debt list refreshed. | This PR; spec review `12.1_INFRABEAT_CONSOLE_SPEC_REVIEW.md` B5 |
| 2026-05-11 | **Phase 7a Sprint 0 SEALED.** All 7 tasks complete in PR #32 squash-merge (dev tip now `cf3a83c`). H3 architectural decision locked: shell-over-SSH via paramiko wins over Ansible (staging VM had ansible-core installed but zero user-created playbooks/inventory/config per 10-section empirical survey). B1 source layout refactored: 6 modules moved into `infrastructure/` package, 4 new layer packages added (`application/`, `domain/`, `presentation/`, `infrastructure/`). New `infrabeat-erp doctor` subcommand with 5 pre-flight checks shipped. New `infrabeat` TUI entry-point stubbed for Sprint 1. F1 resolved: gh CLI auth via browser OAuth works (token in OS keyring). Pytest baseline: 75 -> 86 passed (+11 doctor tests). Lessons L71-L72 captured in `docs/closures/21_PHASE_7A_SPRINT_0_CLOSURE.md`. | PR #32 |

---
