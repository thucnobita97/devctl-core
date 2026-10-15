from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from devctl_core.cli import app

runner = CliRunner()


def test_info_text() -> None:
    result = runner.invoke(app, ["info"])
    assert result.exit_code == 0
    assert "core_version:" in result.output
    assert "python_version:" in result.output
    assert "providers:" in result.output
    assert "native" in result.output
    assert "docker-compose" in result.output


def test_info_json() -> None:
    result = runner.invoke(app, ["info", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert "core_version" in payload
    assert "python_version" in payload
    assert "platform" in payload
    assert isinstance(payload["providers"], list)
    for expected in (
        "native",
        "docker-compose",
        "systemd",
        "external",
        "docker-external",
    ):
        assert expected in payload["providers"]


def test_info_json_with_config_dir(tmp_path: Path) -> None:
    cfg_dir = tmp_path / ".devctl"
    cfg_dir.mkdir()
    result = runner.invoke(
        app, ["info", "--json", "--config-dir", str(cfg_dir)]
    )
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["config_dir"] == str(cfg_dir)
    assert payload["config_exists"] is True


def test_info_json_config_dir_missing(tmp_path: Path) -> None:
    cfg_dir = tmp_path / "nope"
    result = runner.invoke(
        app, ["info", "--json", "--config-dir", str(cfg_dir)]
    )
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["config_exists"] is False
