"""Tests for infrabeat_erp.http and infrabeat_erp.config (Phase 6B.1)."""

from pathlib import Path

import pytest

from infrabeat_erp.infrastructure.config import VMConfig, get_vm, load_config
from infrabeat_erp.infrastructure.http import make_client


TOML_FIXTURE = """\
[vm.dev]
base_url = "http://10.1.0.184"

[vm.staging]
base_url = "http://10.1.0.185"
"""


def test_make_client_no_token() -> None:
    client = make_client("http://example.test")
    assert client.headers["User-Agent"] == "infrabeat-erp/0.1.0"
    assert client.headers["Accept"] == "application/json"
    assert client.headers["Content-Type"] == "application/json"
    assert "Authorization" not in client.headers


def test_make_client_with_token() -> None:
    client = make_client("http://example.test", access_token="test-token-123")
    assert client.headers["Authorization"] == "Bearer test-token-123"


def test_make_client_uses_base_url() -> None:
    client = make_client("http://example.test")
    assert str(client.base_url).startswith("http://example.test")


def test_make_client_uses_timeout() -> None:
    client = make_client("http://example.test", timeout=5.0)
    assert client.timeout.connect == 5.0


def _write_toml(tmp_path: Path) -> Path:
    cfg = tmp_path / "config.toml"
    cfg.write_text(TOML_FIXTURE, encoding="utf-8")
    return cfg


def test_load_config_reads_toml(tmp_path: Path) -> None:
    cfg = _write_toml(tmp_path)
    vms = load_config(cfg)
    assert vms["dev"].base_url == "http://10.1.0.184"
    assert vms["staging"].base_url == "http://10.1.0.185"


def test_get_vm_returns_correct(tmp_path: Path) -> None:
    cfg = _write_toml(tmp_path)
    vm = get_vm("dev", cfg)
    assert vm == VMConfig(name="dev", base_url="http://10.1.0.184")


def test_get_vm_raises_on_missing(tmp_path: Path) -> None:
    cfg = _write_toml(tmp_path)
    with pytest.raises(KeyError) as exc:
        get_vm("nope", cfg)
    assert "unknown VM alias" in str(exc.value)


def test_load_config_raises_file_not_found(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist.toml"
    with pytest.raises(FileNotFoundError) as exc:
        load_config(missing)
    assert str(missing) in str(exc.value)
