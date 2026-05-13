"""TOML config loader for infrabeat-erp VM aliases.

Resolves friendly aliases (dev, staging, production) to base URLs from a
TOML file at ~/.config/infrabeat-erp/config.toml. Stdlib only; tomllib
ships with Python 3.11+ (target is 3.12).
"""

import tomllib
from dataclasses import dataclass
from pathlib import Path

DEFAULT_CONFIG_PATH = Path.home() / ".config" / "infrabeat-erp" / "config.toml"


@dataclass(frozen=True)
class VMConfig:
    """Resolved configuration for a single VM alias."""

    name: str
    base_url: str


def load_config(path: Path | None = None) -> dict[str, VMConfig]:
    """Load VM aliases from a TOML config file.

    Reads a file structured as `[vm.<alias>]` tables, each with a
    `base_url` key, and returns a dict mapping alias to VMConfig.

    Args:
        path: Optional path to the TOML file. Defaults to
            DEFAULT_CONFIG_PATH (~/.config/infrabeat-erp/config.toml).

    Returns:
        Mapping of alias name to VMConfig.

    Raises:
        FileNotFoundError: If the config file does not exist. The message
            includes the resolved path.
    """
    resolved = path if path is not None else DEFAULT_CONFIG_PATH
    if not resolved.exists():
        raise FileNotFoundError(
            f"infrabeat-erp config not found at {resolved}"
        )

    with resolved.open("rb") as fh:
        data = tomllib.load(fh)

    vms: dict[str, VMConfig] = {}
    for alias, entry in data.get("vm", {}).items():
        vms[alias] = VMConfig(name=alias, base_url=entry["base_url"])
    return vms


def get_vm(name: str, path: Path | None = None) -> VMConfig:
    """Look up a single VM alias.

    Args:
        name: Alias to look up (e.g. "dev", "staging", "production").
        path: Optional path to the TOML file. Defaults to
            DEFAULT_CONFIG_PATH.

    Returns:
        The matching VMConfig.

    Raises:
        KeyError: If the alias is not present in the config. The message
            lists the known aliases.
    """
    vms = load_config(path)
    if name not in vms:
        known = ", ".join(sorted(vms)) if vms else "(none)"
        raise KeyError(f"unknown VM alias: {name}; known: {known}")
    return vms[name]
