"""Keyring-backed secrets persistence for infrabeat-erp.

Phase 6C.1 promotes secrets storage from CWD-relative plaintext JSON to
an OS keyring (Windows Credential Manager / macOS Keychain / Linux
Secret Service) with a Fernet-encrypted JSON file fallback for headless
or CI environments. The legacy plaintext layout from Phase 5 / 6B.4a is
read-only here: ``load_secrets`` falls through to it as a last resort,
and the ``migrate`` helper (driven by the ``infrabeat-erp
migrate-secrets`` subcommand) moves a plaintext file into the new
backend and renames the original to ``<vm>.json.migrated`` for a
forensic trail.

The public API (save_secrets, load_secrets, SecretsStoreError,
SecretsNotFound) keeps its 6B.4a signatures so the existing
register/login/smoke subcommands need no changes.
"""

import base64
import json
import os
import secrets as _stdlib_secrets
from pathlib import Path

import keyring
import keyring.errors
from cryptography.fernet import Fernet, InvalidToken

SECRETS_DIRNAME = ".secrets"
SECRETS_DIR_MODE = 0o700
SECRETS_FILE_MODE = 0o600

KEYRING_SERVICE = "infrabeat-erp"
MASTER_KEY_USER = "__master__"
MASTER_KEY_ENV = "INFRABEAT_MASTER_KEY"
MASTER_KEY_FILE = Path.home() / ".config" / "infrabeat-erp" / "master.key"


# === Exceptions ===========================================================
class SecretsStoreError(Exception):
    """Base for secrets store failures (I/O, parse, permission errors)."""


class SecretsNotFound(SecretsStoreError):
    """Requested VM has no secrets entry (register or login required first)."""


class SecretsBackendUnavailable(Exception):
    """No keyring backend AND no writable master key fallback location.

    Distinct from SecretsStoreError so the CLI's top-level handler can
    surface a backend-setup hint rather than a per-VM I/O message.
    """


# === Private helpers ======================================================
def _secrets_dir(base_dir: Path | None) -> Path:
    """Resolve the .secrets directory under base_dir (defaults to cwd)."""
    root = base_dir if base_dir is not None else Path.cwd()
    return root / SECRETS_DIRNAME


def _ensure_secrets_dir(base_dir: Path | None) -> Path:
    directory = _secrets_dir(base_dir)
    directory.mkdir(parents=True, exist_ok=True)
    if os.name != "nt":
        os.chmod(directory, SECRETS_DIR_MODE)
    return directory


# === Public API ===========================================================
def save_secrets(
    vm_alias: str,
    data: dict,
    base_dir: Path | None = None,
) -> Path | None:
    """Persist secrets for a VM alias to the primary backend.

    Try keyring first; if the backend is unavailable, fall through to a
    Fernet-encrypted JSON file at ``<base_dir>/.secrets/<vm>.json.enc``.
    Never writes the legacy plaintext file. Returns the encrypted file
    Path when the file fallback was used, or None when the value was
    stored in the keyring.

    Args:
        vm_alias: VM alias used as the keyring username / file stem.
        data: JSON-serializable mapping of secrets to persist.
        base_dir: Directory under which .secrets lives for the file
            fallback. Defaults to Path.cwd().

    Returns:
        The absolute Path of the encrypted file when written, else None.

    Raises:
        SecretsStoreError: On serialization or I/O failure.
        SecretsBackendUnavailable: If neither keyring nor a writable
            master key location is available.
    """
    if _try_keyring_save(vm_alias, data):
        return None
    _try_encrypted_save(vm_alias, data, base_dir)
    return _secrets_dir(base_dir) / f"{vm_alias}.json.enc"


def load_secrets(
    vm_alias: str,
    base_dir: Path | None = None,
) -> dict:
    """Load secrets for a VM alias from the first backend that has them.

    Tries in order:
        a) keyring (primary)
        b) Fernet-encrypted JSON at <base_dir>/.secrets/<vm>.json.enc
        c) Legacy plaintext JSON at <base_dir>/.secrets/<vm>.json

    Args:
        vm_alias: VM alias whose entry should be read.
        base_dir: Directory under which .secrets lives for the file
            backends. Defaults to Path.cwd().

    Returns:
        The parsed secrets dict.

    Raises:
        SecretsNotFound: If no backend has an entry for this alias.
        SecretsStoreError: On parse or I/O failure in a backend that
            otherwise had data.
    """
    via_keyring = _try_keyring_load(vm_alias)
    if via_keyring is not None:
        return via_keyring

    via_encrypted = _try_encrypted_load(vm_alias, base_dir)
    if via_encrypted is not None:
        return via_encrypted

    via_legacy = _try_legacy_load(vm_alias, base_dir)
    if via_legacy is not None:
        return via_legacy

    raise SecretsNotFound(
        f"no secrets for {vm_alias}; run register first"
    )


