from __future__ import annotations

import json
import sys
from pathlib import Path

from typer.testing import CliRunner

from devctl_core.cli import app
from devctl_core.info import collect_info

runner = CliRunner()


def test_collect_info_minimal() -> None:
    info = collect_info()
    assert "core_version" in info
    assert "python_version" in info
    assert info["python_version"] == sys.version.split()[0]
    assert "platform" in info
    assert isinstance(info["providers"], list)
    assert "native" in info["providers"]


def test_collect_info_with_config_dir(tmp_path: Path) -> None:
    info = collect_info(config_dir=tmp_path / ".devctl")
    assert "config_dir" in info
    assert info["config_exists"] is False
    assert str(info["config_path"]).endswith("config.yaml")


def test_collect_info_with_existing_config(tmp_path: Path) -> None:
    cfg_dir = tmp_path / ".devctl"
    cfg_dir.mkdir()
    info = collect_info(config_dir=cfg_dir)
    assert info["config_exists"] is True


def test_cli_info_text() -> None:
    result = runner.invoke(app, ["info"])
    assert result.exit_code == 0, result.output
    assert "core_version:" in result.output
    assert "providers:" in result.output
    assert "native" in result.output


def test_cli_info_json() -> None:
    result = runner.invoke(app, ["info", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert "core_version" in payload
    assert "native" in payload["providers"]


def test_cli_info_with_config_dir(tmp_path: Path) -> None:
    result = runner.invoke(app, ["info", "--config-dir", str(tmp_path / ".devctl"), "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert "config_dir" in payload
    assert payload["config_exists"] is False
