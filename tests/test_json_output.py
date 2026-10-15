from __future__ import annotations

import json
import os
from pathlib import Path

from typer.testing import CliRunner

from devctl_core.cli import app

runner = CliRunner()


def _write_devctl(root: Path, *, version: int = 1) -> Path:
    cfg_dir = root / ".devctl"
    (cfg_dir / "services").mkdir(parents=True)
    (cfg_dir / "hooks").mkdir()
    (cfg_dir / "runtime").mkdir()
    (cfg_dir / "logs").mkdir()
    (cfg_dir / "config.yaml").write_text(
        f"version: {version}\n"
        "project:\n  name: demo\n"
        "paths:\n"
        "  runtime: .devctl/runtime\n"
        "  logs: .devctl/logs\n"
        "  hooks: .devctl/hooks\n",
        encoding="utf-8",
    )
    (cfg_dir / "services" / "app.yaml").write_text(
        "name: app\nprovider: native\ncommand: echo hi\n",
        encoding="utf-8",
    )
    return cfg_dir


# -------------------------------- validate -------------------------------


def test_validate_json_ok(tmp_path: Path) -> None:
    cfg_dir = _write_devctl(tmp_path)
    result = runner.invoke(
        app, ["validate", "--config-dir", str(cfg_dir), "--json"]
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload == {"ok": True, "errors": []}


def test_validate_json_fail(tmp_path: Path) -> None:
    cfg_dir = _write_devctl(tmp_path, version=2)
    result = runner.invoke(
        app, ["validate", "--config-dir", str(cfg_dir), "--json"]
    )
    assert result.exit_code == 2
    payload = json.loads(result.output)
    assert payload["ok"] is False
    assert len(payload["errors"]) == 1
    err = payload["errors"][0]
    assert err["code"] == "CFG_002"
    assert "context" in err
    assert "suggestion" in err
    assert "docs" in err


def test_validate_json_missing_manifest(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["validate", "--config-dir", str(tmp_path / "nope"), "--json"],
    )
    assert result.exit_code == 10
    payload = json.loads(result.output)
    assert payload["ok"] is False
    assert payload["errors"][0]["code"] == "MAN_001"


# --------------------------------- status --------------------------------


def test_status_json_stopped(tmp_path: Path) -> None:
    cfg_dir = _write_devctl(tmp_path)
    result = runner.invoke(
        app, ["status", "--config-dir", str(cfg_dir), "--json"]
    )
    assert result.exit_code == 0, result.output
    rows = json.loads(result.output)
    assert isinstance(rows, list)
    assert len(rows) == 1
    assert rows[0]["name"] == "app"
    assert rows[0]["provider"] == "native"
    assert rows[0]["state"] == "stopped"
    assert rows[0]["health"] is None
    assert rows[0]["pid"] is None


def test_status_json_running(tmp_path: Path) -> None:
    cfg_dir = _write_devctl(tmp_path)
    (cfg_dir / "runtime" / "app.pid").write_text(
        str(os.getpid()), encoding="utf-8"
    )
    result = runner.invoke(
        app, ["status", "--config-dir", str(cfg_dir), "--json"]
    )
    assert result.exit_code == 0, result.output
    rows = json.loads(result.output)
    assert rows[0]["state"] == "running"
    assert rows[0]["pid"] == os.getpid()


def test_status_json_missing_manifest(tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["status", "--config-dir", str(tmp_path / "nope"), "--json"]
    )
    assert result.exit_code == 10
    payload = json.loads(result.output)
    assert payload["ok"] is False
    assert payload["errors"][0]["code"] == "MAN_001"
