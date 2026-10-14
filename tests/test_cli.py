from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from devctl_core.cli import app

runner = CliRunner()


def _write_minimal_devctl(root: Path, *, version: int = 1) -> Path:
    cfg_dir = root / ".devctl"
    (cfg_dir / "services").mkdir(parents=True)
    (cfg_dir / "hooks").mkdir()
    (cfg_dir / "config.yaml").write_text(
        f"version: {version}\nproject:\n  name: demo\npaths:\n  hooks: .devctl/hooks\n"
    )
    (cfg_dir / "services" / "postgres.yaml").write_text(
        "name: postgres\nprovider: docker-compose\nservice: postgres\n"
    )
    return cfg_dir


def test_cli_validate_ok(tmp_path: Path) -> None:
    cfg_dir = _write_minimal_devctl(tmp_path)
    result = runner.invoke(app, ["validate", "--config-dir", str(cfg_dir)])
    assert result.exit_code == 0, result.output
    assert "OK" in result.output


def test_cli_validate_manifest_missing(tmp_path: Path) -> None:
    result = runner.invoke(app, ["validate", "--config-dir", str(tmp_path / "nope")])
    assert result.exit_code == 10
    assert "MAN_001" in result.output


def test_cli_validate_config_missing(tmp_path: Path) -> None:
    cfg_dir = tmp_path / ".devctl"
    cfg_dir.mkdir()
    result = runner.invoke(app, ["validate", "--config-dir", str(cfg_dir)])
    assert result.exit_code == 11
    assert "MAN_002" in result.output


def test_cli_validate_services_empty(tmp_path: Path) -> None:
    cfg_dir = tmp_path / ".devctl"
    (cfg_dir / "services").mkdir(parents=True)
    (cfg_dir / "config.yaml").write_text("version: 1\nproject:\n  name: demo\n")
    result = runner.invoke(app, ["validate", "--config-dir", str(cfg_dir)])
    assert result.exit_code == 12
    assert "MAN_003" in result.output


def test_cli_validate_bad_version(tmp_path: Path) -> None:
    cfg_dir = _write_minimal_devctl(tmp_path, version=2)
    result = runner.invoke(app, ["validate", "--config-dir", str(cfg_dir)])
    assert result.exit_code == 2
    assert "CFG_002" in result.output
    assert "ERROR: CFG_002" in result.output


def test_cli_validate_bad_yaml(tmp_path: Path) -> None:
    cfg_dir = tmp_path / ".devctl"
    (cfg_dir / "services").mkdir(parents=True)
    (cfg_dir / "config.yaml").write_text("version: 1\nproject:\n  name: *x\n")
    result = runner.invoke(app, ["validate", "--config-dir", str(cfg_dir)])
    assert result.exit_code == 1
    assert "CFG_001" in result.output


def test_cli_validate_duplicate_service(tmp_path: Path) -> None:
    cfg_dir = _write_minimal_devctl(tmp_path)
    (cfg_dir / "services" / "pg2.yaml").write_text("name: postgres\nprovider: native\ncommand: x\n")
    result = runner.invoke(app, ["validate", "--config-dir", str(cfg_dir)])
    assert result.exit_code == 3
    assert "CFG_003" in result.output


def test_cli_validate_cycle(tmp_path: Path) -> None:
    cfg_dir = tmp_path / ".devctl"
    (cfg_dir / "services").mkdir(parents=True)
    (cfg_dir / "hooks").mkdir()
    (cfg_dir / "config.yaml").write_text(
        "version: 1\nproject:\n  name: demo\npaths:\n  hooks: .devctl/hooks\n"
    )
    (cfg_dir / "services" / "a.yaml").write_text(
        "name: a\nprovider: native\ncommand: a\ndepends_on: [b]\n"
    )
    (cfg_dir / "services" / "b.yaml").write_text(
        "name: b\nprovider: native\ncommand: b\ndepends_on: [a]\n"
    )
    result = runner.invoke(app, ["validate", "--config-dir", str(cfg_dir)])
    assert result.exit_code == 4
    assert "CFG_004" in result.output


def test_cli_validate_dangling_depends_on(tmp_path: Path) -> None:
    cfg_dir = tmp_path / ".devctl"
    (cfg_dir / "services").mkdir(parents=True)
    (cfg_dir / "hooks").mkdir()
    (cfg_dir / "config.yaml").write_text(
        "version: 1\nproject:\n  name: demo\npaths:\n  hooks: .devctl/hooks\n"
    )
    (cfg_dir / "services" / "a.yaml").write_text(
        "name: a\nprovider: native\ncommand: a\ndepends_on: [ghost]\n"
    )
    result = runner.invoke(app, ["validate", "--config-dir", str(cfg_dir)])
    assert result.exit_code == 5
    assert "CFG_005" in result.output
    assert "ghost" in result.output


def test_cli_validate_env_file_missing(tmp_path: Path) -> None:
    cfg_dir = tmp_path / ".devctl"
    (cfg_dir / "services").mkdir(parents=True)
    (cfg_dir / "hooks").mkdir()
    (cfg_dir / "config.yaml").write_text(
        "version: 1\nproject:\n  name: demo\npaths:\n  hooks: .devctl/hooks\n"
    )
    (cfg_dir / "services" / "a.yaml").write_text(
        "name: a\nprovider: native\ncommand: a\nenv_file: nonexistent/.env\n"
    )
    result = runner.invoke(app, ["validate", "--config-dir", str(cfg_dir)])
    assert result.exit_code == 5
    assert "CFG_005" in result.output
    assert "env_file" in result.output


def test_cli_validate_hook_missing(tmp_path: Path) -> None:
    cfg_dir = tmp_path / ".devctl"
    (cfg_dir / "services").mkdir(parents=True)
    (cfg_dir / "hooks").mkdir()
    (cfg_dir / "config.yaml").write_text(
        "version: 1\nproject:\n  name: demo\npaths:\n  hooks: .devctl/hooks\n"
    )
    (cfg_dir / "services" / "a.yaml").write_text(
        "name: a\nprovider: native\ncommand: a\nhooks:\n  post-start: nope.sh\n"
    )
    result = runner.invoke(app, ["validate", "--config-dir", str(cfg_dir)])
    assert result.exit_code == 5
    assert "CFG_005" in result.output
    assert "hooks.post-start" in result.output
