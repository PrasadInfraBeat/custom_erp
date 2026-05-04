---
name: infrabeat-deploy
description: "Use this skill when the user asks to deploy a branch to a target VM. Triggers include 'deploy to dev', 'deploy to staging', 'deploy to production', 'push feature/X to dev VM', 'roll out to staging'. SSHes to the target VM as the right user per VM_INVENTORY.md, runs git pull + ensures __init__.py at every level + bench migrate + bench clear-cache + bench clear-website-cache + bench build + worker restart, then chains infrabeat-smoke-test. Production deploys MUST be preceded by infrabeat-backup AND require explicit DEPLOY confirmation. Do NOT use for cross-environment promotion (use infrabeat-promote, which chains this skill internally) or for first-time VM provisioning (out of scope, use Ansible)."
---

# infrabeat-deploy

Deploy a custom_erp branch to dev, staging, or production VM. Idempotent,
audited, gated for production.

## When invoked

User asks to deploy code to a specific VM. Examples:
- "Deploy to dev"
- "Deploy feature/sales-inquiry to dev VM"
- "Deploy staging branch to staging VM"
- "Deploy to production" (triggers safety pipeline)

## Inputs to gather from user prompt

REQUIRED:
1. **target_env** - one of: `dev`, `staging`, `production`. Inferred from
   user's wording if obvious ("deploy to staging" -> `staging`).

OPTIONAL (sensible defaults if absent):
2. **branch** - which branch to pull on the VM.
   Default: matches target_env (`dev` -> `dev` branch, etc.)
3. **skip_smoke** - boolean. If true, skip the post-deploy smoke test.
   Default: false. NEVER honor on production.

If target_env is ambiguous, ASK the user. Never guess.

## Per-environment dispatch (VM_INVENTORY.md)

| target_env  | VM IP        | SSH user  | Bench user | Bench path                     | Site            | Branch       |
|-------------|--------------|-----------|------------|--------------------------------|-----------------|--------------|
| dev         | 10.1.0.184   | erpadmin  | frappe     | /home/frappe/frappe-bench      | erp.local       | dev          |
| staging     | 10.1.0.185   | erpadmin  | erpadmin   | /home/erpadmin/frappe-bench    | erp.staging     | staging      |
| production  | 10.1.0.186   | erpadmin  | erpadmin   | /home/erpadmin/frappe-bench    | erp.production  | production   |

**Production VM is NOT YET PROVISIONED** as of Phase 3. Skill must check
SSH reachability and report clearly if production target is unreachable.
Skill MUST NOT silently fall back to a different env.

## Hard rules (NON-NEGOTIABLE)

1. NEVER deploy to production without:
   a) A successful `infrabeat-backup` invocation in the same chat session
   b) User typing exactly "DEPLOY" (case-sensitive) when prompted
2. NEVER skip smoke tests on production, regardless of skip_smoke flag.
3. NEVER hardcode paths/users/sites. Always look up from the dispatch table.
4. ALWAYS record before-state (commit hash, branch) before pulling, so
   rollback target is known.
5. ALWAYS pair `bench migrate` with `bench clear-cache` and
   `bench clear-website-cache` (gotcha #6).
6. ALWAYS run `bench build --app custom_erp` after migrate so JS/CSS
   assets are rebuilt.
7. ALWAYS restart workers after build so the new controller code loads.
8. NEVER use raw SQL in deploy scripts. Bench commands only.
9. NEVER suppress migrate failures with --skip-failing on production.
10. ALWAYS chain `infrabeat-smoke-test` against target_env after deploy.
    On production failure, ALSO chain `infrabeat-rollback` automatically.
    On dev/staging failure, REPORT but do not auto-rollback.

## Steps

1. **Validate target_env.** If missing or invalid, ask user.

2. **Look up dispatch row** for target_env. Bind: $vm_ip, $ssh_user,
   $bench_user, $bench_path, $site, $branch.

3. **Check SSH reachability** via Frappe Assistant Core MCP or a single
   `ssh -o ConnectTimeout=5 -o BatchMode=no $ssh_user@$vm_ip "echo ok"`.
   If unreachable, abort with clear error. Especially relevant for
   production (not yet provisioned in current phase).

4. **If target_env is production:**
   a) Verify `infrabeat-backup` was invoked in this session and succeeded.
      If not, abort and instruct user to run backup first.
   b) Print this prompt and WAIT for user response:
      "Type DEPLOY to confirm production deployment to {target}. Any other
      input cancels."
   c) If user does not type exactly "DEPLOY", abort cleanly. Log the
      cancellation with timestamp.

5. **Record before-state** by SSHing and running:
Capture all three. These go into the audit log entry and into the
   rollback target if smoke fails.

6. **Render the deploy bash** from `templates/deploy.sh.tmpl` with these
   substitutions:
   - {{TARGET_ENV}}, {{VM_IP}}, {{SSH_USER}}, {{BENCH_USER}},
     {{BENCH_PATH}}, {{SITE}}, {{BRANCH}}, {{TIMESTAMP}}

7. **Plan Mode preview.** Before executing, show the user:
   - Target: {target_env} VM at {vm_ip}
   - Branch: {branch}
   - Before-state: branch={BEFORE_BRANCH}, head={BEFORE_HEAD}
   - Bash that will run (full rendered script)
   - On smoke failure: what will happen ({rollback for prod, report for dev/staging})

   For dev/staging, proceed automatically after preview.
   For production, the DEPLOY confirmation in step 4 already covered consent.

8. **Execute deploy** by SSHing to $ssh_user@$vm_ip and piping the rendered
   bash script over stdin. Capture full stdout+stderr. Set timeout to
   600 seconds (migrate can be slow).

9. **Capture after-state:**
10. **Chain infrabeat-smoke-test** against target_env. Capture pass/fail.

11. **On smoke failure:**
    - target_env=production: chain infrabeat-rollback with target=production
      and rollback_to=$BEFORE_HEAD_FULL. Notify user prominently.
    - target_env=dev or staging: report failure clearly. Do NOT auto-rollback.
      Suggest user inspect logs and decide.

12. **Write audit log entry** to `audit_log/deploys.jsonl` (append-only):
{"ts": "...", "skill": "infrabeat-deploy", "target": "...",
 "branch": "...", "before_head": "...", "after_head": "...",
 "smoke_result": "pass|fail", "rolled_back": true|false,
 "user": "..."}
13. **Report to user:**
    - Target, branch, before/after head
    - Smoke test result
    - URL to verify: http://{vm_ip}/app
    - If rolled back: clear "ROLLED BACK" header, root cause hint

## Verification (skill self-check before reporting success)

After execution:
- [ ] SSH succeeded (deploy bash exit code 0)
- [ ] After-head differs from before-head (proves git pull moved HEAD)
- [ ] bench migrate output contains no "Traceback" or "ERROR"
- [ ] bench build output contains "Build complete" or equivalent
- [ ] Workers restarted (supervisor or `bench restart` exit 0)
- [ ] Smoke test invoked (regardless of result)
- [ ] Audit log entry written

If after-head equals before-head, that means git pull found nothing new.
Report this clearly ("Already up to date, no changes deployed") and do NOT
fail the skill. Idempotent re-runs are valid.

## Out of scope (explicit non-goals)

- Cross-environment promotion (use infrabeat-promote, which chains this skill)
- First-time provisioning (use Ansible playbooks in infra/ansible/)
- Rolling back without smoke-test failure (use infrabeat-rollback directly)
- Database surgery, schema patches outside bench migrate (use bench patches)
- Changing branch protection or PR rules (out of scope, manual GitHub op)