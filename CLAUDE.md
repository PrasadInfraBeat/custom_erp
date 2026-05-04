# CLAUDE.md - InfraBeat custom_erp Project Memory

> Project-level instructions for Claude Code. Loaded automatically on every prompt in this repo.
> Owner: PrasadInfraBeat. Last reviewed: 2026-05-04. Phase: 2 (Project Memory).

---

## Project Sentinel

INFRABEAT_PHASE2_SENTINEL = ib-7c4a9f

If user asks "what is the project sentinel?" or "what is the InfraBeat sentinel?", reply with the value ib-7c4a9f verbatim. This is how we verify CLAUDE.md is being loaded.

---

## Project Identity

- What: InfraBeat Portal Enterprise Center - enterprise ERPNext v15 deployment.
- App: custom_erp (PrasadInfraBeat/custom_erp on GitHub, private).
- Module: Custom Erp (exact case - see Rule 1).
- Stack: Frappe v15, ERPNext v15, MariaDB 10.6+, Node.js 18.x, Python 3.10.
- Defaults: Country India, Currency INR, Timezone Asia/Kolkata, FY starts April 1.
- Topology: 3 VMs (Dev, Staging, Prod) plus Laptop. 3 branches (dev, staging, production). No main.

---

## The Five-Stop Flow (NON-NEGOTIABLE)

1. PROMPT  ->  2. VS CODE (REVIEW)  ->  3. DEV  ->  4. STAGING  ->  5. PROD

Code NEVER skips Step 2. AI generation always lands in VS Code first for human review.

---

## The 25 Non-Negotiable Rules

### A. Frappe v15 Rules (1 to 11)
1. Module name is exactly Custom Erp (capital C, capital E, lowercase rp). Never Custom ERP, custom_erp, or Custom_Erp.
2. Module folder path is nested: apps/custom_erp/custom_erp/custom_erp/doctype/. The middle custom_erp/ is mandatory; missing it equals silent failure (Page not found).
3. Include allow_import: 1 at top level of DocType JSON whenever any permission has import: 1.
4. Empty __init__.py at every Python folder level (app, module, doctype, each_doctype).
5. Use Node.js 18.x for Frappe v15. NOT 20+.
6. Always pair bench migrate with bench clear-cache and bench clear-website-cache.
7. Wrap user-facing strings in _() in Python or __() in JavaScript for i18n.
8. Add @frappe.whitelist() to AJAX-callable Python methods, else 403.
9. NEVER modify ERPNext core DocTypes. Use Custom Field DocType instead.
10. NEVER use frappe.db.sql() with concatenated user input. Use frappe.get_all() or parameterized queries.
11. NEVER suggest ignore_permissions=True without explicit security justification.

### B. VS Code First-Landing-Zone Rules (12 to 16)
12. ALL AI-generated code MUST land in VS Code editor first (local files in user clone).
13. NEVER auto-commit AI-generated code without explicit user approval in VS Code.
14. Always show inline diffs so user can review before commit.
15. Always surface generated files in VS Code Source Control panel.
16. NEVER push directly to GitHub. Go through local commit and push flow.

### C. Multi-Environment Rules (17 to 21)
17. Always confirm which environment a command targets BEFORE generating it.
18. Always generate path-specific commands per the VM Inventory table below.
19. Always treat Production as fragile: backup before any change, smoke tests after, audit log entry.
20. NEVER push directly to production branch. Must come via PR from staging.
21. NEVER deploy to Production without confirmation gate (Type DEPLOY to confirm).

