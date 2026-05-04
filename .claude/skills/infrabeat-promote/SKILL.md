---
name: infrabeat-promote
description: "Use this skill when the user asks to promote code from one environment to the next. Triggers include 'promote to staging', 'promote to production', 'merge dev into staging', 'ship to prod'. Verifies source-env smoke tests pass, opens a GitHub PR (dev->staging or staging->production), waits for CI green, merges, then chains infrabeat-deploy on the target VM. Production target ALSO chains infrabeat-backup before deploy and requires DEPLOY confirmation. Do NOT use for hotfix branches that skip environments or for cross-repo promotion."
---

# infrabeat-promote

> **STATUS:** Stub. Implementation pending in Phase 3.
> Frontmatter is valid (name + description) so Claude Code skill discovery picks it up.
> Body will be filled with: When invoked / Inputs / Hard rules / Steps / Verification.