# InfraBeat Ansible Playbooks

Idempotent automation for the 3 InfraBeat ERPNext VMs (dev, staging, production).
Created in **Phase 7b Sprint 0 Task A**.

## Layout

```
infra/ansible/
  ansible.cfg              # Project config (inventory location, SSH defaults)
  inventory/
    dev.yml                # Dev VM (10.1.0.184)
    staging.yml            # Staging VM (10.1.0.185)
    production.yml         # Production VM (10.1.0.186)
  playbooks/
    preflight.yml          # Ping + sudo + bench path verification (~10s)
    ssh_keys.yml           # Distribute laptop SSH key to VM (idempotent)
    bootstrap.yml          # OS prereqs + Node 18.x + bench/ERPNext/FAC detection
```

## Prerequisites

- Ansible 2.14+ on a control node (laptop WSL or any VM with ssh access to all 3)
- SSH key `~/.ssh/infrabeat_ed25519` distributed (run `python scripts/bootstrap_ssh_keys.py` first if greenfield)
- Collections: `ansible-galaxy collection install ansible.posix community.general`

## Usage

Dry-run preflight against staging:
```
cd infra/ansible
ansible-playbook -i inventory/staging.yml playbooks/preflight.yml --check
```

Distribute SSH key (idempotent):
```
for env in dev staging production; do
  ansible-playbook -i inventory/$env.yml playbooks/ssh_keys.yml
done
```

Bootstrap dev:
```
ansible-playbook -i inventory/dev.yml playbooks/bootstrap.yml
```

Tag-scoped run (only Node section):
```
ansible-playbook -i inventory/dev.yml playbooks/bootstrap.yml --tags node
```

## Scope Boundaries

`bootstrap.yml` covers OS-level prereqs and **version detection only**. It does NOT install bench / ERPNext / FAC from scratch (those are 30+ min flows with careful version pins per closure `14_PHASE_4_CLOSURE.md`). Detection tasks REPORT missing components; full install is an operator runbook step.

Future expansions (out of scope here):
- `bench_install.yml` - full bench bootstrap from clean Ubuntu
- `erpnext_install.yml` - frappe + erpnext app install
- `fac_install.yml` - Frappe Assistant Core install + site activation
- `deploy.yml` - pull + migrate + build + restart (Phase 7b Sprint 1 candidate)
- `rollback.yml` - restore-from-backup + git revert + smoke (Phase 7b Task B candidate)

## Per-Environment Differences (Gotcha 1 / VM Inventory)

| Env | bench_user | bench_path | site | branch | mode |
|---|---|---|---|---|---|
| dev | frappe | /home/frappe/frappe-bench | erp.local | dev | dev |
| staging | erpadmin | /home/erpadmin/frappe-bench | erp.staging | staging | production |
| production | erpadmin | /home/erpadmin/frappe-bench | erp.production | production | production |

Playbooks reference `{{ bench_user }}`, `{{ bench_path }}`, `{{ site_name }}` exclusively. **Never hardcode** environment-specific values in tasks.

## Testing

```
cd tools/infrabeat_erp
python -m pytest tests/test_ansible_inventory.py -v
```

Verifies inventory parses, host vars match `04_VM_INVENTORY.md`, playbooks parse, Node 18.x enforced (Gotcha 5), ed25519 key referenced.
