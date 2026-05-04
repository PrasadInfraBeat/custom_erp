---
name: infrabeat-rollback
description: "Use this skill when the user asks to roll back, revert, or restore a VM to a previous state after a bad deploy. Triggers include 'rollback prod', 'revert staging', 'restore from backup', 'undo last deploy', or auto-invoked when infrabeat-smoke-test fails post-production-deploy. Restores the most recent infrabeat-backup archive on the target VM via bench restore + reverts custom_erp app to the prior git commit. Do NOT use for git-only revert without DB issues (use plain git revert) or for cross-environment recovery."
---

# infrabeat-rollback

> **STATUS:** Stub. Implementation pending in Phase 3.
> Frontmatter is valid (name + description) so Claude Code skill discovery picks it up.
> Body will be filled with: When invoked / Inputs / Hard rules / Steps / Verification.