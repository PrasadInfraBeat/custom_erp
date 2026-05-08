"""Filesystem-backed secrets persistence for infrabeat-erp.

Transitional storage layer for OAuth client registrations and tokens. The
Phase 5 scripts wrote a JSON file per VM alias under <cwd>/.secrets/, and
6B.4b's CLI subcommands (register / login / refresh) need the same on-disk
contract while the package matures. This module preserves that layout so
existing dev / staging artifacts remain readable.

Phase 6C will replace the implementation with an OS keyring backend plus a
Fernet-encrypted file fallback. The public API (save_secrets, load_secrets,
SecretsStoreError, SecretsNotFound) MUST remain stable across that swap so
the CLI subcommands in 6B.4b need no changes when 6C lands.

Stdlib only: JSON for serialization, os.replace for atomicity, os.chmod
for POSIX 0o600 permissions (no-op semantics on Windows).
"""

import json
import os
from pathlib import Path

SECRETS_DIRNAME = ".secrets"
SECRETS_DIR_MODE = 0o700
SECRETS_FILE_MODE = 0o600


# === Exceptions ===========================================================
class SecretsStoreError(Exception):
    """Base for secrets store failures (I/O, parse, permission errors)."""


class SecretsNotFound(SecretsStoreError):
    """Requested VM has no secrets file (register or login required first)."""


# === Private helpers ======================================================
def _secrets_dir(base_dir: Path | None) -> Path:
    """Resolve the .secrets directory under base_dir (defaults to cwd)."""
    root = base_dir if base_dir is not None else Path.cwd()
    return root / SECRETS_DIRNAME


# === Public API ===========================================================
def save_secrets(
    vm_alias: str,
    data: dict,
    base_dir: Path | None = None,
) -> Path:
    """Persist secrets for a VM alias to base_dir/.secrets/<vm_alias>.json.

    Creates the .secrets directory with mode 0o700 if missing. Serializes
    data to JSON and writes atomically via a same-directory tempfile that
    is flushed, fsynced, then os.replace()d onto the target path. The
    final file mode is set to 0o600 (POSIX); os.chmod is a harmless no-op
    on Windows.

    Args:
        vm_alias: VM alias used as the JSON filename stem (e.g. "dev").
        data: JSON-serializable mapping of secrets to persist.
        base_dir: Directory under which .secrets lives. Defaults to
            Path.cwd() to match the Phase 5 layout.

    Returns:
        The absolute Path of the written secrets file.

    Raises:
        SecretsStoreError: On any I/O, encoding, or permission failure;
            the underlying exception is chained via "from".
    """
    directory = _secrets_dir(base_dir)
    target = directory / f"{vm_alias}.json"
    tmp_path = directory / f"{vm_alias}.json.tmp"

    try:
        directory.mkdir(parents=True, exist_ok=True)
        if os.name != "nt":
            os.chmod(directory, SECRETS_DIR_MODE)

        payload = json.dumps(data, indent=2, sort_keys=True)
        fd = os.open(
            tmp_path,
            os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
            SECRETS_FILE_MODE,
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(payload)
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
            f"failed to save secrets for {vm_alias}: {exc}"
        ) from exc
    except (TypeError, ValueError) as exc:
        raise SecretsStoreError(
            f"failed to serialize secrets for {vm_alias}: {exc}"
        ) from exc

    return target


def load_secrets(
    vm_alias: str,
    base_dir: Path | None = None,
) -> dict:
    """Load secrets for a VM alias from base_dir/.secrets/<vm_alias>.json.

    Args:
        vm_alias: VM alias whose JSON file should be read.
        base_dir: Directory under which .secrets lives. Defaults to
            Path.cwd() to match the Phase 5 layout.

    Returns:
        The parsed JSON object as a dict.

    Raises:
        SecretsNotFound: If the secrets file does not exist; the message
            tells the user to run register first.
        SecretsStoreError: On any I/O or JSON parse failure; the
            underlying exception is chained via "from".
    """
    target = _secrets_dir(base_dir) / f"{vm_alias}.json"
    if not target.exists():
        raise SecretsNotFound(
            f"no secrets for {vm_alias}; run register first"
        )

    try:
        raw = target.read_text(encoding="utf-8")
    except OSError as exc:
        raise SecretsStoreError(
            f"failed to read secrets for {vm_alias}: {exc}"
        ) from exc

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SecretsStoreError(
            f"failed to parse secrets for {vm_alias}: {exc}"
        ) from exc
