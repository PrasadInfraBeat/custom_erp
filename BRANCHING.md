# Branching Strategy for custom_erp

## Branch Structure

| Branch | Purpose | Protection |
|---|---|---|
| dev | Active development; Claude AI commits here | None (open) |
| staging | QA / UAT testing | PR + 1 review required |
| production | Live deployment branch | PR + 1 review + CI pass |
| main | Stable release tags only | PR + 1 review |

## Promotion Flow

dev  -->  staging  -->  production  -->  main

## Workflow Rules (Enforced via GitHub Actions)

1. Direct pushes to protected branches are blocked - must come via PR merge
2. All PRs require at least 1 approving review
3. All PRs must pass Python lint, JSON validation, secrets scan
4. CODEOWNERS auto-requests review for critical files

## How to Develop

1. git checkout dev
2. git pull origin dev
3. Make changes
4. git add . && git commit -m "feat: ..."
5. git push origin dev
6. Create PR dev to staging on GitHub

## Emergency Hotfix

1. git checkout -b hotfix/issue-name production
2. Fix + commit + push
3. Create PR hotfix to production
4. After merge, also merge into dev and staging
