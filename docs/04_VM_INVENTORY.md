# VM_INVENTORY — InfraBeat Three-Environment Setup

> **CRITICAL:** Each VM has different paths, users, sites, and branches. Claude MUST reference this file before any deployment or remote operation. Cross-VM mistakes are the #1 cause of failed deploys.

> **Last reconciled 2026-05-10 (Phase 6E FULLY SEALED — both enforcement and debt-retirement tracks).** Phase 6E delivered: squash-only merging (6E.0), plaintext credential sanitization across 7 files (PR #21), 3-VM × 3-credential-type rotation to 24-char keyring-backed values (Phase 6E.1.5), repo flipped public (6E.2), branch ruleset Active with 6 required CI checks (6E.3), dynamic OIDC endpoint discovery (PR #24), audit log to user-home (PR #26), master key dedicated keyring service (PR #27), OAuth token auto-refresh (PR #28), and the `infrabeat-erp-query` custom Claude Code skill (PR #29). **Plaintext credentials usable against any VM: ZERO.** Phase 6E architecture empirically validated on dev VM (Phase 6E.4 close smoke); cross-VM smoke on staging + production deferred to Phase 7+. Current `dev` tip: **`982c0ba`** (PR #30 — Phase 6E.4+ debt-retirement closure docs merge). See Document Change Log at end.

---

## 🟢 Development VM (ERP0)

| Item | Value |
|---|---|
| **IP** | `10.1.0.184` |
| **Role** | Daily development, hot-reload coding |
| **Status** | ✅ FULLY OPERATIONAL |
| **OS** | Ubuntu 22.04.5 LTS |
| **SSH user** | `erpadmin` |
| **SSH password** | **Rotated Phase 6E.1.5** — 24-char value in OS keyring service `infrabeat-vm-creds` under username `dev-ssh`. Retrieve via `python -c "import keyring; print(keyring.get_password('infrabeat-vm-creds', 'dev-ssh'))"`. Old `Erpinfra@123` no longer valid. |
| **Bench path** | `/home/frappe/frappe-bench/` |
| **Bench user** | `frappe` |
| **Site name** | `erp.local` |
| **Web URL** | `http://10.1.0.184` |
| **Admin login** | `Administrator / <rotated>` — password rotated Phase 6E.1.5; 24-char value in keyring `infrabeat-vm-creds/dev-admin` |
| **MariaDB root** | **Rotated Phase 6E.1.5** — 24-char value in keyring `infrabeat-vm-creds/dev-mariadb-root` |
| **Git branch** | `dev` (auto-deploys on push) |
| **Mode** | bench dev (`bench start`) |

### Apps Installed
- ✅ frappe v15
- ✅ erpnext v15
- ✅ frappe-assistant-core v2.0.0 (verified live 2026-05-09 in Phase 6C.4; re-verified 2026-05-10 in Phase 6E.4 close smoke)
- ✅ custom_erp (active branch: `dev`)

### FAC State (re-verified 2026-05-10 via `infrabeat-erp smoke dev` post Phase 6E.4 close)

| Field | Value |
|---|---|
| FAC version | `2.0.0` |
| MCP protocol | `2025-06-18` |
| Tool count | **17** |
| OAuth registration | RFC 7591 dynamic registration accepted |
| OAuth flow | RFC 7636 PKCE S256 + browser-based authcode flow working |
| MCP endpoint | `/api/method/frappe_assistant_core.api.fac_endpoint.handle_mcp` (post-PR #11 hotfix); **read dynamically from OIDC `mcp_endpoint` per Phase 6E.4 (PR #24)** |
| OIDC discovery | `/.well-known/openid-configuration` returns `mcp_endpoint` correctly; **consumed at runtime per Phase 6E.4** |
| Token TTL | 3600s — **auto-refresh via `TokenRefreshAuth(httpx.Auth)` per Phase 6E.9 (PR #28)**; re-`login` only required when refresh-token also expired |
| Audit log capture | ✅ Active per Phase 6C.3 (PR #13); **migrated to `~/.infrabeat-erp/audit/<YYYY-MM-DD>.jsonl` per Phase 6E.6 (PR #26)** |
| Production guard | N/A — dev VM is freely accessible (guards apply only to `production` alias) |
| Keyring storage | ✅ Active per Phase 6C.1 (PR #16); **master key promoted to dedicated `infrabeat-erp-master/master` service per Phase 6E.8 (PR #27)** with 5-step backward-compatible resolution |

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
| **Status** | ✅ FULLY OPERATIONAL (Stage 1A closed; Phase 6C.4 verified 2026-05-09) |
| **OS** | Ubuntu 22.04 LTS |
| **SSH user** | `erpadmin` |
| **SSH password** | **Rotated Phase 6E.1.5** — 24-char value in keyring `infrabeat-vm-creds/staging-ssh`. Old `Erpinfra@123` no longer valid. |
| **Bench path** | `/home/erpadmin/frappe-bench/` ⚠ DIFFERENT FROM DEV |
| **Bench user** | `erpadmin` ⚠ DIFFERENT FROM DEV |
| **Site name** | `erp.staging` ⚠ DIFFERENT FROM DEV |
| **Web URL** | `http://10.1.0.185` |
| **Admin login** | `Administrator / <rotated>` — password rotated Phase 6E.1.5; 24-char value in keyring `infrabeat-vm-creds/staging-admin` |
| **MariaDB root** | **Rotated Phase 6E.1.5** — 24-char value in keyring `infrabeat-vm-creds/staging-mariadb-root` |
| **Git branch** | `staging` (manual promote from dev) |
| **Mode** | Production (nginx + supervisor) |

### Apps Installed
- ✅ frappe v15
- ✅ erpnext v15
- ✅ frappe-assistant-core v2.0.0 (verified live 2026-05-09 in Phase 6C.4 — parity with dev + production)
- ✅ custom_erp (active branch: `staging`)

### FAC State (verified 2026-05-09 via `infrabeat-erp smoke staging`; **cross-VM Phase 6E re-validation deferred to Phase 7+**)

| Field | Value |
|---|---|
| FAC version | `2.0.0` (parity with dev + production) |
| MCP protocol | `2025-06-18` (parity) |
| Tool count | **17** (byte-equivalent catalog with dev + production) |
| OAuth registration | RFC 7591 dynamic registration accepted (`client_id=v6cfdr10i3` issued) |
| OAuth flow | RFC 7636 PKCE S256 + browser-based authcode flow working |
| Token TTL | 3600s — auto-refresh expected to work per Phase 6E.9 (cross-VM re-validation pending) |
| Audit log capture | ✅ Active per Phase 6C.3 + Phase 6E.6 user-home migration |
| Production guard | N/A — staging is the UAT proving ground; freely accessible by design |
| Keyring storage | ✅ Active per Phase 6C.1 + Phase 6E.8 master-key separation |

### Verified Working (Stage 1A Closure + Phase 6C.4)
- Customer Visit DocType end-to-end
- All supervisor services RUNNING
- Redis on Frappe ports (11000, 13000), system redis disabled (per Stage 1A Gotcha #3)
- API returns 200 for Customer Visit endpoints
- Browser CRUD verified
- Phase 6C.4 closure smoke: composed audit + keyring storage validated end-to-end

---

## 🔴 Production VM (ERP1)

| Item | Value |
|---|---|
| **IP** | `10.1.0.186` |
| **Role** | Live production, business-critical |
| **Status** | ✅ FULLY OPERATIONAL (Phase 5 verified, Phase 6C.4 re-verified 2026-05-09) |
| **OS** | Ubuntu 22.04 LTS |
| **SSH user** | `erpadmin` |
| **SSH password** | **Rotated Phase 6E.1.5** — 24-char value in keyring `infrabeat-vm-creds/production-ssh`. Note: production MariaDB root password rotation triggered the password-recovery incident (L55 — safe-mode systemd override runbook in `19_PHASE_6E_CLOSURE.md` §7.A); rotation completed successfully after recovery. |
| **Bench path** | `/home/erpadmin/frappe-bench/` (mirrors staging) |
| **Bench user** | `erpadmin` |
| **Site name** | `erp.production` |
| **Web URL** | `http://10.1.0.186` |
| **Admin login** | `Administrator / <rotated>` — password rotated Phase 6E.1.5; 24-char value in keyring `infrabeat-vm-creds/production-admin` |
| **MariaDB root** | **Rotated Phase 6E.1.5 (after recovery)** — 24-char value in keyring `infrabeat-vm-creds/production-mariadb-root` |
| **Git branch** | `production` (manual promote from staging + backup gate) |
| **Mode** | Production (nginx + supervisor) |

### Apps Installed
- ✅ frappe v15
- ✅ erpnext v15
- ✅ frappe-assistant-core **v2.0.0** (empirically verified 2026-05-09 in Phase 6C.4 — Phase 5 §10's claim of `2.4.1` was a stale doc artifact)
- ⚠ custom_erp — **first promotion not yet performed** (production branch awaits first staging-to-prod promotion)

### FAC State (verified 2026-05-09 via `infrabeat-erp --allow-production smoke production`; **cross-VM Phase 6E re-validation deferred to Phase 7+**)

| Field | Value |
|---|---|
| FAC version | **`2.0.0`** (empirically verified — perfect parity with dev + staging) |
| MCP protocol | **`2025-06-18`** (parity) |
| Tool count | **17** (byte-equivalent catalog with dev + staging) |
| OAuth registration | RFC 7591 dynamic registration accepted (`client_id=cvngll9k67` issued 2026-05-09 in Phase 6C.4) |
| OAuth flow | RFC 7636 PKCE S256 + browser-based authcode flow working — first machine-trust handshake from `infrabeat-erp` to production VM successful |
| Audit log capture | ✅ Active per Phase 6C.3 + Phase 6E.6 user-home migration — Phase 6C.4 captured `register`, `login`, `smoke`, `migrate-secrets` invocations all with `args` containing `--allow-production` |
| Production guard | ✅ Active per Phase 6C.2 — empirically validated: `smoke production` WITHOUT `--allow-production` exits 1 in 16ms (fires before any network I/O) |
| Keyring storage | ✅ Active per Phase 6C.1 + Phase 6E.8 master-key separation — production secrets registered direct-to-keyring, never touched plaintext |

> **6C COMPOSITION FULLY VALIDATED ON PRODUCTION (2026-05-09).** All three protections compose additively without interference. `register --allow-production production` issued client_id and saved to keyring. `smoke production` (with flag) returned 17-tool catalog. `migrate-secrets --vm production` returned `no-source` in 14ms (idempotent path validated). `smoke production` (without flag) refused with exit 1. All four invocations captured in audit log.

> **🎉 FAC VERSION DRIFT QUESTION RESOLVED.** Carried since Phase 5 §10 (which claimed prod at `2.4.1` while dev was empirically at `2.0.0`), the question is empirically settled: **all 3 VMs run `2.0.0`/`2025-06-18`/17 tools at perfect parity**. The `2.4.1` claim was a stale doc artifact, NOT actual environmental drift.

### Production Safety Rules
1. **NEVER deploy to prod without backup first** — Phase 7+ delivers `infrabeat-erp backup <vm>` subcommand per spec review 12.1 H2; manual `bench backup --with-files` for now
2. **NEVER push directly to `production` branch** — must come via PR from `staging`; branch ruleset (Phase 6E.3) now blocks this at platform level
3. **Smoke tests MUST pass** post-deploy or auto-rollback fires (Phase 7+)
4. **Audit log entry required** for every prod change — ✅ Phase 6C.3 + Phase 6E.6 user-home migration provide JSONL audit log infrastructure
5. **Confirmation gate**: User must type `DEPLOY` to confirm prod actions — ✅ Phase 6C.2 introduces `_confirm_deploy_or_env` helper (interactive `click.prompt` requiring literal `DEPLOY` OR `INFRABEAT_CONFIRM=DEPLOY` env var). Wired into future mutating subcommands (Phase 7); current 8 read-only/migration subcommands don't need it.
6. **Production guard flag**: User must pass `--allow-production` to any command targeting prod — ✅ Phase 6C.2 introduces the global flag enforced via `_ensure_production_allowed` in `register`, `login`, `smoke`, `migrate-secrets`, and via `_build_authed_client` for `query`, `get`, `describe`, `search`. All 8 subcommands gated.

---

## 🚨 Cross-VM Differences (DON'T MIX UP)

| Aspect | Dev | Staging | Production |
|---|---|---|---|
| Bench path | `/home/frappe/frappe-bench/` | `/home/erpadmin/frappe-bench/` | `/home/erpadmin/frappe-bench/` |
| Bench user | `frappe` | `erpadmin` | `erpadmin` |
| Site name | `erp.local` | `erp.staging` | `erp.production` |
| Branch | `dev` | `staging` | `production` |
| Mode | bench dev | production | production |
| FAC version | `2.0.0` (verified) | `2.0.0` (verified) | **`2.0.0`** (verified Phase 6C.4) |
| Tool count | 17 | 17 | 17 (byte-equivalent) |
| MCP protocol | `2025-06-18` | `2025-06-18` | `2025-06-18` |
| Audit log capture | ✅ Active (user-home per 6E.6) | ✅ Active (user-home per 6E.6) | ✅ Active (user-home per 6E.6) + gated by `--allow-production` |
| Keyring storage | ✅ Active (3 services per 6E.8) | ✅ Active | ✅ Active |
| SSH/MariaDB/Admin passwords | Rotated 6E.1.5 (24-char keyring) | Rotated 6E.1.5 (24-char keyring) | Rotated 6E.1.5 (24-char keyring; post-recovery per L55) |
| `infrabeat-erp` access | Free | Free (UAT proving ground) | Gated by `--allow-production` flag |
| Phase 6E smoke re-verified | ✅ 2026-05-10 (Phase 6E.4 close) | ⏳ Pending Phase 7+ | ⏳ Pending Phase 7+ |
| Risk tolerance | High (break freely) | Low (careful) | Zero (mandatory `--allow-production` + future `--confirm DEPLOY` for mutations) |

---

## 🌐 Network Topology

- All 3 VMs on subnet `10.1.0.0/24`
- Laptop on `10.1.1.0/24` reaching VMs via inter-subnet routing (verified 2026-05-09; the inter-subnet router is a third-party reliability factor independent of VM health — transient ConnectTimeouts can originate at the router; documented as Phase 6C lesson L48)
- Internal network (VPN required for external access)
- Inter-VM SSH: must be configured with key trust (currently password-based; Phase 6E.1.5 rotated passwords but did NOT migrate to key trust — Phase 7 pre-flight `infrabeat doctor` will validate keys are present)
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
- **Password auth only** (must migrate to keys) — Phase 6E.1.5 rotated to strong 24-char passwords but did NOT migrate to key trust
- ✅ Three OS keyring services on laptop populated per Phase 6E.1.5b: `infrabeat-erp` (OAuth tokens), `infrabeat-erp-master` (Fernet master key), `infrabeat-vm-creds` (9 VM passwords)
- ✅ `gh` CLI device-flow auth completed per Phase 6E.7 — `gh pr create` and `gh api repos/.../rulesets` both work without browser fallback
- **Phase 7 prerequisite (per spec review 12.1 H5):** `infrabeat doctor` subcommand will validate SSH key trust + sudoers fragments + audit dir writable + FAC reachable + GitHub PAT scope correct as part of Sprint 0 (C0)

---

## 📍 Quick Reference for Claude Code

When Claude sees:
- "deploy to dev" → SSH to `erpadmin@10.1.0.184` (key auth target; password in keyring `infrabeat-vm-creds/dev-ssh`), work in `/home/frappe/frappe-bench/`, site `erp.local`, branch `dev`
- "deploy to staging" → SSH to `erpadmin@10.1.0.185` (key auth target; password in keyring `infrabeat-vm-creds/staging-ssh`), work in `/home/erpadmin/frappe-bench/`, site `erp.staging`, branch `staging`
- "deploy to production" → SSH to `erpadmin@10.1.0.186` (key auth target; password in keyring `infrabeat-vm-creds/production-ssh`), work in `/home/erpadmin/frappe-bench/`, site `erp.production`, branch `production`, BACKUP FIRST, **and pass `--allow-production` (and `--confirm DEPLOY` for mutating ops) per Phase 6C.2 guards**

When Claude is using `infrabeat-erp` CLI:
- All commands look up secrets in OS keyring per Phase 6C.1 + 6E.8 separation — no need to stay in any specific directory for credential resolution. The `~/.infrabeat-erp/audit/` directory is user-home per Phase 6E.6 (legacy `<cwd>/.audit/` paths still readable via fallback chain); `<cwd>/.secrets/` only matters for legacy migration sources (`.json.migrated` rename trail)
- Token TTL is 3600s — **auto-refresh transparent on 401 per Phase 6E.9**; re-run `infrabeat-erp login <vm>` only if refresh-token itself expired (rare, surfaces `TokenRefreshFailed` with explicit guidance)
- Every invocation is captured in `~/.infrabeat-erp/audit/<YYYY-MM-DD>.jsonl` per Phase 6C.3 + 6E.6 — review with `Get-Content (Get-ChildItem "$HOME\.infrabeat-erp\audit\*.jsonl" | Sort-Object LastWriteTime -Descending | Select-Object -First 1) -Tail 12` for forensic analysis
- Production-targeted commands require `--allow-production` global flag per Phase 6C.2 — refused with exit code 1 otherwise (refusal fires in <20ms, before any network I/O)
- Custom Claude Code skill `infrabeat-erp-query` (Phase 6E.10) routes ERPNext data questions through CLI subcommands when invoked in Claude Code

---

## 📜 Document Change Log

| Date | Change | Source of truth |
|---|---|---|
| 2026-05-09 | Reconciled during Phase 6C kickoff Step 4. Production VM status flipped from "NOT YET PROVISIONED" to "FULLY OPERATIONAL". | `15_PHASE_5_CLOSURE.md` §10 |
| 2026-05-09 | Added FAC State subsection to Dev VM with empirical values: FAC `2.0.0`, MCP `2025-06-18`, 17 tools, OAuth verified. | `infrabeat-erp smoke dev` live output |
| 2026-05-09 | Added FAC State subsection to Production VM marked for re-verification in Phase 6C.4. | `15_PHASE_5_CLOSURE.md` §10 |
| 2026-05-09 | Phase 6C kickoff Step 5: empirically verified Staging FAC at `2.0.0`/`2025-06-18`/17 tools — byte-equivalent catalog with dev. | `infrabeat-erp smoke staging` live output |
| 2026-05-09 | **Phase 6C.3 merged on `dev` at `5184710` (PR #13).** Audit log infrastructure active for every CLI invocation. | PR #13 squash merge |
| 2026-05-09 | **Phase 6C.2 merged on `dev` at `c45fc38` (PR #14).** `--allow-production` global flag + `_confirm_deploy_or_env` helper. | PR #14 squash merge |
| 2026-05-09 | **Cleanup hotfix at `fc0e7ce` (PR #15).** Removed inadvertently-committed helper scripts. Added `.gitignore` patterns. | PR #15 squash merge |
| 2026-05-09 | **Phase 6C.1 merged on `dev` at `42b1d07` (PR #16).** Keyring promotion + `migrate-secrets` subcommand + Fernet fallback. Test count 60→70. | PR #16 squash merge |
| 2026-05-09 | **🎉 Phase 6C.4 closure smoke completed; FAC drift question RESOLVED.** All 3 VMs at `2.0.0`/`2025-06-18`/17 tools parity. | `infrabeat-erp --allow-production smoke production` empirical capture |
| 2026-05-09 | Added laptop subnet (`10.1.1.0/24`) note in Network Topology with router-flap caveat (Phase 6C lesson L48). | Network probe 2026-05-09 |
| 2026-05-09 | Flagged `~/.ssh/github_pat` does-not-exist drift; Phase 6C.1 keyring is the new right home. Noted `gh` CLI installed but device-flow auth incomplete. | Filesystem check 2026-05-09 |
| 2026-05-10 | **Phase 6D SEALED (PR #19, `98255b0`).** GitHub Actions pytest CI gate on PRs to dev/staging/production. Coverage gate 70%. | `18_PHASE_6D_CLOSURE.md` |
| 2026-05-10 | **Phase 6E enforcement track SEALED (PRs #21, #22 at `38047c6`).** Squash-only + 7-file sanitization + 3-VM × 3-credential rotation + laptop keyring populated + repo flipped public + branch ruleset Active. PR #21 first ever real-enforced PR. Lessons L53-L65 captured (incl. L55 MariaDB safe-mode recovery runbook). | `19_PHASE_6E_CLOSURE.md` |
| 2026-05-10 | **Phase 6E debt retirement SEALED (PRs #24-#29 + closure doc PR #30 at `982c0ba`).** L40/L49/L50 closed; master-key dedicated service; token auto-refresh; custom skill `infrabeat-erp-query`; gh CLI auth completed. Pytest 70→75 monotonically. Lessons L66-L68 captured. | `20_PHASE_6E_DEBT_RETIREMENT_CLOSURE.md` |
| 2026-05-10 | **B5 reconciliation: this document and `00_1_PROJECT_FACTS.md` reconciled through Phase 6E close.** All three VMs annotated with rotated-credential keyring locations, Phase 6E primitives in FAC State sections, cross-VM smoke re-validation flagged as Phase 7+ debt. | This PR; spec review `12.1_INFRABEAT_CONSOLE_SPEC_REVIEW.md` §B5 |
| 2026-05-11 | **Phase 7a Sprint 0 verification.** `infrabeat-erp doctor` confirms all 9 VM credentials present in `infrabeat-vm-creds` keyring service. Naming convention canonical: `<vm>-ssh-password`, `<vm>-admin-password`, `<vm>-mariadb-root` (where `<vm>` is `dev`/`staging`/`production`). Earlier F3 finding (claimed missing entries) RETRACTED post-doctor verification. Doctor live: `4 PASS, 0 FAIL, 0 WARN, 1 INFO`. | `21_PHASE_7A_SPRINT_0_CLOSURE.md` |
| 2026-05-11 | **Phase 7a Sprint 1 VM-state corrections (L76 + bootstrap).** Production VM (10.1.0.186) IS provisioned: hostname `erp1-virtual-machine`. Earlier `not yet provisioned` claim retracted as 3rd L71 instance this phase. Naming convention noted (counterintuitive): production=erp1, staging=erp2. All 3 VMs verified reachable via passwordless ed25519 SSH (`~/.ssh/infrabeat_ed25519`) per `scripts/bootstrap_ssh_keys.py`. Canonical hostnames: dev=`erp-vm` (10.1.0.184), staging=`erp2-virtual-machine` (10.1.0.185), production=`erp1-virtual-machine` (10.1.0.186). | `22_PHASE_7A_SPRINT_1_CLOSURE.md` |

---
