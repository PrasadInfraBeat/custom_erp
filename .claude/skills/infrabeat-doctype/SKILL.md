---
name: infrabeat-doctype
description: "Use this skill when the user asks to create, scaffold, or generate a new ERPNext DocType in custom_erp. Triggers include phrases like 'create DocType', 'new DocType', 'scaffold DocType', 'add DocType', or any prompt naming a DocType to be built. Produces 5 files (JSON, Python controller, JS client script, test, install bash) and writes them to apps/custom_erp/custom_erp/custom_erp/doctype/<snake_name>/ for review in VS Code BEFORE commit. Do NOT use for modifying existing DocTypes (use infrabeat-script with custom fields), for ERPNext core DocTypes (forbidden), or for child tables alone (mention 'child table' to switch behavior)."
---

# infrabeat-doctype

Generate a complete, project-compliant ERPNext v15 DocType into the local
custom_erp app for review in VS Code before commit.

## When invoked

User asks to create or scaffold a new DocType in custom_erp. Examples:
- "Create a Sales Inquiry DocType with customer, product, urgency, status"
- "Scaffold a Site Visit DocType, naming series SV-.YYYY.-.#####"
- "New DocType: Customer Feedback, fields: customer, rating, comment"

## Inputs to gather from user prompt

REQUIRED:
1. **DocType name** (Title Case, e.g. "Sales Inquiry")
2. **Field list** with at minimum: fieldname, fieldtype, label, required (Y/N).
   Optional per field: options, default, in_list_view, in_standard_filter, reqd.

OPTIONAL (sensible defaults if absent):
3. **Naming series prefix** (2-3 letters). Default: derive from DocType name initials.
4. **Title field** (which field shows as record title). Default: first Data field.
5. **Submittable** (yes/no). Default: no.
6. **Track changes** (yes/no). Default: yes.
7. **List view fields** (up to 5). Default: title field + first 3 fields.
8. **Filters** (2-3 fields). Default: status field if present, otherwise none.
9. **Permissions**. Default: System Manager (full), Sales Manager (full),
   Sales User (read/write/create/report/export/share/print/email).

If REQUIRED inputs are missing or ambiguous, ASK the user before generating.
Do NOT invent fields the user did not specify.

## Hard rules (NON-NEGOTIABLE - from 00.2_GOTCHAS.md and CLAUDE.md)

1. Module name is EXACTLY "Custom Erp" (capital C, capital E, lowercase rp).
   Never "Custom ERP", "custom_erp", or "Custom_Erp" in JSON `module` field.
2. File path is EXACTLY:
   apps/custom_erp/custom_erp/custom_erp/doctype/<snake_name>/
   The middle `custom_erp/` is the module folder. Missing it = silent failure.
3. JSON top-level MUST include `"allow_import": 1` if any permission row has
   `"import": 1`. Otherwise import button does not render.
4. JSON top-level MUST include `"custom": 0` (this is project-owned, not a
   custom field).
5. Empty `__init__.py` MUST be created at every Python folder level:
   - apps/custom_erp/custom_erp/custom_erp/__init__.py (likely exists)
   - apps/custom_erp/custom_erp/custom_erp/doctype/__init__.py (likely exists)
   - apps/custom_erp/custom_erp/custom_erp/doctype/<snake_name>/__init__.py (NEW)
6. fieldname MUST be snake_case. label MUST be Title Case.
7. Naming series pattern: `<PREFIX>-.YYYY.-.#####` (e.g. `SI-.YYYY.-.#####`).
8. Class name in controller MUST be PascalCase, no spaces (SalesInquiry).
9. Python: 4-space indent, double quotes, PEP 8, type hints where useful.
   Wrap user-facing strings in `_()` for i18n.
10. JavaScript: 4-space indent, double quotes, arrow functions for callbacks.
    Wrap user-facing strings in `__()` for i18n.
11. AJAX-callable Python methods MUST have `@frappe.whitelist()` decorator.
12. NEVER use `frappe.db.sql()` with concatenated user input. Use
    `frappe.get_all()` or parameterized queries.
13. NEVER suggest `ignore_permissions=True` without explicit security
    justification.
