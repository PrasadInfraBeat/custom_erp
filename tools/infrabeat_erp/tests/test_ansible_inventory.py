"""Phase 7b Sprint 0 Task A - Ansible inventory + playbook structural tests.

Verifies:
- infra/ansible/ tree exists at expected paths
- 3 inventory files parse as YAML and host vars match 04_VM_INVENTORY.md
- 3 playbooks parse as YAML with at least one play and one task
- bench_user differs correctly (dev=frappe, staging/production=erpadmin)
- All inventories reference ed25519 SSH key
- ansible.cfg present and parses as INI
- bootstrap.yml enforces Node 18.x (Gotcha 5)
"""
from __future__ import annotations

import configparser
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
ANSIBLE_DIR = REPO_ROOT / "infra" / "ansible"
INVENTORY_DIR = ANSIBLE_DIR / "inventory"
PLAYBOOKS_DIR = ANSIBLE_DIR / "playbooks"

EXPECTED_VMS = {
    "dev": {
        "ansible_host": "10.1.0.184",
        "ansible_user": "erpadmin",
        "bench_user": "frappe",
        "bench_path": "/home/frappe/frappe-bench",
        "site_name": "erp.local",
        "branch_name": "dev",
        "bench_mode": "dev",
    },
    "staging": {
        "ansible_host": "10.1.0.185",
        "ansible_user": "erpadmin",
        "bench_user": "erpadmin",
        "bench_path": "/home/erpadmin/frappe-bench",
        "site_name": "erp.staging",
        "branch_name": "staging",
        "bench_mode": "production",
    },
    "production": {
        "ansible_host": "10.1.0.186",
        "ansible_user": "erpadmin",
        "bench_user": "erpadmin",
        "bench_path": "/home/erpadmin/frappe-bench",
        "site_name": "erp.production",
        "branch_name": "production",
        "bench_mode": "production",
    },
}


def test_ansible_dir_exists() -> None:
    assert ANSIBLE_DIR.is_dir(), f"missing {ANSIBLE_DIR}"
    assert INVENTORY_DIR.is_dir(), f"missing {INVENTORY_DIR}"
    assert PLAYBOOKS_DIR.is_dir(), f"missing {PLAYBOOKS_DIR}"


def test_ansible_cfg_present_and_parses() -> None:
    cfg_path = ANSIBLE_DIR / "ansible.cfg"
    assert cfg_path.is_file(), f"missing {cfg_path}"
    parser = configparser.ConfigParser()
    parser.read(cfg_path)
    assert parser.has_section("defaults")
    assert parser.has_section("ssh_connection")


@pytest.mark.parametrize("env", ["dev", "staging", "production"])
def test_inventory_file_parses(env: str) -> None:
    inv_path = INVENTORY_DIR / f"{env}.yml"
    assert inv_path.is_file(), f"missing {inv_path}"
    data = yaml.safe_load(inv_path.read_text(encoding="utf-8"))
    assert "all" in data
    assert "hosts" in data["all"]
    assert env in data["all"]["hosts"]


@pytest.mark.parametrize("env", ["dev", "staging", "production"])
def test_inventory_host_matches_vm_inventory(env: str) -> None:
    inv_path = INVENTORY_DIR / f"{env}.yml"
    data = yaml.safe_load(inv_path.read_text(encoding="utf-8"))
    host_vars = data["all"]["hosts"][env]
    expected = EXPECTED_VMS[env]
    for key, value in expected.items():
        assert host_vars.get(key) == value, (
            f"{env}.yml host var {key!r} mismatch: "
            f"got {host_vars.get(key)!r}, expected {value!r}"
        )


def test_bench_user_differs_dev_vs_staging() -> None:
    """Gotcha 1: dev uses frappe user, staging/production use erpadmin."""
    dev_data = yaml.safe_load((INVENTORY_DIR / "dev.yml").read_text(encoding="utf-8"))
    staging_data = yaml.safe_load((INVENTORY_DIR / "staging.yml").read_text(encoding="utf-8"))
    production_data = yaml.safe_load((INVENTORY_DIR / "production.yml").read_text(encoding="utf-8"))
    assert dev_data["all"]["hosts"]["dev"]["bench_user"] == "frappe"
    assert staging_data["all"]["hosts"]["staging"]["bench_user"] == "erpadmin"
    assert production_data["all"]["hosts"]["production"]["bench_user"] == "erpadmin"


@pytest.mark.parametrize("env", ["dev", "staging", "production"])
def test_inventory_uses_ed25519_key(env: str) -> None:
    data = yaml.safe_load((INVENTORY_DIR / f"{env}.yml").read_text(encoding="utf-8"))
    key_path = data["all"]["vars"]["ansible_ssh_private_key_file"]
    assert "infrabeat_ed25519" in key_path


@pytest.mark.parametrize("playbook", ["preflight.yml", "ssh_keys.yml", "bootstrap.yml"])
def test_playbook_parses_as_yaml(playbook: str) -> None:
    pb_path = PLAYBOOKS_DIR / playbook
    assert pb_path.is_file(), f"missing {pb_path}"
    data = yaml.safe_load(pb_path.read_text(encoding="utf-8"))
    assert isinstance(data, list), f"{playbook} top-level must be a list of plays"
    assert len(data) >= 1
    play = data[0]
    assert "hosts" in play
    assert "tasks" in play
    assert isinstance(play["tasks"], list)
    assert len(play["tasks"]) >= 1


def test_bootstrap_playbook_enforces_node18() -> None:
    """Gotcha 5: Node 18.x is mandatory for Frappe v15 (never 20+)."""
    pb_text = (PLAYBOOKS_DIR / "bootstrap.yml").read_text(encoding="utf-8")
    assert "setup_18.x" in pb_text, "bootstrap.yml missing NodeSource 18.x setup"
    assert "v18" in pb_text, "bootstrap.yml missing v18 version check"


def test_ssh_keys_playbook_uses_authorized_key_module() -> None:
    pb_text = (PLAYBOOKS_DIR / "ssh_keys.yml").read_text(encoding="utf-8")
    assert "ansible.posix.authorized_key" in pb_text


def test_bootstrap_detects_fac_app() -> None:
    pb_text = (PLAYBOOKS_DIR / "bootstrap.yml").read_text(encoding="utf-8")
    assert "frappe_assistant_core" in pb_text


def test_readme_present_with_required_sections() -> None:
    readme = ANSIBLE_DIR / "README.md"
    assert readme.is_file()
    text = readme.read_text(encoding="utf-8")
    assert "Phase 7b Sprint 0" in text
    assert "preflight.yml" in text
    assert "bootstrap.yml" in text
    assert "ssh_keys.yml" in text
    assert "Gotcha" in text
