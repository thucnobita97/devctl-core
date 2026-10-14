from __future__ import annotations

import os
from pathlib import Path

import pytest

from devctl_core.config.models import ServiceCfg
from devctl_core.errors import DevctlError
from devctl_core.providers import (
    ProviderContext,
    all_providers,
)
from devctl_core.providers import (
    get as get_provider,
)
from devctl_core.providers.docker_compose import DockerComposeProvider
from devctl_core.providers.native import NativeProvider


def _svc(name: str = "app", **kwargs: object) -> ServiceCfg:
    return ServiceCfg(name=name, provider="native", **kwargs)  # type: ignore[arg-type]


# ------------------------------- registry -------------------------------


def test_registry_has_native_and_docker_compose() -> None:
    names = set(all_providers())
    assert "native" in names
    assert "docker-compose" in names


def test_registry_get_ok() -> None:
    p = get_provider("native")
    assert p.name == "native"


def test_registry_get_unknown() -> None:
    with pytest.raises(DevctlError) as ei:
        get_provider("nope")
    assert ei.value.code == "PRV_001"
    assert ei.value.context["provider"] == "nope"


# ------------------------------- native ---------------------------------


def test_native_detect() -> None:
    p = NativeProvider()
    ctx = ProviderContext(project_root=Path("."), runtime_dir=Path("/tmp"))
    assert p.detect(_svc("a", command="echo hi"), ctx) is True
    assert p.detect(_svc("a"), ctx) is False


