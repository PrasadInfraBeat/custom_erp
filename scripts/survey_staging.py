"""Phase 7a Sprint 0 Task (A) v2: comprehensive staging VM survey.

Narrow recon at /home/erpadmin/custom_erp/infra/ansible/ returned
'No such file or directory'. This survey broadens system-wide to locate:
  1. Ansible binaries + artifacts (any path)
  2. custom_erp repo actual location
  3. infra/ directory (if it exists anywhere)
  4. frappe-bench state and custom_erp app state
  5. Runtime versions for Sprint 0 baseline

One SSH session, single paramiko connection, byte-perfect output for
H3 decision (shell-over-SSH vs Ansible) plus Task (B) layout planning
plus Task (D) doctor check scoping.
"""
from __future__ import annotations

import sys

import keyring
import paramiko

VM_HOST = "10.1.0.185"
VM_USER = "erpadmin"
KEYRING_SERVICE = "infrabeat-vm-creds"
KEYRING_USERNAME = "staging-ssh-password"

SURVEY_CMD = r"""
echo "########## 1. ANSIBLE BINARIES ##########"
echo "ansible: $(which ansible 2>&1)"
echo "ansible-playbook: $(which ansible-playbook 2>&1)"
ansible --version 2>&1 | head -3
echo

echo "########## 2. custom_erp REPO CLONES (broad search) ##########"
find /home /opt /srv -maxdepth 5 -type d -name "custom_erp" 2>/dev/null
echo

echo "########## 3. infra DIRECTORIES (broad search) ##########"
find /home /opt /srv -maxdepth 6 -type d -name "infra" 2>/dev/null
echo

echo "########## 4. DIRECTORIES NAMED 'ansible' (excluding python libs) ##########"
find /home /opt /srv /etc /usr/local -maxdepth 6 -type d -name "ansible" 2>/dev/null | grep -v 'site-packages\|\.cache\|node_modules\|/python' | head -20
echo

echo "########## 5. ansible.cfg FILES SYSTEM-WIDE ##########"
find /home /opt /srv /etc /usr/local -type f -name "ansible.cfg" 2>/dev/null | head -10
echo

echo "########## 6. PLAYBOOK-LIKE YML FILES ##########"
find /home /opt /srv -maxdepth 6 -type f \( -name "playbook*.yml" -o -name "site.yml" -o -name "hosts.yml" -o -name "inventory.yml" -o -name "main.yml" \) 2>/dev/null | head -30
echo

echo "########## 7. /home/erpadmin TOP-LEVEL ##########"
ls -la /home/erpadmin/ 2>&1
echo

echo "########## 8. FRAPPE-BENCH APPS LIST ##########"
ls /home/erpadmin/frappe-bench/apps/ 2>&1
echo

echo "########## 9. custom_erp APP STATE (inside frappe-bench) ##########"
if [ -d /home/erpadmin/frappe-bench/apps/custom_erp ]; then
  cd /home/erpadmin/frappe-bench/apps/custom_erp
  echo "--- top-level contents ---"
  ls -la
  echo "--- git remote ---"
  git remote -v 2>&1
  echo "--- current branch & commit ---"
  echo "branch: $(git branch --show-current 2>&1)"
  echo "commit: $(git rev-parse --short HEAD 2>&1)"
  echo "--- infra/ inside this app? ---"
  ls -la infra/ 2>&1 | head -10
else
  echo "(custom_erp NOT at /home/erpadmin/frappe-bench/apps/custom_erp)"
fi
echo

echo "########## 10. RUNTIME VERSIONS ##########"
echo "Python: $(python3 --version 2>&1)"
echo "Node: $(node --version 2>&1)"
if [ -x /home/erpadmin/frappe-bench/env/bin/bench ]; then
  /home/erpadmin/frappe-bench/env/bin/bench --version 2>&1 | head -2
else
  echo "bench: $(which bench 2>&1)"
fi
echo

echo "########## SURVEY COMPLETE ##########"
"""


def main() -> int:
    pw = keyring.get_password(KEYRING_SERVICE, KEYRING_USERNAME)
    if not pw:
        print(f"FATAL: no credential in keyring {KEYRING_SERVICE}/{KEYRING_USERNAME}", file=sys.stderr)
        return 2
    print(f"# Connecting to {VM_USER}@{VM_HOST} via paramiko (pw len={len(pw)}) ...", file=sys.stderr)
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(VM_HOST, username=VM_USER, password=pw, timeout=15)
    except paramiko.AuthenticationException:
        print("FATAL: SSH auth rejected.", file=sys.stderr)
        return 3
    except Exception as exc:
        print(f"FATAL: SSH connect failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 4
    print("# Connected. Running comprehensive survey (30-60s, find traverses /home /opt /srv /etc /usr/local) ...", file=sys.stderr)
    _, stdout, stderr = client.exec_command(SURVEY_CMD, timeout=180)
    sys.stdout.write(stdout.read().decode("utf-8", errors="replace"))
    err = stderr.read().decode("utf-8", errors="replace")
    if err.strip():
        sys.stderr.write("--- REMOTE STDERR ---\n")
        sys.stderr.write(err)
    client.close()
    print("# Done.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
