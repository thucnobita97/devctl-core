from __future__ import annotations

import json
import socket
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from devctl_core import doctor as doctor_mod
from devctl_core.cli import app
from devctl_core.config.models import HealthCfg, ServiceCfg
from devctl_core.doctor import (
    ENV_PORT,
    ENV_PYTHON,
    ENV_TOOL,
    ENV_WRITE,
    EXIT_DOCTOR_FAIL,
    check_environment,
)

runner = CliRunner()


def _svc(name: str = "app", **kwargs: object) -> ServiceCfg:
    return ServiceCfg(name=name, provider="native", **kwargs)  # type: ignore[arg-type]


# ------------------------------- python ----------------------------------


def test_check_python_current() -> None:
    # CI/test chạy trên 3.12 -> ok
    results = check_environment()
    py = next(r for r in results if r.name == "python")
    assert py.status == "ok"


def test_check_python_bad_version(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeVI(tuple[int, int, int]):
        pass

    # Ép sys.version_info thành 3.14
    fake = (3, 14, 0)
    monkeypatch.setattr(doctor_mod.sys, "version_info", fake)
    monkeypatch.setattr(doctor_mod.sys, "version", "3.14.0 (fake)")
    py = doctor_mod._check_python()
    assert py.status == "fail"
    assert py.code == ENV_PYTHON


# ------------------------------- tools -----------------------------------


def test_check_tool_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(doctor_mod.shutil, "which", lambda name: f"/usr/bin/{name}")
    r = doctor_mod._check_tool("uv")
    assert r.status == "ok"
    assert r.detail == "/usr/bin/uv"


def test_check_tool_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(doctor_mod.shutil, "which", lambda name: None)
    r = doctor_mod._check_tool("uv")
    assert r.status == "warn"
    assert r.code == ENV_TOOL


# ------------------------------- docker ----------------------------------


def test_docker_daemon_cli_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(doctor_mod.shutil, "which", lambda name: None)
    r = doctor_mod._check_docker_daemon()
    assert r.status == "warn"


def test_docker_daemon_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(doctor_mod.shutil, "which", lambda name: "/usr/bin/docker")
    monkeypatch.setattr(
        doctor_mod.subprocess,
        "run",
        lambda *a, **kw: subprocess.CompletedProcess(args=[], returncode=0),
    )
    r = doctor_mod._check_docker_daemon()
    assert r.status == "ok"


def test_docker_daemon_unhealthy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(doctor_mod.shutil, "which", lambda name: "/usr/bin/docker")
    monkeypatch.setattr(
        doctor_mod.subprocess,
        "run",
        lambda *a, **kw: subprocess.CompletedProcess(args=[], returncode=1),
    )
    r = doctor_mod._check_docker_daemon()
    assert r.status == "warn"


def test_docker_daemon_oserror(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(doctor_mod.shutil, "which", lambda name: "/usr/bin/docker")

    def boom(*a: object, **kw: object) -> object:
        raise OSError("no docker")

    monkeypatch.setattr(doctor_mod.subprocess, "run", boom)
    r = doctor_mod._check_docker_daemon()
    assert r.status == "warn"


# ------------------------------- git -------------------------------------


def test_check_git_ok(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    r = doctor_mod._check_git(tmp_path)
    assert r.status == "ok"


def test_check_git_missing(tmp_path: Path) -> None:
    r = doctor_mod._check_git(tmp_path)
    assert r.status == "warn"


# ------------------------------- write -----------------------------------


def test_check_write_ok(tmp_path: Path) -> None:
    r = doctor_mod._check_write_dir(tmp_path / "cfg")
    assert r.status == "ok"
    assert not (tmp_path / "cfg" / ".doctor-probe").exists()


def test_check_write_fail(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*a: object, **kw: object) -> str:
        raise OSError("permission denied")

    monkeypatch.setattr(Path, "write_text", boom)
    r = doctor_mod._check_write_dir(tmp_path / "cfg")
    assert r.status == "fail"
    assert r.code == ENV_WRITE


# ------------------------------- ports -----------------------------------


def test_check_ports_free(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(doctor_mod, "_port_free", lambda p, host="127.0.0.1": True)
    svc = _svc("app", health=HealthCfg(type="tcp", host="localhost", port=8080))
    results = doctor_mod._check_ports({"app": svc})
    assert len(results) == 1
    assert results[0].status == "ok"


def test_check_ports_conflict(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(doctor_mod, "_port_free", lambda p, host="127.0.0.1": False)
    svc = _svc("app", health=HealthCfg(type="tcp", host="localhost", port=8080))
    results = doctor_mod._check_ports({"app": svc})
    assert len(results) == 1
    assert results[0].status == "fail"
    assert results[0].code == ENV_PORT


def test_check_ports_includes_health_port(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(doctor_mod, "_port_free", lambda p, host="127.0.0.1": True)
    svc = _svc(
        "app",
        health=HealthCfg(type="tcp", host="localhost", port=5432),
    )
    results = doctor_mod._check_ports({"app": svc})
    names = {r.name for r in results}
    assert "port:app:5432" in names


def test_port_free_real_bind() -> None:
    # bind 1 socket rồi check port đó -> occupied
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        assert doctor_mod._port_free(port) is False


# ------------------------------- orchestrator ----------------------------


def test_check_environment_no_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(doctor_mod.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(
        doctor_mod.subprocess,
        "run",
        lambda *a, **kw: subprocess.CompletedProcess(args=[], returncode=0),
    )
    results = check_environment()
    names = {r.name for r in results}
    assert "python" in names
    assert "docker" in names
    assert "docker-daemon" in names
    assert "git-repo" not in names
    assert "write-config-dir" not in names


def test_check_environment_with_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(doctor_mod.shutil, "which", lambda name: None)
    (tmp_path / ".git").mkdir()
    results = check_environment(
        project_root=tmp_path,
        config_dir=tmp_path / ".devctl",
    )
    names = {r.name for r in results}
    assert "git-repo" in names
    assert "write-config-dir" in names


# ------------------------------- CLI -------------------------------------


def test_cli_doctor_text(tmp_path: Path) -> None:
    (tmp_path / ".devctl").mkdir()
    (tmp_path / ".devctl" / "services").mkdir()
    result = runner.invoke(app, ["doctor", "--config-dir", str(tmp_path / ".devctl")])
    assert result.exit_code in (0, EXIT_DOCTOR_FAIL)
    assert "[OK" in result.output or "[WARN" in result.output or "[FAIL" in result.output


def test_cli_doctor_json(tmp_path: Path) -> None:
    (tmp_path / ".devctl").mkdir()
    (tmp_path / ".devctl" / "services").mkdir()
    result = runner.invoke(app, ["doctor", "--config-dir", str(tmp_path / ".devctl"), "--json"])
    assert result.exit_code in (0, EXIT_DOCTOR_FAIL)
    payload = json.loads(result.output)
    assert isinstance(payload, list)
    names = {row["name"] for row in payload}
    assert "python" in names


def test_cli_doctor_fail_exit_code(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / ".devctl").mkdir()
    (tmp_path / ".devctl" / "services").mkdir()

    # Ép port bị chiếm
    monkeypatch.setattr(doctor_mod, "_port_free", lambda p, host="127.0.0.1": False)
    (tmp_path / ".devctl" / "config.yaml").write_text(
        "version: 1\nproject:\n  name: demo\n", encoding="utf-8"
    )
    (tmp_path / ".devctl" / "services" / "app.yaml").write_text(
        "name: app\nprovider: native\nhealth:\n  type: tcp\n  host: localhost\n  port: 8080\n",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["doctor", "--config-dir", str(tmp_path / ".devctl")])
    assert result.exit_code == EXIT_DOCTOR_FAIL
    assert "ENV_003" not in result.output  # code không in trong text mode
    assert "FAIL" in result.output
