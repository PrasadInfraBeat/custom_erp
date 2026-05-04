---
name: infrabeat-smoke-test
description: "Use this skill when the user asks to verify, smoke-test, health-check, or validate a target VM (dev, staging, or production). Triggers include 'smoke test', 'health check', 'verify dev', 'check staging is healthy', 'is prod up', 'validate the deploy'. Also auto-invoked by infrabeat-deploy post-deploy. Runs the standard 6-check battery (SSH reachable, site 200, login API, Customer Visit list 200, DocType meta valid, workers running) plus 2 advisory checks (disk free, redis reachable) via Frappe Assistant Core MCP where available, falling back to SSH+curl. Returns a structured pass/fail table with per-check status and latency. Do NOT use for full diagnostics (use bench doctor or deeper logs) or for creating tests inside the codebase (use infrabeat-script for that)."
---

# infrabeat-smoke-test

Run the 6-check + 2-advisory smoke battery against a target VM and return a
structured result. Used standalone for ad-hoc health checks AND chained from
infrabeat-deploy to gate auto-rollback decisions.

## When invoked

User asks to verify or health-check a VM. Examples:
- "Smoke test dev"
- "Is staging healthy?"
- "Verify production is up"
- "Run smoke checks on dev VM"

Also auto-invoked (no user prompt) when:
- infrabeat-deploy completes a deploy and needs to validate
- infrabeat-promote needs to validate target env before/after promotion

## Inputs

REQUIRED:
1. **target_env** - one of: `dev`, `staging`, `production`. Inferred from
   user wording. If ambiguous, ASK.

OPTIONAL:
2. **timeout_seconds** - per-check HTTP timeout. Default: 10.
3. **strict** - if true, fail on advisory warnings too. Default: false.

## Per-environment dispatch (VM_INVENTORY.md)

| target_env  | VM IP        | SSH user  | Bench user | Bench path                   | Site            |
|-------------|--------------|-----------|------------|------------------------------|-----------------|
| dev         | 10.1.0.184   | erpadmin  | frappe     | /home/frappe/frappe-bench    | erp.local       |
| staging     | 10.1.0.185   | erpadmin  | erpadmin   | /home/erpadmin/frappe-bench  | erp.staging     |
| production  | 10.1.0.186   | erpadmin  | erpadmin   | /home/erpadmin/frappe-bench  | erp.production  |

Production VM is NOT YET PROVISIONED as of Phase 3. Skill must report
"VM unreachable" cleanly without crashing.

## The 6-check battery (each MUST pass for overall PASS)

### 1. SSH reachable
- Transport: SSH probe via `ssh -o ConnectTimeout=5 -o BatchMode=no $ssh_user@$vm_ip "echo ok"`
- Pass: stdout contains "ok", exit 0
- Fail: timeout, connection refused, auth failure

### 2. Site root returns 200
- Transport: HTTP `curl -s -o /dev/null -w "%{http_code}" http://$vm_ip/`
- Pass: 200
- Fail: non-200 or timeout

### 3. Login API works
- Transport: HTTP POST to `/api/method/login` with admin credentials
- Pass: 200, response sets cookie
- Fail: 401, 500, timeout

### 4. Customer Visit list returns 200
- Transport: prefer Frappe Assistant Core MCP `list_documents` tool with
  doctype="Customer Visit". Fallback to authenticated curl with cookie
  from check 3.
- Pass: 200, response is valid JSON list
- Fail: 404 (DocType missing - module path bug), 500, timeout
- Why this DocType: it exists on dev/staging from Stage 1A baseline.
  Customer Visit list 200 = custom_erp module folder nesting is correct
  (gotcha #2 not violated).

### 5. DocType meta fetch returns valid JSON
- Transport: prefer MCP `get_doctype` tool. Fallback to curl
  `/api/method/frappe.client.get?doctype=DocType&name=Customer%20Visit`
- Pass: 200, response is parseable JSON with "fields" array
- Fail: invalid JSON, missing fields, 404

### 6. Workers running
- Transport: SSH probe `sudo supervisorctl status`. Filter for
  `frappe-bench-frappe-web` and `frappe-bench-frappe-default-worker`
  (or equivalent for the env). Pass if state == RUNNING for all.
- Pass: all expected workers in RUNNING state
- Fail: any worker FATAL/STOPPED/BACKOFF

## The 2 advisory checks (WARN, do not fail unless strict=true)

### A1. Disk free > 10%
- Transport: SSH probe `df -h $bench_path | tail -1 | awk '{print $5}'`
- Warn: usage >= 80% (less than 20% free)
- Critical (fail): usage >= 90% even when strict=false

### A2. Redis reachable
- Transport: SSH probe `redis-cli -p 11000 ping` (Frappe v15 redis-cache port)
- Warn: PONG not returned

## Hard rules

1. NEVER skip checks even if user says "just a quick check". Battery is
   atomic - all 6 always run.
2. NEVER report PASS if any of the 6 mandatory checks failed. Advisory
   warnings do NOT downgrade PASS to FAIL unless strict=true.
3. ALWAYS prefer MCP transport over curl when MCP is wired (currently dev VM).
4. ALWAYS measure latency per check. Slow PASS is a yellow flag.
5. NEVER include credentials in audit log entries. Log "auth=ok" not the
   admin password.

## Steps

1. Validate target_env. Resolve dispatch row to $vm_ip, $ssh_user, $site, etc.
2. Run check 1 (SSH). If FAIL, abort battery and report - all subsequent
   checks would fail anyway.
3. Run checks 2-5 in parallel where possible (HTTP probes are independent).
4. Run check 6 (workers) via SSH.
5. Run advisory checks A1, A2 via SSH.
6. Aggregate result: overall PASS iff checks 1-6 all PASS.
7. Build structured result table.
8. Write audit log entry to `audit_log/smoke_tests.jsonl`.
9. Report result to invoker (user OR parent skill).

## Output format (structured)

For each check, emit:



User-facing summary table:
## Steps when invoked from infrabeat-deploy (chained mode)

Same battery, same checks. Differences:
- Caller is the deploy skill, not the user
- Result returned as structured dict, not just printed
- On FAIL with target_env=production, return `{rollback: true, before_head: <captured by deploy>}`
- On FAIL with target_env=dev or staging, return `{rollback: false, hint: "manual investigation"}`

## Verification (skill self-check)

Before reporting PASS:
- [ ] All 6 mandatory checks ran (none SKIPPED unless SSH check 1 failed)
- [ ] Latencies are non-zero (zero usually means the probe didn't actually run)
- [ ] Customer Visit list response was parsed as JSON, not just status-coded
- [ ] DocType meta has "fields" key with array value
- [ ] Audit log entry written

## Out of scope

- Full diagnostics with stack traces (use `bench doctor`, log files manually)
- Synthetic transactions (creating test records and verifying flow)
- Performance benchmarks (latency thresholds are sanity, not SLA)
- Cross-VM comparison (this skill is per-VM; orchestration is parent skill's job)