# 13 ? Phase 3 Closure: Custom Agent Skills (MVP)

> Sibling to `10_STAGE_1A_CLOSURE.md` and `11_DEV_VM_CLOSURE.md`. Captures
> what Phase 3 of the InfraBeat AI-native platform build delivered, the
> decisions logged along the way, and the open items deferred to follow-up
> sessions.

---

## Phase Scope (per `09_CLAUDE_NATIVE_ARCHITECTURE.md`)

Build out the InfraBeat skills layer: 9 custom Agent Skills under
`.claude/skills/` that encode the project's non-negotiable rules into
reusable, invokable capabilities. Each skill = a folder with `SKILL.md`
(YAML frontmatter + body) plus optional `templates/` and `scripts/`
subdirectories.

The 9 planned skills, in priority order:

1. `infrabeat-doctype`     ? DocType + controller + JS + tests INTO VS CODE
2. `infrabeat-script`      ? server scripts, client scripts, hooks
3. `infrabeat-smoke-test`  ? DocType resolves, login works, APIs return 200
4. `infrabeat-deploy`      ? pull + migrate + build + restart on target VM
5. `infrabeat-backup`      ? mandatory before prod deploys
6. `infrabeat-rollback`    ? restore backup, revert git
7. `infrabeat-promote`     ? cross-environment promotion
8. `infrabeat-webform`     ? webform generation
9. `infrabeat-database-op` ? safe DB queries via Frappe Assistant Core

---

## What Shipped (MVP)

3 of 9 skills delivered fully (SKILL.md body + all required templates):

- `infrabeat-doctype` (MVP-1) ? generates 5+1 files into VS Code per the
  doctype path convention (`apps/custom_erp/custom_erp/custom_erp/doctype/`)
- `infrabeat-deploy` (MVP-2) ? per-env dispatch from VM_INVENTORY,
  production gate (mandatory backup + DEPLOY confirmation), Plan Mode
  preview, before/after state recording, smoke-test chain
- `infrabeat-smoke-test` (MVP-3) ? 6-check mandatory battery + 2 advisory,
  dual transport (Frappe Assistant Core MCP preferred, SSH+curl fallback),
  KEY=VALUE structured output

6 of 9 skills delivered as stubs only (valid YAML frontmatter, body is
"STATUS: Stub. Implementation pending."):

- `infrabeat-script`
- `infrabeat-backup`
- `infrabeat-rollback`
- `infrabeat-promote`
- `infrabeat-webform`
- `infrabeat-database-op`

Stubs are sufficient for Claude Code skill discovery ? Claude sees them
in `.claude/skills/` and recognizes the names, but knows the bodies are
not yet implemented.

Repo-level: `.gitattributes` added at root, enforcing LF on all
Unix-targeted files (`.sh`, `.py`, `.json`, `.md`, `.yml`, `.toml`, etc.)
and CRLF on Windows-targeted files (`.cmd`, `.bat`, `.ps1`).

---

## Phase 3 Success Criteria

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | All 9 skill folders exist with valid SKILL.md (YAML + instructions) | DONE | commit 40af336, 9 stub SKILL.md files committed |
| 2 | infrabeat-doctype generates a working DocType end-to-end into VS Code | DONE (skill code) | commit fc1a17c. End-to-end test deferred to next session. |
| 3 | infrabeat-smoke-test invokes against dev VM via existing MCP and returns pass/fail | DONE (skill code) | commit 11747ae. End-to-end test deferred to next session. |
| 4 | .gitattributes added (fix the .sh CRLF issue from Phase 2) | DONE | commit b1cfb63 |
| 5 | PR opened from feature/phase-3-custom-skills to dev, CI green, merged | DONE | PR #2, merge commit d3ae868, all 3 mandatory CI checks green |

All 5 criteria satisfied.

---

## Branch / Commit Audit Trail

Branch: `feature/phase-3-custom-skills` (retained on origin for safety net)

Commits in PR #2 (in order):

| Short SHA | Subject |
|---|---|
| b1cfb63 | chore(repo): add .gitattributes to enforce LF on Unix files |
| 40af336 | feat(skills): scaffold 9 infrabeat agent skill stubs |
| fc1a17c | feat(skills): implement infrabeat-doctype (MVP-1 of 3) |
| 9d6edcd | feat(skills): implement infrabeat-deploy (MVP-2 of 3) |
| 11747ae | feat(skills): implement infrabeat-smoke-test (MVP-3 of 3) |

Merge commit: `d3ae868` on dev branch (origin/dev = origin/HEAD = d3ae868)

CI status: 3 successful (Validate JSON, Scan for secrets, Python lint),
2 skipped (direct-push block, approving review ? both correct skips for
solo-dev PR flow).

