from __future__ import annotations

import os
import signal
from pathlib import Path

import pytest
from typer.testing import CliRunner

from devctl_core.cli import app

runner = CliRunner()


def _write_devctl(root: Path) -> Path:
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
        "  hooks: .devctl/hooks\n"
        "defaults:\n"
        "  provider: native\n"
        "  stop_timeout: 1\n",
        encoding="utf-8",
    )
    (cfg_dir / "services" / "app.yaml").write_text(
        "name: app\nprovider: native\ncommand: echo hi\n",
        encoding="utf-8",
    )
    return cfg_dir


class _FakeProc:
    def __init__(self, pid: int) -> None:
        self.pid = pid


def _install_fakes(monkeypatch: pytest.MonkeyPatch, new_pid: int = 4242) -> dict[str, bool]:
    from devctl_core.providers import native as native_mod

    state = {"sigterm": False}

    def fake_popen(*args: object, **kwargs: object) -> _FakeProc:
        return _FakeProc(new_pid)

    def fake_kill(pid: int, sig: int) -> None:
        if sig == signal.SIGKILL:
            return
        if sig == signal.SIGTERM:
            state["sigterm"] = True
            return
        if sig == 0:
            if state["sigterm"]:
                raise ProcessLookupError
            return
        raise OSError

    monkeypatch.setattr(native_mod.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(native_mod.os, "kill", fake_kill)
    return state


# --------------------------------- restart -------------------------------


def test_restart_when_stopped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fakes(monkeypatch)
    cfg_dir = _write_devctl(tmp_path)

    result = runner.invoke(
        app,
        ["restart", "app", "--config-dir", str(cfg_dir), "--skip-health"],
    )
    assert result.exit_code == 0, result.output
    assert "restarted: app" in result.output
    assert (cfg_dir / "runtime" / "app.pid").exists()


def test_restart_when_running(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    state = _install_fakes(monkeypatch)
    cfg_dir = _write_devctl(tmp_path)
    (cfg_dir / "runtime" / "app.pid").write_text(str(os.getpid()), encoding="utf-8")

    result = runner.invoke(
        app,
        ["restart", "app", "--config-dir", str(cfg_dir), "--skip-health"],
    )
    assert result.exit_code == 0, result.output
    assert state["sigterm"] is True
    # pid file ghi đè bằng pid mới
    assert (cfg_dir / "runtime" / "app.pid").read_text(encoding="utf-8") == "4242"


def test_restart_unknown_service(tmp_path: Path) -> None:
    cfg_dir = _write_devctl(tmp_path)
    result = runner.invoke(
        app,
        ["restart", "ghost", "--config-dir", str(cfg_dir), "--skip-health"],
    )
    assert result.exit_code == 30
    assert "SVC_001" in result.output


# ------------------------------------ ps ---------------------------------


def test_ps_all_stopped(tmp_path: Path) -> None:
    cfg_dir = _write_devctl(tmp_path)
    result = runner.invoke(app, ["ps", "--config-dir", str(cfg_dir)])
    assert result.exit_code == 0, result.output
    assert "service\tstate" in result.output
    assert "app\tstopped" in result.output


def test_ps_running(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fakes(monkeypatch)
    cfg_dir = _write_devctl(tmp_path)
    (cfg_dir / "runtime" / "app.pid").write_text(str(os.getpid()), encoding="utf-8")

    result = runner.invoke(app, ["ps", "--config-dir", str(cfg_dir)])
    assert result.exit_code == 0
    assert "app\trunning" in result.output


def test_ps_missing_manifest(tmp_path: Path) -> None:
    result = runner.invoke(app, ["ps", "--config-dir", str(tmp_path / "nope")])
    assert result.exit_code == 10
    assert "MAN_001" in result.output
