---
name: infrabeat-smoke-test
description: "Use this skill when the user asks to verify, smoke-test, health-check, or validate a target VM (dev, staging, or production). Triggers include 'smoke test', 'health check', 'verify dev', 'check staging is healthy', 'is prod up'. Runs the standard 6-check battery (SSH reachable, site 200, login API, list endpoint 200, DocType meta valid, workers running) via Frappe Assistant Core MCP and returns a structured pass/fail table. Do NOT use for creating tests (use infrabeat-script for that) or for full system diagnostics."
---

# infrabeat-smoke-test

> **STATUS:** Stub. Implementation pending in Phase 3.
> Frontmatter is valid (name + description) so Claude Code skill discovery picks it up.
> Body will be filled with: When invoked / Inputs / Hard rules / Steps / Verification.