# === Phase 6C.1 KEYRING PROMOTION =========================================
# Adds the keyring backend, Fernet-encrypted JSON fallback, plaintext
# legacy reader, and the migrate() helper that moves a Phase-5/6B
# plaintext file into the new primary backend. save_secrets / load_secrets
# above dispatch into the helpers below; everything in this block is new
# in 6C.1 and additive.

def _try_keyring_load(vm_alias: str) -> dict | None:
    """Read JSON-encoded secrets from the keyring; None if absent/unavailable."""
    try:
        raw = keyring.get_password(KEYRING_SERVICE, vm_alias)
    except keyring.errors.KeyringError:
        return None
    except Exception:
        return None
    if raw is None:
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SecretsStoreError(
            f"failed to parse keyring entry for {vm_alias}: {exc}"
        ) from exc
    if not isinstance(parsed, dict):
        raise SecretsStoreError(
            f"keyring entry for {vm_alias} is not a JSON object"
        )
    return parsed


def _try_keyring_save(vm_alias: str, data: dict) -> bool:
    """Try to persist via keyring; return False on backend unavailability."""
    try:
        payload = json.dumps(data, sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise SecretsStoreError(
            f"failed to serialize secrets for {vm_alias}: {exc}"
        ) from exc
    try:
        keyring.set_password(KEYRING_SERVICE, vm_alias, payload)
        return True
    except keyring.errors.KeyringError:
        return False
    except Exception:
        return False


def _resolve_master_key() -> bytes:
    """Return the Fernet master key, generating + persisting if needed.

    Resolution order:
        1. INFRABEAT_MASTER_KEY env var (overrides everything; used by
           tests and by users on locked-down systems).
        2. keyring entry service='infrabeat-erp', username='__master__'.
        3. ~/.config/infrabeat-erp/master.key file (mode 0o600 on POSIX).
        4. Generate 32 random bytes (base64-urlsafe encoded), store in
           keyring; if keyring fails, write to the master key file; if
           both fail, raise SecretsBackendUnavailable.
    """
    env_value = os.environ.get(MASTER_KEY_ENV)
    if env_value:
        return env_value.encode("ascii")

    try:
        from_keyring = keyring.get_password(KEYRING_SERVICE, MASTER_KEY_USER)
    except Exception:
        from_keyring = None
    if from_keyring:
        return from_keyring.encode("ascii")

    try:
        if MASTER_KEY_FILE.exists():
            return (
                MASTER_KEY_FILE.read_text(encoding="ascii").strip().encode("ascii")
            )
    except OSError:
        pass

    new_key = base64.urlsafe_b64encode(_stdlib_secrets.token_bytes(32))
    new_key_str = new_key.decode("ascii")

    try:
        keyring.set_password(KEYRING_SERVICE, MASTER_KEY_USER, new_key_str)
        return new_key
    except Exception:
        pass

    try:
        MASTER_KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
        if os.name != "nt":
            os.chmod(MASTER_KEY_FILE.parent, SECRETS_DIR_MODE)
        MASTER_KEY_FILE.write_text(new_key_str, encoding="ascii")
        if os.name != "nt":
            os.chmod(MASTER_KEY_FILE, SECRETS_FILE_MODE)
        return new_key
    except OSError as exc:
        raise SecretsBackendUnavailable(
            "no keyring backend and master key file unwritable; "
            f"set {MASTER_KEY_ENV} env var to a Fernet key. underlying: {exc}"
        ) from exc


def _encrypt_json(secrets_dict: dict, master_key: bytes) -> bytes:
    payload = json.dumps(secrets_dict, sort_keys=True).encode("utf-8")
    return Fernet(master_key).encrypt(payload)


def _decrypt_json(blob: bytes, master_key: bytes) -> dict:
    try:
        plain = Fernet(master_key).decrypt(blob)
    except InvalidToken as exc:
        raise SecretsStoreError(
            f"failed to decrypt secrets (wrong master key?): {exc}"
        ) from exc
    parsed = json.loads(plain.decode("utf-8"))
    if not isinstance(parsed, dict):
        raise SecretsStoreError(
            "decrypted secrets payload is not a JSON object"
        )
    return parsed


def _try_encrypted_load(
    vm_alias: str,
    base_dir: Path | None,
) -> dict | None:
    target = _secrets_dir(base_dir) / f"{vm_alias}.json.enc"
    if not target.exists():
        return None
    try:
        blob = target.read_bytes()
    except OSError as exc:
        raise SecretsStoreError(
            f"failed to read encrypted secrets for {vm_alias}: {exc}"
        ) from exc
    return _decrypt_json(blob, _resolve_master_key())


def _try_encrypted_save(
    vm_alias: str,
    data: dict,
    base_dir: Path | None,
) -> bool:
    directory = _ensure_secrets_dir(base_dir)
    target = directory / f"{vm_alias}.json.enc"
    tmp_path = directory / f"{vm_alias}.json.enc.tmp"
    blob = _encrypt_json(data, _resolve_master_key())

    try:
        fd = os.open(
            tmp_path,
            os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
            SECRETS_FILE_MODE,
        )
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(blob)
                fh.flush()
                os.fsync(fh.fileno())
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

        os.replace(tmp_path, target)
        os.chmod(target, SECRETS_FILE_MODE)
    except OSError as exc:
        raise SecretsStoreError(
            f"failed to save encrypted secrets for {vm_alias}: {exc}"
        ) from exc
    return True


def _try_legacy_load(
    vm_alias: str,
    base_dir: Path | None,
) -> dict | None:
    """Read pre-6C.1 plaintext JSON. Read-only; never writes."""
    target = _secrets_dir(base_dir) / f"{vm_alias}.json"
    if not target.exists():
        return None
    try:
        raw = target.read_text(encoding="utf-8")
    except OSError as exc:
        raise SecretsStoreError(
            f"failed to read legacy secrets for {vm_alias}: {exc}"
        ) from exc
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SecretsStoreError(
            f"failed to parse legacy secrets for {vm_alias}: {exc}"
        ) from exc
    if not isinstance(parsed, dict):
        raise SecretsStoreError(
            f"legacy secrets file for {vm_alias} is not a JSON object"
        )
    return parsed


def is_migrated(vm_alias: str, base_dir: Path | None = None) -> bool:
    """Return True if the legacy plaintext file has the .migrated suffix."""
    return (_secrets_dir(base_dir) / f"{vm_alias}.json.migrated").exists()


def migrate(vm_alias: str, base_dir: Path | None = None) -> str:
    """Move legacy plaintext secrets into the keyring-primary backend.

    Returns one of:
        - 'migrated': legacy plaintext found, persisted via save_secrets,
          and renamed to <vm>.json.migrated.
        - 'already-migrated': a <vm>.json.migrated marker exists.
        - 'no-source': neither legacy nor migrated marker present.

    Idempotent: a second call after success returns 'already-migrated'.
    Does NOT delete the .migrated file; the user is expected to remove
    it manually after verifying the new backend works.
    """
    directory = _secrets_dir(base_dir)
    legacy = directory / f"{vm_alias}.json"
    migrated_marker = directory / f"{vm_alias}.json.migrated"

    if migrated_marker.exists():
        return "already-migrated"
    if not legacy.exists():
        return "no-source"

    try:
        raw = legacy.read_text(encoding="utf-8")
    except OSError as exc:
        raise SecretsStoreError(
            f"failed to read legacy secrets for {vm_alias}: {exc}"
        ) from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SecretsStoreError(
            f"failed to parse legacy secrets for {vm_alias}: {exc}"
        ) from exc
    if not isinstance(data, dict):
        raise SecretsStoreError(
            f"legacy secrets file for {vm_alias} is not a JSON object"
        )

    save_secrets(vm_alias, data, base_dir=base_dir)

    try:
        os.replace(legacy, migrated_marker)
    except OSError as exc:
        raise SecretsStoreError(
            f"failed to rename legacy secrets file for {vm_alias}: {exc}"
        ) from exc
    return "migrated"