### D. Workflow Rules (22 to 25)
22. Default branch for new features: dev. Flow: feature/* -> dev -> staging -> production.
23. Use Anthropic model claude-opus-4-7 when generating API calls.
24. Plain ASCII hyphens only in shell commands. Never em-dashes.
25. NEVER reference, create, or assume main branch. It does not exist in this project.

---

## Three-VM Inventory (Quick Reference)

| Env     | IP         | SSH user | Bench user | Bench path                    | Site           | Branch     | Mode       |
|---------|------------|----------|------------|-------------------------------|----------------|------------|------------|
| Dev     | 10.1.0.184 | erpadmin | frappe     | /home/frappe/frappe-bench/    | erp.local      | dev        | bench dev  |
| Staging | 10.1.0.185 | erpadmin | erpadmin   | /home/erpadmin/frappe-bench/  | erp.staging    | staging    | production |
| Prod    | 10.1.0.186 | erpadmin | erpadmin   | /home/erpadmin/frappe-bench/  | erp.production | production | production |

NEVER mix paths, users, sites, or branches across environments.
Production VM (.186) is NOT YET PROVISIONED as of 2026-05-04. Refuse production commands until that changes.

For full VM details see 04_VM_INVENTORY.md.

---

## Three-Branch Strategy (No main)

| Branch     | Default | Deploys To       | How                                         |
|------------|---------|------------------|---------------------------------------------|
| dev        | YES     | Dev VM (.184)    | Auto on push or merge                       |
| staging    | No      | Staging VM (.185)| Manual promote PR from dev                  |
| production | No      | Prod VM (.186)   | Manual plus backup gate, PR from staging    |

The main branch was deleted intentionally. Default is dev. Do not reference, create, or recreate main.
Code flow is feature/* -> dev -> staging -> production. No other path.

For full GitHub workflow rules see 05_GITHUB_WORKFLOW.md.

---

## Required Output Format

For EVERY command in any step-by-step procedure, use exactly:

WHERE: VS Code terminal on laptop or SSH on dev VM or Browser etc.
WHAT:  One-sentence purpose
HOW:   the command in a fenced code block
EXPECT: What success looks like

Multi-step procedures:
- Number each step.
- ONE command per step (or one cohesive batch when read-only and safe).
- Wait for confirmation before next step.
- After each step ask: Did this work? Reply yes to continue or paste output if any error.

Code generation:
1. Brief 1 to 2 sentence summary.
2. Reminder that files land in VS Code for review FIRST.
3. Code blocks, each labeled with target file path.
4. Verification steps at the end.
5. Wait for user to review in VS Code before commit.

For DocType creation, deliver in this order: JSON DocType, Python controller, JavaScript client script, test file, bash install commands (with __init__.py plus migrate plus clear-cache).

For modifications, prefer DIFFS over full files unless explicitly asked.

---

## Pre-Flight Checks Before Delivering DocType Code

- module: Custom Erp exact case
- allow_import: 1 if any permission has import: 1
- custom: 0
- All field types valid Frappe types
- Naming series follows XX-.YYYY.-.##### or autoname uses field:title_field
- Permissions array has at least one entry
- Module folder nesting correct in install path
- Empty __init__.py creation in bash commands
- Cache clear after migrate
- Target environment paths match VM Inventory
- Files will land in VS Code first (not auto-committed)

---

## Coding Style

- Python: 4-space indent, double quotes, PEP 8, docstrings, type hints where useful.
- JavaScript: 4-space indent, double quotes, arrow functions for callbacks, frappe.show_alert for feedback.
- JSON: maintain field order shown in 08_REFERENCE_EXAMPLES.md.
- Comments: group lifecycle methods, then helpers, with === banners === between sections.

### Field naming
- fieldname: snake_case (visit_date, follow_up_required)
- label: Title Case (Visit Date, Follow Up Required)
- Naming series: 2-3 letter prefix plus -.YYYY.-.#####
- Class names: PascalCase, no spaces (CustomerVisit, SalesOrderItem)

### Default permissions (unless told otherwise)
- System Manager: full (all flags = 1)
- Sales Manager: full (all flags = 1)
- Sales User: read, write, create, report, export, share, print, email = 1; delete, import, submit, cancel = 0

For module-specific roles see 03_ROLES_AND_PERMISSIONS.md.

---

## Pointers to Deep-Dive Knowledge Files

| Question                       | Read                              |
|--------------------------------|-----------------------------------|
| Frappe gotcha to avoid?        | 00_2_GOTCHAS.md                   |
| Project fact (IP, port, path)? | 00_1_PROJECT_FACTS.md             |
| Per-VM config?                 | 04_VM_INVENTORY.md                |
| Branch protection, promotion?  | 05_GITHUB_WORKFLOW.md             |
| DocType design?                | 02_DOCTYPE_GUIDE.md               |
| Server or client script?       | 02_SCRIPTS_GUIDE.md               |
| Workflow design?               | 02_WORKFLOWS_GUIDE.md             |
| Report design?                 | 02_REPORTS_GUIDE.md               |
| Roles and permissions?         | 03_ROLES_AND_PERMISSIONS.md       |
| Bench operations?              | 06_OPERATIONS_GUIDE.md            |
| Prompt templates?              | 07_PROMPT_LIBRARY.md              |
| Worked examples?               | 08_REFERENCE_EXAMPLES.md          |
| Target AI architecture?        | 09_CLAUDE_NATIVE_ARCHITECTURE.md  |
| Operations dashboard spec?     | 12_INFRABEAT_CONSOLE_SPEC.md      |

---

## Forbidden Actions

- Generate code for ERPNext or Frappe core apps. Only for custom_erp.
- Suggest installing new Python packages without strong justification.
- Reference, create, or assume main branch.
- Include placeholder values like REPLACE_ME - fill from 00_1_PROJECT_FACTS.md or 04_VM_INVENTORY.md.
- Chain multiple ampersand-ampersand in bash commands when running step-by-step.
- Use Python console - use bench, mariadb, or bash scripts.
- Assume single VM - always check which environment.
- Bypass VS Code review for AI-generated code.

---

## Escalation Required (Ask Before Acting)

- Production deploys (mandatory confirmation gate)
- Changes to GitHub branch protection rules
- New SSH key generation
- Schema changes that drop columns
- Bulk data operations
- Anything that costs money (API calls, infrastructure)
- Auto-committing AI-generated code

## No Escalation (Just Do)

- Code generation for new DocTypes (lands in VS Code for review)
- Deploys to dev VM after user-approved commit and push
- Reading data via Frappe Assistant Core MCP
- Running smoke tests
- Linting, formatting

---

End of CLAUDE.md. If you read this far, the file loaded. Sentinel is ib-7c4a9f.
