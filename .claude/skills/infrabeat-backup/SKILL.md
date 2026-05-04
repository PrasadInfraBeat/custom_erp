---
name: infrabeat-backup
description: "Use this skill when the user asks to back up a VM, or before any production deployment (mandatory pre-prod-deploy step). Triggers include 'backup prod', 'snapshot staging', 'create backup', or any infrabeat-deploy invocation targeting production. Runs bench backup with files on the target VM, names the archive with timestamp + git commit hash, stores under /home/<benchuser>/backups/, and emits the absolute path for use by infrabeat-rollback if needed. Do NOT use for restore (use infrabeat-rollback) or for partial table backups."
---

# infrabeat-backup

> **STATUS:** Stub. Implementation pending in Phase 3.
> Frontmatter is valid (name + description) so Claude Code skill discovery picks it up.
> Body will be filled with: When invoked / Inputs / Hard rules / Steps / Verification.