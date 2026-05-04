---
name: infrabeat-deploy
description: "Use this skill when the user asks to deploy a branch to a target VM. Triggers include 'deploy to dev', 'deploy to staging', 'deploy to production', 'push to dev VM', 'roll out feature/X to dev'. SSHes to the target VM as the right user, runs git pull + bench migrate + bench clear-cache + bench build + worker restart in the correct bench path per VM_INVENTORY.md. Production deploys MUST be preceded by infrabeat-backup and require explicit DEPLOY confirmation. Do NOT use for cross-environment promotion (use infrabeat-promote) or for first-time provisioning."
---

# infrabeat-deploy

> **STATUS:** Stub. Implementation pending in Phase 3.
> Frontmatter is valid (name + description) so Claude Code skill discovery picks it up.
> Body will be filled with: When invoked / Inputs / Hard rules / Steps / Verification.