def test_native_start_writes_pid(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from devctl_core.providers import native as native_mod

    class FakeProc:
        pid = 12345

    def fake_popen(*args: object, **kwargs: object) -> FakeProc:
        return FakeProc()

    monkeypatch.setattr(native_mod.subprocess, "Popen", fake_popen)

    p = NativeProvider()
    ctx = ProviderContext(project_root=tmp_path, runtime_dir=tmp_path / "runtime")
    p.start(_svc("app", command="echo hi"), ctx)

    pid_file = tmp_path / "runtime" / "app.pid"
    assert pid_file.read_text(encoding="utf-8") == "12345"


def test_native_start_no_command() -> None:
    p = NativeProvider()
    ctx = ProviderContext(project_root=Path("."), runtime_dir=Path("/tmp"))
    with pytest.raises(DevctlError) as ei:
        p.start(_svc("app"), ctx)
    assert ei.value.code == "SVC_002"


def test_native_start_oserror(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from devctl_core.providers import native as native_mod

    def fake_popen(*args: object, **kwargs: object) -> object:
        raise OSError("boom")

    monkeypatch.setattr(native_mod.subprocess, "Popen", fake_popen)

    p = NativeProvider()
    ctx = ProviderContext(project_root=tmp_path, runtime_dir=tmp_path / "runtime")
    with pytest.raises(DevctlError) as ei:
        p.start(_svc("app", command="echo hi"), ctx)
    assert ei.value.code == "SVC_002"
    assert ei.value.context["reason"] == "oserror"


def test_native_status_stopped_no_file(tmp_path: Path) -> None:
    p = NativeProvider()
    ctx = ProviderContext(project_root=tmp_path, runtime_dir=tmp_path / "runtime")
    assert p.status(_svc("app"), ctx) == "stopped"


def test_native_status_running(tmp_path: Path) -> None:
    p = NativeProvider()
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    (runtime / "app.pid").write_text(str(os.getpid()), encoding="utf-8")
    ctx = ProviderContext(project_root=tmp_path, runtime_dir=runtime)
    assert p.status(_svc("app"), ctx) == "running"


def test_native_status_unknown_pid(tmp_path: Path) -> None:
    p = NativeProvider()
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    (runtime / "app.pid").write_text("not-a-pid", encoding="utf-8")
    ctx = ProviderContext(project_root=tmp_path, runtime_dir=runtime)
    assert p.status(_svc("app"), ctx) == "unknown"


def test_native_stop_no_pid(tmp_path: Path) -> None:
    p = NativeProvider()
    ctx = ProviderContext(project_root=tmp_path, runtime_dir=tmp_path / "runtime")
    with pytest.raises(DevctlError) as ei:
        p.stop(_svc("app"), ctx)
    assert ei.value.code == "SVC_003"


def test_native_stop_bad_pid_file(tmp_path: Path) -> None:
    p = NativeProvider()
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    (runtime / "app.pid").write_text("garbage", encoding="utf-8")
    ctx = ProviderContext(project_root=tmp_path, runtime_dir=runtime)
    with pytest.raises(DevctlError) as ei:
        p.stop(_svc("app"), ctx)
    assert ei.value.code == "SVC_003"
    assert ei.value.context["reason"] == "bad_pid_file"


def test_native_stop_kills_pid(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from devctl_core.providers import native as native_mod

    calls: list[tuple[int, int]] = []

    def fake_kill(pid: int, sig: int) -> None:
        calls.append((pid, sig))
        if sig == 0:
            raise ProcessLookupError

    monkeypatch.setattr(native_mod.os, "kill", fake_kill)

    p = NativeProvider()
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    (runtime / "app.pid").write_text("12345", encoding="utf-8")
    ctx = ProviderContext(project_root=tmp_path, runtime_dir=runtime, stop_timeout=1)

    p.stop(_svc("app"), ctx)
    assert (12345, 15) in calls
    assert not (runtime / "app.pid").exists()


# --------------------------- docker-compose -----------------------------


def test_docker_compose_detect_missing_compose(tmp_path: Path) -> None:
    p = DockerComposeProvider()
    ctx = ProviderContext(project_root=tmp_path, runtime_dir=tmp_path)
    svc = ServiceCfg(name="app", provider="docker-compose")
    with pytest.raises(DevctlError) as ei:
        p.detect(svc, ctx)
    assert ei.value.code == "PRV_002"


def test_docker_compose_detect_ok(tmp_path: Path) -> None:
    compose = tmp_path / "docker-compose.yml"
    compose.write_text("services: {}\n", encoding="utf-8")
    p = DockerComposeProvider()
    ctx = ProviderContext(project_root=tmp_path, runtime_dir=tmp_path, compose_file=compose)
    svc = ServiceCfg(name="app", provider="docker-compose")
    assert p.detect(svc, ctx) is True


def test_docker_compose_start_ok(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from devctl_core.providers import docker_compose as dc_mod

    compose = tmp_path / "docker-compose.yml"
    compose.write_text("services: {}\n", encoding="utf-8")

    calls: list[list[str]] = []

    class FakeResult:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_run(cmd: list[str], *args: object, **kwargs: object) -> FakeResult:
        calls.append(list(cmd))
        return FakeResult()

    monkeypatch.setattr(dc_mod.subprocess, "run", fake_run)

    p = DockerComposeProvider()
    ctx = ProviderContext(project_root=tmp_path, runtime_dir=tmp_path, compose_file=compose)
    svc = ServiceCfg(name="app", provider="docker-compose", service="app")
    p.start(svc, ctx)
    assert any("up" in c for c in calls)


def test_docker_compose_start_fail(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from devctl_core.providers import docker_compose as dc_mod

    compose = tmp_path / "docker-compose.yml"
    compose.write_text("services: {}\n", encoding="utf-8")

    class FakeResult:
        returncode = 1
        stdout = ""
        stderr = ""

    def fake_run(*args: object, **kwargs: object) -> FakeResult:
        return FakeResult()

    monkeypatch.setattr(dc_mod.subprocess, "run", fake_run)

    p = DockerComposeProvider()
    ctx = ProviderContext(project_root=tmp_path, runtime_dir=tmp_path, compose_file=compose)
    svc = ServiceCfg(name="app", provider="docker-compose", service="app")
    with pytest.raises(DevctlError) as ei:
        p.start(svc, ctx)
    assert ei.value.code == "SVC_002"


def test_docker_compose_status_running(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from devctl_core.providers import docker_compose as dc_mod

    compose = tmp_path / "docker-compose.yml"
    compose.write_text("services: {}\n", encoding="utf-8")

    class FakeResult:
        returncode = 0
        stdout = "abc123\n"
        stderr = ""

    def fake_run(*args: object, **kwargs: object) -> FakeResult:
        return FakeResult()

    monkeypatch.setattr(dc_mod.subprocess, "run", fake_run)

    p = DockerComposeProvider()
    ctx = ProviderContext(project_root=tmp_path, runtime_dir=tmp_path, compose_file=compose)
    svc = ServiceCfg(name="app", provider="docker-compose", service="app")
    assert p.status(svc, ctx) == "running"


def test_docker_compose_status_stopped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from devctl_core.providers import docker_compose as dc_mod

    compose = tmp_path / "docker-compose.yml"
    compose.write_text("services: {}\n", encoding="utf-8")

    class FakeResult:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_run(*args: object, **kwargs: object) -> FakeResult:
        return FakeResult()

    monkeypatch.setattr(dc_mod.subprocess, "run", fake_run)

    p = DockerComposeProvider()
    ctx = ProviderContext(project_root=tmp_path, runtime_dir=tmp_path, compose_file=compose)
    svc = ServiceCfg(name="app", provider="docker-compose", service="app")
    assert p.status(svc, ctx) == "stopped"


# ---------------------------- CLI start/stop ----------------------------


def _write_devctl(root: Path, *, with_service: bool = True) -> Path:
    cfg_dir = root / ".devctl"
    (cfg_dir / "services").mkdir(parents=True)
    (cfg_dir / "hooks").mkdir()
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
    if with_service:
        (cfg_dir / "services" / "app.yaml").write_text(
            "name: app\nprovider: native\ncommand: echo hi\n",
            encoding="utf-8",
        )
    return cfg_dir


def test_cli_provider_list() -> None:
    from typer.testing import CliRunner

    from devctl_core.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["provider", "list"])
    assert result.exit_code == 0
    assert "native" in result.output
    assert "docker-compose" in result.output


def test_cli_start_unknown_service(tmp_path: Path) -> None:
    from typer.testing import CliRunner

    from devctl_core.cli import app

    runner = CliRunner()
    cfg_dir = _write_devctl(tmp_path)
    result = runner.invoke(app, ["start", "ghost", "--config-dir", str(cfg_dir)])
    assert result.exit_code == 30
    assert "SVC_001" in result.output


def test_cli_start_ok(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from typer.testing import CliRunner

    from devctl_core.cli import app
    from devctl_core.providers import native as native_mod

    class FakeProc:
        pid = 4242

    def fake_popen(*args: object, **kwargs: object) -> FakeProc:
        return FakeProc()

    monkeypatch.setattr(native_mod.subprocess, "Popen", fake_popen)

    runner = CliRunner()
    cfg_dir = _write_devctl(tmp_path)
    result = runner.invoke(app, ["start", "app", "--config-dir", str(cfg_dir)])
    assert result.exit_code == 0, result.output
    assert "started: app" in result.output
    assert (tmp_path / ".devctl" / "runtime" / "app.pid").exists()


def test_cli_stop_not_running(tmp_path: Path) -> None:
    from typer.testing import CliRunner

    from devctl_core.cli import app

    runner = CliRunner()
    cfg_dir = _write_devctl(tmp_path)
    result = runner.invoke(app, ["stop", "app", "--config-dir", str(cfg_dir)])
    assert result.exit_code == 32
    assert "SVC_003" in result.output


def test_native_start_already_running(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = NativeProvider()
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    (runtime / "app.pid").write_text(str(os.getpid()), encoding="utf-8")
    ctx = ProviderContext(project_root=tmp_path, runtime_dir=runtime)

    with pytest.raises(DevctlError) as ei:
        p.start(_svc("app", command="echo hi"), ctx)
    assert ei.value.code == "SVC_002"
    assert ei.value.context["reason"] == "already_running"


def test_native_start_empty_command(tmp_path: Path) -> None:
    p = NativeProvider()
    ctx = ProviderContext(project_root=tmp_path, runtime_dir=tmp_path / "runtime")
    with pytest.raises(DevctlError) as ei:
        p.start(_svc("app", command="   "), ctx)
    assert ei.value.code == "SVC_002"
    assert ei.value.context["reason"] == "empty_command"


def test_native_is_alive_permission_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from devctl_core.providers import native as native_mod

    def fake_kill(pid: int, sig: int) -> None:
        raise PermissionError

    monkeypatch.setattr(native_mod.os, "kill", fake_kill)
    assert NativeProvider._is_alive(1234) is True


def test_native_is_alive_oserror(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from devctl_core.providers import native as native_mod

    def fake_kill(pid: int, sig: int) -> None:
        raise OSError

    monkeypatch.setattr(native_mod.os, "kill", fake_kill)
    assert NativeProvider._is_alive(1234) is False


def test_native_terminate_process_already_gone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from devctl_core.providers import native as native_mod

    def fake_kill(pid: int, sig: int) -> None:
        raise ProcessLookupError

    monkeypatch.setattr(native_mod.os, "kill", fake_kill)
    NativeProvider._terminate(12345, timeout=0)


def test_native_terminate_sigkill_after_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from devctl_core.providers import native as native_mod

    calls: list[tuple[int, int]] = []

    def fake_kill(pid: int, sig: int) -> None:
        calls.append((pid, sig))

    monkeypatch.setattr(native_mod.os, "kill", fake_kill)
    NativeProvider._terminate(999, timeout=-1)
    assert (999, 15) in calls
    assert (999, 9) in calls


def test_docker_compose_status_returncode_nonzero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from devctl_core.providers import docker_compose as dc_mod

    compose = tmp_path / "docker-compose.yml"
    compose.write_text("services: {}\n", encoding="utf-8")

    class FakeResult:
        returncode = 1
        stdout = ""
        stderr = ""

    def fake_run(*args: object, **kwargs: object) -> FakeResult:
        return FakeResult()

    monkeypatch.setattr(dc_mod.subprocess, "run", fake_run)

    p = DockerComposeProvider()
    ctx = ProviderContext(project_root=tmp_path, runtime_dir=tmp_path, compose_file=compose)
    svc = ServiceCfg(name="app", provider="docker-compose", service="app")
    assert p.status(svc, ctx) == "unknown"


def test_docker_compose_exec_oserror(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from devctl_core.providers import docker_compose as dc_mod

    compose = tmp_path / "docker-compose.yml"
    compose.write_text("services: {}\n", encoding="utf-8")

    def fake_run(*args: object, **kwargs: object) -> object:
        raise OSError("docker not found")

    monkeypatch.setattr(dc_mod.subprocess, "run", fake_run)

    p = DockerComposeProvider()
    ctx = ProviderContext(project_root=tmp_path, runtime_dir=tmp_path, compose_file=compose)
    svc = ServiceCfg(name="app", provider="docker-compose", service="app")
    with pytest.raises(DevctlError) as ei:
        p.start(svc, ctx)
    assert ei.value.code == "PRV_001"
    assert ei.value.context["reason"] == "docker_missing"


def test_docker_compose_stop_ok(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from devctl_core.providers import docker_compose as dc_mod

    compose = tmp_path / "docker-compose.yml"
    compose.write_text("services: {}\n", encoding="utf-8")

    class FakeResult:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_run(*args: object, **kwargs: object) -> FakeResult:
        return FakeResult()

    monkeypatch.setattr(dc_mod.subprocess, "run", fake_run)

    p = DockerComposeProvider()
    ctx = ProviderContext(project_root=tmp_path, runtime_dir=tmp_path, compose_file=compose)
    svc = ServiceCfg(name="app", provider="docker-compose", service="app")
    p.stop(svc, ctx)
