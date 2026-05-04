---
name: infrabeat-doctype
description: "Use this skill when the user asks to create, scaffold, or generate a new ERPNext DocType in custom_erp. Triggers include phrases like 'create DocType', 'new DocType', 'scaffold DocType', 'add DocType', or any prompt naming a DocType to be built. Produces 5 files (JSON, Python controller, JS client script, test, install bash) and writes them to apps/custom_erp/custom_erp/custom_erp/doctype/<snake_name>/ for review in VS Code BEFORE commit. Do NOT use for modifying existing DocTypes (use infrabeat-script with custom fields), for ERPNext core DocTypes (forbidden), or for child tables alone (mention 'child table' to switch behavior)."
---

# infrabeat-doctype

> **STATUS:** Stub. Implementation pending in Phase 3.
> Frontmatter is valid (name + description) so Claude Code skill discovery picks it up.
> Body will be filled with: When invoked / Inputs / Hard rules / Steps / Verification.