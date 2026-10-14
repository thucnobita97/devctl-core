from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from devctl_core.cli import app
from devctl_core.errors import DevctlError
from devctl_core.migrations import (
    register,
    reset_for_tests,
    run_migrations,
)

runner = CliRunner()


class _V1ToV2:
    from_version = 1
    to_version = 2

    def migrate(self, data: dict[str, object]) -> dict[str, object]:
        d = dict(data)
        d["version"] = 2
        d["added_field"] = "hello"
        return d


class _V2ToV3:
    from_version = 2
    to_version = 3

    def migrate(self, data: dict[str, object]) -> dict[str, object]:
        d = dict(data)
        d["version"] = 3
        d["v3_marker"] = True
        return d


@pytest.fixture(autouse=True)
def _reset_registry() -> None:
    reset_for_tests()
    yield
    reset_for_tests()


# --------------------------- run_migrations -----------------------------


def test_run_migrations_no_op() -> None:
    data = {"version": 1}
    assert run_migrations(1, 1, data) == data


def test_run_migrations_downgrade_raises() -> None:
    with pytest.raises(DevctlError) as ei:
        run_migrations(2, 1, {})
    assert ei.value.code == "CFG_002"
    assert ei.value.context["reason"] == "downgrade_not_supported"


def test_run_migrations_missing_path() -> None:
    with pytest.raises(DevctlError) as ei:
        run_migrations(1, 2, {"version": 1})
    assert ei.value.code == "CFG_002"
    assert ei.value.context["reason"] == "migration_path_missing"


def test_run_migrations_single_step() -> None:
    register(_V1ToV2())
    result = run_migrations(1, 2, {"version": 1})
    assert result["version"] == 2
    assert result["added_field"] == "hello"


def test_run_migrations_chain() -> None:
    register(_V1ToV2())
    register(_V2ToV3())
    result = run_migrations(1, 3, {"version": 1})
    assert result["version"] == 3
    assert result["v3_marker"] is True
    assert result["added_field"] == "hello"


# ------------------------------- CLI -------------------------------------


def _write_cfg(root: Path, version: int | None) -> Path:
    cfg_dir = root / ".devctl"
    (cfg_dir / "services").mkdir(parents=True)
    if version is None:
        body = "project:\n  name: demo\n"
    else:
        body = f"version: {version}\nproject:\n  name: demo\n"
    (cfg_dir / "config.yaml").write_text(body, encoding="utf-8")
    return cfg_dir


def test_cli_migrate_already_at_version(tmp_path: Path) -> None:
    cfg_dir = _write_cfg(tmp_path, 1)
    result = runner.invoke(app, ["config", "migrate", "--config-dir", str(cfg_dir)])
    assert result.exit_code == 0, result.output
    assert "already at version 1" in result.output


def test_cli_migrate_dry_run(tmp_path: Path) -> None:
    register(_V1ToV2())
    cfg_dir = _write_cfg(tmp_path, 1)
    original = (cfg_dir / "config.yaml").read_text(encoding="utf-8")

    result = runner.invoke(
        app,
        ["config", "migrate", "--config-dir", str(cfg_dir), "--dry-run"],
    )
    assert result.exit_code == 0, result.output
    assert '"from": 1' in result.output
    assert '"to": 2' in result.output

    # file không đổi
    assert (cfg_dir / "config.yaml").read_text(encoding="utf-8") == original
    assert not (cfg_dir / "config.yaml.bak").exists()


def test_cli_migrate_writes_with_backup(tmp_path: Path) -> None:
    register(_V1ToV2())
    cfg_dir = _write_cfg(tmp_path, 1)

    result = runner.invoke(app, ["config", "migrate", "--config-dir", str(cfg_dir)])
    assert result.exit_code == 0, result.output
    assert "migrated: 1 -> 2" in result.output

    new = (cfg_dir / "config.yaml").read_text(encoding="utf-8")
    assert "version: 2" in new
    assert "added_field: hello" in new

    backup = cfg_dir / "config.yaml.bak"
    assert backup.exists()
    assert "version: 1" in backup.read_text(encoding="utf-8")


def test_cli_migrate_explicit_target(tmp_path: Path) -> None:
    register(_V1ToV2())
    register(_V2ToV3())
    cfg_dir = _write_cfg(tmp_path, 1)

    result = runner.invoke(
        app,
        [
            "config",
            "migrate",
            "--config-dir",
            str(cfg_dir),
            "--target",
            "3",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "migrated: 1 -> 3" in result.output
    new = (cfg_dir / "config.yaml").read_text(encoding="utf-8")
    assert "version: 3" in new


def test_cli_migrate_missing_config(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["config", "migrate", "--config-dir", str(tmp_path / "nope")],
    )
    assert result.exit_code == 11  # MAN_002
    assert "MAN_002" in result.output


def test_cli_migrate_missing_version(tmp_path: Path) -> None:
    cfg_dir = _write_cfg(tmp_path, None)
    result = runner.invoke(app, ["config", "migrate", "--config-dir", str(cfg_dir)])
    assert result.exit_code == 2
    assert "CFG_002" in result.output
    assert "missing_version" in result.output


def test_cli_migrate_downgrade(tmp_path: Path) -> None:
    cfg_dir = _write_cfg(tmp_path, 2)
    result = runner.invoke(
        app,
        [
            "config",
            "migrate",
            "--config-dir",
            str(cfg_dir),
            "--target",
            "1",
        ],
    )
    assert result.exit_code == 2
    assert "CFG_002" in result.output
    assert "downgrade_not_supported" in result.output
