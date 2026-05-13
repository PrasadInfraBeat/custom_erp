<!-- Phase 6E.5 / L49: covers ERPNext, CI/infra, refactor, docs, security PRs. Branch flow: feature/* -> dev -> staging -> production. No main branch. -->

## Summary

<!-- Brief description of the change and why it is needed. -->

## Type of change

- [ ] Bug fix
- [ ] New feature
- [ ] Refactor (no behavior change)
- [ ] Docs only
- [ ] CI/Infra (workflows, branch protection, tooling)
- [ ] Test-only
- [ ] Security/credentials hygiene
- [ ] Other

## Testing Done

- [ ] `python -m pytest tools/infrabeat_erp/tests/ -q` passes locally (N/A for docs/template-only PRs)
- [ ] `bench migrate` clean on dev VM (N/A for non-ERPNext PRs)
- [ ] Markdown rendered cleanly in PR preview (N/A for non-docs PRs)
- [ ] Manual smoke test (describe what was tested)

## Validation

- [ ] All required CI checks green
- [ ] No plaintext credentials introduced (git grep verified for admin123, Erpinfra@123)
- [ ] Branched from and targeting dev/staging/production - never main (no main branch exists)
- [ ] Squash-merge convention will be honored
- [ ] No files committed outside the explicit scope of this PR

## Out of scope

<!-- Short bulleted list of deferred work intentionally NOT included in this PR. -->

-