14. **Files land in VS Code editor as UNTRACKED CHANGES.** Do NOT git add,
    git commit, or git push. The user reviews in VS Code Source Control
    panel and decides when to commit. (Non-negotiable rule #12.)

## Steps

1. **Validate inputs.** If DocType name or field list missing, ask user.
   Do not proceed with placeholders.

2. **Derive computed values:**
   - snake_name = lowercase, spaces -> underscores (e.g. "Sales Inquiry" -> "sales_inquiry")
   - class_name = PascalCase, no spaces (e.g. "SalesInquiry")
   - prefix = if user gave one, use it; else first letter of each word, uppercased
   - title_field = if user gave one; else first Data fieldtype in field list

3. **Read template files** in this skill's `templates/` directory:
   - templates/doctype.json.tmpl
   - templates/controller.py.tmpl
   - templates/client.js.tmpl
   - templates/test.py.tmpl
   - templates/install.sh.tmpl

4. **Substitute placeholders** in each template. Placeholders use `{{NAME}}` syntax:
   - {{DOCTYPE_NAME}} -> Title Case name (e.g. "Sales Inquiry")
   - {{SNAKE_NAME}} -> snake_case (e.g. "sales_inquiry")
   - {{CLASS_NAME}} -> PascalCase (e.g. "SalesInquiry")
   - {{NAMING_PREFIX}} -> 2-3 letters (e.g. "SI")
   - {{TITLE_FIELD}} -> the title fieldname
   - {{FIELDS_JSON}} -> the rendered fields array (JSON)
   - {{PERMISSIONS_JSON}} -> the rendered permissions array (JSON)
   - {{LIST_VIEW_FIELDS}} -> comma-separated list view fieldnames
   - {{TIMESTAMP}} -> ISO timestamp at generation time

5. **Write rendered files** using Claude Code's Write tool. Target paths
   (relative to repo root):

   - apps/custom_erp/custom_erp/custom_erp/doctype/{{SNAKE_NAME}}/__init__.py
     (empty file, just create it)
   - apps/custom_erp/custom_erp/custom_erp/doctype/{{SNAKE_NAME}}/{{SNAKE_NAME}}.json
   - apps/custom_erp/custom_erp/custom_erp/doctype/{{SNAKE_NAME}}/{{SNAKE_NAME}}.py
   - apps/custom_erp/custom_erp/custom_erp/doctype/{{SNAKE_NAME}}/{{SNAKE_NAME}}.js
   - apps/custom_erp/custom_erp/custom_erp/doctype/{{SNAKE_NAME}}/test_{{SNAKE_NAME}}.py
   - apps/custom_erp/custom_erp/custom_erp/doctype/{{SNAKE_NAME}}/install.sh
     (the install commands; user runs this manually after review or via infrabeat-deploy)

6. **STOP. Do NOT git add, commit, or push.** Report to user:

   > Generated 6 files for {{DOCTYPE_NAME}} DocType into VS Code:
   > [list of paths]
   >
   > Review in VS Code Source Control panel. When ready, commit on a
   > feature branch. To deploy, invoke infrabeat-deploy.

## Verification (skill self-check before reporting success)

After writing files, verify each:
- [ ] All 6 files exist at the correct paths
- [ ] doctype.json parses as valid JSON (no syntax errors)
- [ ] controller.py parses as valid Python (no syntax errors)
- [ ] client.js has no obvious syntax errors (balanced braces, semicolons)
- [ ] test.py parses as valid Python
- [ ] JSON `module` field is exactly "Custom Erp"
- [ ] JSON includes `"custom": 0`
- [ ] If any permission row has `"import": 1`, top-level has `"allow_import": 1`
- [ ] __init__.py exists in the new doctype folder
- [ ] No `git add` or `git commit` was run

If any check fails, fix and re-verify. Do not report success on a partially
generated DocType.

## Out of scope (explicit non-goals)

- Migrating existing DocTypes (use infrabeat-script with Custom Field DocType)
- Modifying ERPNext core DocTypes (forbidden by rule #9 of CLAUDE.md)
- Running bench migrate / build / clear-cache (that is infrabeat-deploy's job)
- Committing or pushing to git (that is the user's job, after VS Code review)
- Creating standalone child tables (mention "child table" in prompt to trigger
  child-table-specific behavior - different istable: 1 flag handling)