---
name: infrabeat-database-op
description: "Use this skill when the user asks to run a database query, bulk update, or schema-touching operation against a target VM. Triggers include 'query DB on dev', 'bulk update X records', 'count rows where', 'show me records that match', 'run SQL on staging'. Routes the operation through Frappe Assistant Core MCP using parameterized queries (never raw concatenation), writes audit log entry, and requires explicit confirmation for any DELETE/UPDATE/DROP. Do NOT use for routine record CRUD (use Frappe REST API directly) or for production schema migrations (use bench patches via infrabeat-deploy)."
---

# infrabeat-database-op

> **STATUS:** Stub. Implementation pending in Phase 3.
> Frontmatter is valid (name + description) so Claude Code skill discovery picks it up.
> Body will be filled with: When invoked / Inputs / Hard rules / Steps / Verification.