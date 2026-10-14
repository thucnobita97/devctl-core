from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from devctl_core.cli import app
from devctl_core.init import init_devctl

runner = CliRunner()


def test_init_creates_skeleton(tmp_path: Path) -> None:
    result = init_devctl(tmp_path)
    assert (tmp_path / ".devctl" / "config.yaml").exists()
    assert (tmp_path / ".devctl" / "session.yaml").exists()
    assert (tmp_path / ".devctl" / "services").is_dir()
    assert (tmp_path / ".devctl" / "hooks").is_dir()
    assert (tmp_path / ".devctl" / "templates").is_dir()
    assert len(result.created) > 0
    assert len(result.skipped) == 0


def test_init_idempotent_skips_existing(tmp_path: Path) -> None:
    init_devctl(tmp_path)
    cfg = tmp_path / ".devctl" / "config.yaml"
    cfg.write_text("CUSTOM\n", encoding="utf-8")

    result = init_devctl(tmp_path)
    assert cfg in result.skipped
    assert cfg.read_text(encoding="utf-8") == "CUSTOM\n"


def test_init_force_overwrites(tmp_path: Path) -> None:
    init_devctl(tmp_path)
    cfg = tmp_path / ".devctl" / "config.yaml"
    cfg.write_text("CUSTOM\n", encoding="utf-8")

    init_devctl(tmp_path, force=True)
    assert cfg.read_text(encoding="utf-8") != "CUSTOM\n"
    assert "version: 1" in cfg.read_text(encoding="utf-8")


def test_cli_init_ok(tmp_path: Path) -> None:
    result = runner.invoke(app, ["init", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert (tmp_path / ".devctl" / "config.yaml").exists()
    assert "created:" in result.output
    assert "0 skipped" in result.output or "skipped" in result.output


def test_cli_init_skip(tmp_path: Path) -> None:
    runner.invoke(app, ["init", str(tmp_path)])
    result = runner.invoke(app, ["init", str(tmp_path)])
    assert result.exit_code == 0
    assert "skipped:" in result.output


def test_cli_init_force(tmp_path: Path) -> None:
    runner.invoke(app, ["init", str(tmp_path)])
    cfg = tmp_path / ".devctl" / "config.yaml"
    cfg.write_text("custom\n", encoding="utf-8")

    runner.invoke(app, ["init", str(tmp_path), "--force"])
    assert "version: 1" in cfg.read_text(encoding="utf-8")


def test_cli_init_then_validate_services_empty(tmp_path: Path) -> None:
    runner.invoke(app, ["init", str(tmp_path)])
    result = runner.invoke(app, ["validate", "--config-dir", str(tmp_path / ".devctl")])
    assert result.exit_code == 12
    assert "MAN_003" in result.output
