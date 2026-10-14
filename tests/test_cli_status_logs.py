from __future__ import annotations

import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from devctl_core.cli import app

runner = CliRunner()


def _write_devctl(
    root: Path,
    *,
    service_health: str | None = None,
    with_log: bool = False,
) -> Path:
    cfg_dir = root / ".devctl"
    (cfg_dir / "services").mkdir(parents=True)
    (cfg_dir / "hooks").mkdir()
    (cfg_dir / "runtime").mkdir()
    (cfg_dir / "logs").mkdir()
    (cfg_dir / "config.yaml").write_text(
        "version: 1\n"
        "project:\n  name: demo\n"
        "paths:\n"
        "  runtime: .devctl/runtime\n"
        "  logs: .devctl/logs\n"
        "  hooks: .devctl/hooks\n",
        encoding="utf-8",
    )
    body = "name: app\nprovider: native\ncommand: echo hi\n"
    if service_health is not None:
        body += service_health
    (cfg_dir / "services" / "app.yaml").write_text(body, encoding="utf-8")
    if with_log:
        (cfg_dir / "logs" / "app.log").write_text(
            "\n".join(f"line-{i}" for i in range(1, 21)) + "\n",
            encoding="utf-8",
        )
    return cfg_dir


def test_status_all_stopped(tmp_path: Path) -> None:
    cfg_dir = _write_devctl(tmp_path)
    result = runner.invoke(app, ["status", "--config-dir", str(cfg_dir)])
    assert result.exit_code == 0, result.output
    assert "service" in result.output
    assert "app" in result.output
    assert "stopped" in result.output


def test_status_running(tmp_path: Path) -> None:
    cfg_dir = _write_devctl(tmp_path)
    (cfg_dir / "runtime" / "app.pid").write_text(str(os.getpid()), encoding="utf-8")
    result = runner.invoke(app, ["status", "--config-dir", str(cfg_dir)])
    assert result.exit_code == 0
    assert "running" in result.output


def test_status_unknown_service(tmp_path: Path) -> None:
    cfg_dir = _write_devctl(tmp_path)
    result = runner.invoke(
        app, ["status", "ghost", "--config-dir", str(cfg_dir)]
    )
    assert result.exit_code == 30
    assert "SVC_001" in result.output


def test_status_health_unhealthy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from devctl_core import health as health_mod

    cfg_dir = _write_devctl(
        tmp_path,
        service_health="health:\n  type: exec\n  command: \"false\"\n  timeout: 1\n",
    )
    (cfg_dir / "runtime" / "app.pid").write_text(
        str(os.getpid()), encoding="utf-8"
    )

    class FakeCompleted:
        returncode = 1
        stdout = ""
        stderr = ""

    def fake_run(*args: object, **kwargs: object) -> FakeCompleted:
        return FakeCompleted()

    monkeypatch.setattr(health_mod.subprocess, "run", fake_run)

    result = runner.invoke(app, ["status", "--config-dir", str(cfg_dir)])
    assert result.exit_code == 33
    assert "unhealthy" in result.output


def test_logs_missing(tmp_path: Path) -> None:
    cfg_dir = _write_devctl(tmp_path)
    result = runner.invoke(
        app, ["logs", "app", "--config-dir", str(cfg_dir)]
    )
    assert result.exit_code == 0
    assert "no log file" in result.output


def test_logs_tail_default(tmp_path: Path) -> None:
    cfg_dir = _write_devctl(tmp_path, with_log=True)
    (cfg_dir / "logs" / "app.log").write_text(
        "\n".join(f"line-{i}" for i in range(1, 101)) + "\n",
        encoding="utf-8",
    )
    result = runner.invoke(
        app, ["logs", "app", "--config-dir", str(cfg_dir)]
    )
    assert result.exit_code == 0
    assert "line-100" in result.output
    assert "line-51\n" in result.output
    assert "line-50\n" not in result.output
    assert "line-1\n" not in result.output


def test_logs_tail_n(tmp_path: Path) -> None:
    cfg_dir = _write_devctl(tmp_path, with_log=True)
    result = runner.invoke(
        app, ["logs", "app", "--config-dir", str(cfg_dir), "--tail", "3"]
    )
    assert result.exit_code == 0
    assert "line-20" in result.output
    assert "line-18" in result.output
    assert "line-17" not in result.output


def test_logs_unknown_service(tmp_path: Path) -> None:
    cfg_dir = _write_devctl(tmp_path, with_log=True)
    result = runner.invoke(
        app, ["logs", "ghost", "--config-dir", str(cfg_dir)]
    )
    assert result.exit_code == 30
    assert "SVC_001" in result.output
