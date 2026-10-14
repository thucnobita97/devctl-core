from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from devctl_core.config.models import ServiceCfg
from devctl_core.errors import DevctlError
from devctl_core.providers import all_providers
from devctl_core.providers import get as get_provider
from devctl_core.providers.base import ProviderContext
from devctl_core.providers.docker_external import DockerExternalProvider
from devctl_core.providers.external import ExternalProvider
from devctl_core.providers.systemd import SystemdProvider


def _svc(name: str = "app", **kwargs: object) -> ServiceCfg:
    return ServiceCfg(name=name, provider="native", **kwargs)  # type: ignore[arg-type]


def _ctx(tmp_path: Path, scope: str = "user") -> ProviderContext:
    return ProviderContext(
        project_root=tmp_path,
        runtime_dir=tmp_path / "rt",
        systemd_scope=scope,
    )


def _completed(
    returncode: int = 0, stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


# ------------------------------ registry --------------------------------


def test_registry_has_all_providers() -> None:
    names = set(all_providers())
    for expected in ("native", "docker-compose", "systemd", "external", "docker-external"):
        assert expected in names


def test_registry_get_systemd() -> None:
    assert get_provider("systemd").name == "systemd"


# ------------------------------ systemd ---------------------------------


def test_systemd_detect_ok(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from devctl_core.providers import systemd as sd_mod

    calls: list[list[str]] = []

    def fake_run(cmd: list[str], *a: object, **kw: object) -> subprocess.CompletedProcess[str]:
        calls.append(list(cmd))
        return _completed(0, "[Unit]\nDescription=app\n")

    monkeypatch.setattr(sd_mod.subprocess, "run", fake_run)

    p = SystemdProvider()
    svc = _svc("app")
    assert p.detect(svc, _ctx(tmp_path)) is True
    # user scope mặc định
    assert calls[0][:2] == ["systemctl", "--user"]
    assert calls[0][2] == "cat"


def test_systemd_detect_system_scope(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from devctl_core.providers import systemd as sd_mod

    calls: list[list[str]] = []

    def fake_run(cmd: list[str], *a: object, **kw: object) -> subprocess.CompletedProcess[str]:
        calls.append(list(cmd))
        return _completed(0, "")

    monkeypatch.setattr(sd_mod.subprocess, "run", fake_run)

    p = SystemdProvider()
    p.detect(_svc("app"), _ctx(tmp_path, scope="system"))
    assert calls[0][:2] == ["systemctl", "cat"]


def test_systemd_detect_missing_unit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from devctl_core.providers import systemd as sd_mod

    def fake_run(*a: object, **kw: object) -> subprocess.CompletedProcess[str]:
        return _completed(1, "", "no unit")

    monkeypatch.setattr(sd_mod.subprocess, "run", fake_run)

    p = SystemdProvider()
    with pytest.raises(DevctlError) as ei:
        p.detect(_svc("app"), _ctx(tmp_path))
    assert ei.value.code == "PRV_003"
    assert ei.value.context["unit"] == "app"


def test_systemd_start_ok(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from devctl_core.providers import systemd as sd_mod

    def fake_run(*a: object, **kw: object) -> subprocess.CompletedProcess[str]:
        return _completed(0, "")

    monkeypatch.setattr(sd_mod.subprocess, "run", fake_run)
    SystemdProvider().start(_svc("app"), _ctx(tmp_path))


def test_systemd_start_fail(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from devctl_core.providers import systemd as sd_mod

    def fake_run(cmd: list[str], *a: object, **kw: object) -> subprocess.CompletedProcess[str]:
        if "cat" in cmd:
            return _completed(0, "")
        return _completed(1, "", "fail")

    monkeypatch.setattr(sd_mod.subprocess, "run", fake_run)
    with pytest.raises(DevctlError) as ei:
        SystemdProvider().start(_svc("app"), _ctx(tmp_path))
    assert ei.value.code == "SVC_002"


def test_systemd_stop_fail(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from devctl_core.providers import systemd as sd_mod

    def fake_run(cmd: list[str], *a: object, **kw: object) -> subprocess.CompletedProcess[str]:
        if "cat" in cmd:
            return _completed(0, "")
        return _completed(1, "", "fail")

    monkeypatch.setattr(sd_mod.subprocess, "run", fake_run)
    with pytest.raises(DevctlError) as ei:
        SystemdProvider().stop(_svc("app"), _ctx(tmp_path))
    assert ei.value.code == "SVC_003"


def test_systemd_status_running(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from devctl_core.providers import systemd as sd_mod

    def fake_run(*a: object, **kw: object) -> subprocess.CompletedProcess[str]:
        return _completed(0, "active\n")

    monkeypatch.setattr(sd_mod.subprocess, "run", fake_run)
    assert SystemdProvider().status(_svc("app"), _ctx(tmp_path)) == "running"


def test_systemd_status_stopped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from devctl_core.providers import systemd as sd_mod

    def fake_run(*a: object, **kw: object) -> subprocess.CompletedProcess[str]:
        return _completed(1, "inactive\n")

    monkeypatch.setattr(sd_mod.subprocess, "run", fake_run)
    assert SystemdProvider().status(_svc("app"), _ctx(tmp_path)) == "stopped"


def test_systemd_systemctl_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from devctl_core.providers import systemd as sd_mod

    def fake_run(*a: object, **kw: object) -> object:
        raise OSError("systemctl not found")

    monkeypatch.setattr(sd_mod.subprocess, "run", fake_run)
    with pytest.raises(DevctlError) as ei:
        SystemdProvider().detect(_svc("app"), _ctx(tmp_path))
    assert ei.value.code == "PRV_001"
    assert ei.value.context["reason"] == "systemctl_missing"


def test_systemd_uses_service_field(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from devctl_core.providers import systemd as sd_mod

    calls: list[list[str]] = []

    def fake_run(cmd: list[str], *a: object, **kw: object) -> subprocess.CompletedProcess[str]:
        calls.append(list(cmd))
        return _completed(0, "")

    monkeypatch.setattr(sd_mod.subprocess, "run", fake_run)
    SystemdProvider().detect(_svc("app", service="myapp.service"), _ctx(tmp_path))
    assert calls[0][-1] == "myapp.service"


# ------------------------------ external --------------------------------


def test_external_detect_true(tmp_path: Path) -> None:
    assert ExternalProvider().detect(_svc("app"), _ctx(tmp_path)) is True


def test_external_start_raises(tmp_path: Path) -> None:
    with pytest.raises(DevctlError) as ei:
        ExternalProvider().start(_svc("app"), _ctx(tmp_path))
    assert ei.value.code == "PRV_001"
    assert ei.value.context["reason"] == "detect_only"


def test_external_stop_raises(tmp_path: Path) -> None:
    with pytest.raises(DevctlError) as ei:
        ExternalProvider().stop(_svc("app"), _ctx(tmp_path))
    assert ei.value.code == "PRV_001"


def test_external_status(tmp_path: Path) -> None:
    assert ExternalProvider().status(_svc("app"), _ctx(tmp_path)) == "external"


# --------------------------- docker-external ----------------------------


def test_docker_external_detect_ok(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from devctl_core.providers import docker_external as de_mod

    def fake_run(*a: object, **kw: object) -> subprocess.CompletedProcess[str]:
        return _completed(0, "abc123\n")

    monkeypatch.setattr(de_mod.subprocess, "run", fake_run)
    assert DockerExternalProvider().detect(_svc("app"), _ctx(tmp_path)) is True


def test_docker_external_detect_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from devctl_core.providers import docker_external as de_mod

    def fake_run(*a: object, **kw: object) -> subprocess.CompletedProcess[str]:
        return _completed(0, "")

    monkeypatch.setattr(de_mod.subprocess, "run", fake_run)
    with pytest.raises(DevctlError) as ei:
        DockerExternalProvider().detect(_svc("app"), _ctx(tmp_path))
    assert ei.value.code == "PRV_004"


def test_docker_external_docker_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from devctl_core.providers import docker_external as de_mod

    def fake_run(*a: object, **kw: object) -> object:
        raise OSError("docker missing")

    monkeypatch.setattr(de_mod.subprocess, "run", fake_run)
    with pytest.raises(DevctlError) as ei:
        DockerExternalProvider().detect(_svc("app"), _ctx(tmp_path))
    assert ei.value.code == "PRV_001"


def test_docker_external_start_stop_raise(tmp_path: Path) -> None:
    p = DockerExternalProvider()
    with pytest.raises(DevctlError) as ei1:
        p.start(_svc("app"), _ctx(tmp_path))
    assert ei1.value.code == "PRV_001"
    with pytest.raises(DevctlError) as ei2:
        p.stop(_svc("app"), _ctx(tmp_path))
    assert ei2.value.code == "PRV_001"


def test_docker_external_status_running(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from devctl_core.providers import docker_external as de_mod

    def fake_run(*a: object, **kw: object) -> subprocess.CompletedProcess[str]:
        return _completed(0, "true\n")

    monkeypatch.setattr(de_mod.subprocess, "run", fake_run)
    assert DockerExternalProvider().status(_svc("app"), _ctx(tmp_path)) == "running"


def test_docker_external_status_stopped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from devctl_core.providers import docker_external as de_mod

    def fake_run(*a: object, **kw: object) -> subprocess.CompletedProcess[str]:
        return _completed(0, "false\n")

    monkeypatch.setattr(de_mod.subprocess, "run", fake_run)
    assert DockerExternalProvider().status(_svc("app"), _ctx(tmp_path)) == "stopped"


def test_docker_external_status_unknown(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from devctl_core.providers import docker_external as de_mod

    def fake_run(*a: object, **kw: object) -> object:
        raise OSError("docker gone")

    monkeypatch.setattr(de_mod.subprocess, "run", fake_run)
    assert DockerExternalProvider().status(_svc("app"), _ctx(tmp_path)) == "unknown"


# ---------------------- systemd scope trong _build_context ---------------


def test_build_context_reads_systemd_scope(tmp_path: Path) -> None:
    from devctl_core.cli import _build_context

    cfg_dir = tmp_path / ".devctl"
    (cfg_dir / "services").mkdir(parents=True)
    (cfg_dir / "hooks").mkdir()
    (cfg_dir / "config.yaml").write_text(
        "version: 1\n"
        "project:\n  name: demo\n"
        "paths:\n"
        "  runtime: .devctl/runtime\n"
        "  logs: .devctl/logs\n"
        "  hooks: .devctl/hooks\n"
        "providers:\n"
        "  systemd:\n"
        "    scope: system\n",
        encoding="utf-8",
    )
    (cfg_dir / "services" / "app.yaml").write_text(
        "name: app\nprovider: systemd\nservice: app.service\n",
        encoding="utf-8",
    )
    _cfg, _services, ctx = _build_context(cfg_dir)
    assert ctx.systemd_scope == "system"