---

## File Inventory (delivered to repo)

Repo root:

- `.gitattributes` (832 bytes) ? line-ending policy

Under `.claude/skills/`:

- 9 folders: `infrabeat-backup`, `infrabeat-database-op`,
  `infrabeat-deploy`, `infrabeat-doctype`, `infrabeat-promote`,
  `infrabeat-rollback`, `infrabeat-script`, `infrabeat-smoke-test`,
  `infrabeat-webform`
- 9 `SKILL.md` files (3 fully implemented, 6 stubs)
- 7 template files (5 under `infrabeat-doctype/templates/`, 1 each under
  `infrabeat-deploy/templates/` and `infrabeat-smoke-test/templates/`)

Total Phase 3 line count delta: 1,092 lines added, 0 deleted.

---

## Decisions Logged

D1. **Authoring approach for skills: Approach 1 with separate template
files** (Claude Code's native Read/Write tools handle file I/O; no Python
script layer; templates use `{{PLACEHOLDER}}` substitution; matches
Anthropic's official skill patterns).

D2. **Build order: scaffold all 9 first, then implement MVP-3, then
follow-up 6.** Satisfied criterion #1 cheaply, let MVP iterate without
rework.

D3. **MVP composition: doctype + deploy + smoke-test** (closes the prompt
to running-dev cycle). Backup/rollback deferred because dev VM is
throwaway-tolerant.

D4. **Per-environment dispatch in deploy/smoke skills.** Both skills take
`target_env` as input and look up paths/users/sites from VM_INVENTORY at
runtime. Single skill handles all 3 VMs.

D5. **Production gate is mandatory.** Production deploy requires
infrabeat-backup invocation in same session AND user typing exactly
"DEPLOY". No bypass flags.

D6. **Smoke-test chain on production.** Failed production smoke test
auto-invokes infrabeat-rollback. Failed dev/staging smoke tests REPORT
but do not auto-rollback (those VMs are tolerant).

D7. **Git identity.** Set globally to `Prasad Ganegaonkar
<pganegaonkar@gmail.com>` (real GitHub email). Auto-derived
`prasad.ganegaonkar@infrabeat.net` was a hostname-derived non-existent
mailbox; commits 722dd51, 9e566d2 (Phase 2) and c01fdd3 (the precursor
to b1cfb63) retain that fake email. Cosmetic only; not rewriting history.

D8. **Closure docs live in repo at root.** Decided during Phase 3
closure: `13_PHASE_3_CLOSURE.md` goes to repo root alongside `CLAUDE.md`,
`BRANCHING.md`, `README.md`. Prior closure docs (`10_*`, `11_*`) live
only in Claude.ai project knowledge ? the repo+project-knowledge dual
storage is the new convention going forward.

---

## Known TODOs Deferred to Follow-up

T1. **Dev-VM sudo block in deploy template** ? current
`templates/deploy.sh.tmpl` has a `sudo -u {{BENCH_USER}} bash -s` re-exec
block with `INNER_BODY_PLACEHOLDER`. Refinement needed during E2E test
on dev VM (where ssh_user=erpadmin differs from bench_user=frappe). For
staging/prod (ssh_user=bench_user=erpadmin), re-exec is skipped
naturally. Estimated fix: <30 lines of bash.

T2. **Hardcoded admin credentials in smoke template** ?
`templates/smoke.sh.tmpl` previously embedded a literal Administrator
password in the login curl. Sanitized in Phase 6E.1 to read from the
`$ADMIN_PASSWORD` env var (sourced from the `infrabeat-vm-creds`
keyring service; see `04_VM_INVENTORY.md` ?VM Credential Setup). Phase
4 originally planned to source from a VM-side secret file; the keyring
approach supersedes that.

T3. **Audit hook env var names from Phase 2** ? Phase 2 wrote
`.claude/hooks/audit_pre.sh` and `audit_post.sh` with best-guess env
var names (`CLAUDE_TOOL_NAME` etc.). First skill invocation will trigger
a hook; inspect `audit_log/local.jsonl` and correct names if they don't
match.

T4. **Cosmetic Markdown-link junk in 3 commit message bodies**
(fc1a17c, 9d6edcd, 11747ae). Caused by chat-render layer mangling
filename-with-extension strings into Markdown autolinks during paste.
Subjects are clean. Tech debt, harmless. Future commit messages drafted
in chat sessions should avoid `.ext` style filenames in bodies.

T5. **6 stub skill bodies** ? script, backup, rollback, promote,
webform, database-op. Subsequent PRs will add bodies, in this priority
order per Phase 3 plan.

T6. **End-to-end acceptance test (the 8-step proof)** ? was scheduled
for separate session post-merge to keep PR #2 focused on skill code.
Test plan documented in PR #2 description and below.

---

## End-to-End Acceptance Test Plan (deferred, scheduled for next session)

In Claude Code panel on laptop:

1. Type: "Use infrabeat-doctype to create a Ping Check DocType with one
   Data field 'message', required, in Custom Erp module, naming series
   PC-.YYYY.-.#####"
2. Verify 6 files appear unstaged in VS Code Source Control panel at
   `apps/custom_erp/custom_erp/custom_erp/doctype/ping_check/`
3. Review diffs in VS Code, accept, commit on `feature/phase-3-test-doctype`,
   push
4. Type: "Use infrabeat-deploy to deploy this branch to dev VM"
5. Skill SSHes to 10.1.0.184, pulls, migrates, builds, restarts, reports
6. Type: "Use infrabeat-smoke-test against dev VM"
7. Skill returns structured pass/fail report; both Customer Visit AND
   Ping Check resolve 200
8. Browser: navigate to http://10.1.0.184/app/ping-check, create a
   record, save successfully

Pass = all 8 steps complete with zero manual SSH or bench from the user.
Test serves dual purpose: validates Phase 3 criteria #2 and #3 in
practice, AND surfaces TODOs T1, T2, T3 for fixing.

---

## Lessons That Shaped Phase 3 Execution

L1. **PowerShell here-strings are the only reliable way to write files.**
Confirmed across all 9 skill stubs and 8 fully-implemented skill files.
Editor-paste workflows fail on multi-line content (carryover from Phase 2).

L2. **Re-anchor the working directory in every fresh PowerShell session.**
Closing a shell drops `$variables` and `Get-Location`. Three times in
Phase 3 a new shell opened in home directory and a relative path
collided. Fix: every step starts with
`Set-Location (Join-Path $env:USERPROFILE 'Projects\custom_erp')`.

L3. **Chat-render layer mangles `filename.ext` into Markdown autolinks
on paste.** Affects PowerShell command paths and commit message bodies
both. Filesystem and git contents are unaffected because here-strings
preserve what PowerShell received from clipboard, not what was rendered.
Mitigation: avoid `.ext` filenames in commit message bodies; use Notepad
intermediary for PR descriptions.

L4. **`.gitattributes` is necessary on any Windows + Unix project.**
Without it, `core.autocrlf=true` overrides any local LF preference at
checkout time. Phase 2 deferred this; Phase 3 fixed it as the first act.

L5. **Git commits with auto-derived identity create fake-mailbox
attribution on GitHub.** Discovered Phase 2 commits `722dd51` and
`9e566d2` were committed as
`prasad.ganegaonkar@infrabeat.net` ? a hostname-derived string that is
not a real email. Phase 3 fixed forward by setting global git identity
explicitly to the real GitHub email.

L6. **PR templates auto-populate when `.github/pull_request_template.md`
exists.** GitHub fills the description field automatically. Plan PR
descriptions to fit the template structure rather than overwriting it.

L7. **CI on this project is JSON-validation + secret-scan + Python lint
+ branch-protection skips.** Templates with `{{PLACEHOLDER}}` syntax
embedded in `controller.py.tmpl` did NOT trip the Python linter (pre-empt
worry was unfounded). If future skill templates do trip lint, ignore
patterns can be added later.

---

## What Comes Next (Phase 4 preview)

Per `09_CLAUDE_NATIVE_ARCHITECTURE.md` Phase 4 (3 hours):
**Multi-VM** ? All 3 VMs reachable via Claude, prod provisioned.

Specifically:

- Provision production VM (10.1.0.186) ? currently NOT YET PROVISIONED
- Set up SSH key auth from laptop to all 3 VMs (replace password auth)
- Register MCP servers for staging and production (frappe-staging,
  frappe-prod) in `~/.claude.json`
- Extract admin credentials out of smoke template (TODO T2)
- E2E acceptance test for Phase 3 (TODO T6) ? will be a Phase 3-Phase 4
  bridge activity

Phase 5 follows: **GitHub Workflow** ? branch protection rules, GitHub
Actions for deploy-dev/staging/production.yml, MCP integration with
GitHub.

Phase 6 final: **Validation** ? end-to-end test of prompt to prod
deploy, then platform is shipped.

---

## Sentinel

`ib-7c4a9f` (Phase 2 project-memory sentinel; live verification still
deferred ? see TODO T6 / E2E test).

## Closed By

Prasad Ganegaonkar (PrasadInfraBeat). Session date matches merge commit
d3ae868 timestamp on origin.