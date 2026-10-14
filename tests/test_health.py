from __future__ import annotations

import os
from pathlib import Path

import pytest

from devctl_core.config.models import HealthCfg, ServiceCfg
from devctl_core.errors import DevctlError
from devctl_core.health import check
from devctl_core.providers.base import ProviderContext


def _ctx(tmp_path: Path) -> ProviderContext:
    return ProviderContext(project_root=tmp_path, runtime_dir=tmp_path / "runtime")


def _svc(**health_kwargs: object) -> ServiceCfg:
    return ServiceCfg(
        name="app",
        provider="native",
        health=HealthCfg(**health_kwargs),  # type: ignore[arg-type]
    )


# ---------------------------------- no-op --------------------------------


def test_check_no_health_noop(tmp_path: Path) -> None:
    svc = ServiceCfg(name="app", provider="native")
    check(svc, _ctx(tmp_path))  # không raise


# ----------------------------------- tcp ---------------------------------


def test_check_tcp_ok(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:

    from devctl_core import health as health_mod

    class FakeSock:
        def __enter__(self) -> FakeSock:
            return self

        def __exit__(self, *a: object) -> None:
            pass

    def fake_create(*args: object, **kwargs: object) -> FakeSock:
        return FakeSock()

    monkeypatch.setattr(health_mod.socket, "create_connection", fake_create)
    check(_svc(type="tcp", host="localhost", port=1234), _ctx(tmp_path))


def test_check_tcp_fail(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from devctl_core import health as health_mod

    def fake_create(*args: object, **kwargs: object) -> object:
        raise OSError("connection refused")

    monkeypatch.setattr(health_mod.socket, "create_connection", fake_create)
    with pytest.raises(DevctlError) as ei:
        check(_svc(type="tcp", host="localhost", port=1234), _ctx(tmp_path))
    assert ei.value.code == "SVC_004"
    assert ei.value.context["type"] == "tcp"


# ----------------------------------- http --------------------------------


def test_check_http_ok(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from devctl_core import health as health_mod

    class FakeResp:
        status = 200

        def __enter__(self) -> FakeResp:
            return self

        def __exit__(self, *a: object) -> None:
            pass

        def getcode(self) -> int:
            return 200

    def fake_urlopen(*args: object, **kwargs: object) -> FakeResp:
        return FakeResp()

    monkeypatch.setattr(health_mod.urllib.request, "urlopen", fake_urlopen)
    check(
        _svc(type="http", url="http://x", expect_status=200),
        _ctx(tmp_path),
    )


def test_check_http_bad_status(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from devctl_core import health as health_mod

    class FakeResp:
        status = 500

        def __enter__(self) -> FakeResp:
            return self

        def __exit__(self, *a: object) -> None:
            pass

        def getcode(self) -> int:
            return 500

    def fake_urlopen(*args: object, **kwargs: object) -> FakeResp:
        return FakeResp()

    monkeypatch.setattr(health_mod.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(DevctlError) as ei:
        check(
            _svc(type="http", url="http://x", expect_status=200),
            _ctx(tmp_path),
        )
    assert ei.value.code == "SVC_004"
    assert ei.value.context["status"] == "500"


def test_check_http_url_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import urllib.error

    from devctl_core import health as health_mod

    def fake_urlopen(*args: object, **kwargs: object) -> object:
        raise urllib.error.URLError("boom")

    monkeypatch.setattr(health_mod.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(DevctlError) as ei:
        check(_svc(type="http", url="http://x"), _ctx(tmp_path))
    assert ei.value.code == "SVC_004"


# ----------------------------------- exec --------------------------------


def test_check_exec_ok(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from devctl_core import health as health_mod

    class FakeCompleted:
        returncode = 0
        stdout = "PONG\n"
        stderr = ""

    def fake_run(*args: object, **kwargs: object) -> FakeCompleted:
        return FakeCompleted()

    monkeypatch.setattr(health_mod.subprocess, "run", fake_run)
    check(
        _svc(type="exec", command="redis-cli ping", expect="PONG"),
        _ctx(tmp_path),
    )


def test_check_exec_bad_exit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from devctl_core import health as health_mod

    class FakeCompleted:
        returncode = 1
        stdout = ""
        stderr = ""

    def fake_run(*args: object, **kwargs: object) -> FakeCompleted:
        return FakeCompleted()

    monkeypatch.setattr(health_mod.subprocess, "run", fake_run)
    with pytest.raises(DevctlError) as ei:
        check(_svc(type="exec", command="x"), _ctx(tmp_path))
    assert ei.value.code == "SVC_004"
    assert ei.value.context["exit_code"] == "1"


def test_check_exec_expect_mismatch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from devctl_core import health as health_mod

    class FakeCompleted:
        returncode = 0
        stdout = "NOPE\n"
        stderr = ""

    def fake_run(*args: object, **kwargs: object) -> FakeCompleted:
        return FakeCompleted()

    monkeypatch.setattr(health_mod.subprocess, "run", fake_run)
    with pytest.raises(DevctlError) as ei:
        check(
            _svc(type="exec", command="redis-cli ping", expect="PONG"),
            _ctx(tmp_path),
        )
    assert ei.value.code == "SVC_004"
    assert ei.value.context["expected"] == "PONG"


def test_check_exec_timeout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import subprocess

    from devctl_core import health as health_mod

    def fake_run(*args: object, **kwargs: object) -> object:
        raise subprocess.TimeoutExpired(cmd="x", timeout=1)

    monkeypatch.setattr(health_mod.subprocess, "run", fake_run)
    with pytest.raises(DevctlError) as ei:
        check(_svc(type="exec", command="x"), _ctx(tmp_path))
    assert ei.value.code == "SVC_004"
    assert ei.value.context["message"] == "timeout"


# --------------------------------- process -------------------------------


def test_check_process_ok(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    (runtime / "app.pid").write_text(str(os.getpid()), encoding="utf-8")
    ctx = ProviderContext(project_root=tmp_path, runtime_dir=runtime)
    svc = ServiceCfg(name="app", provider="native", health=HealthCfg(type="process"))
    check(svc, ctx)


def test_check_process_no_pid_file(tmp_path: Path) -> None:
    svc = ServiceCfg(name="app", provider="native", health=HealthCfg(type="process"))
    with pytest.raises(DevctlError) as ei:
        check(svc, _ctx(tmp_path))
    assert ei.value.code == "SVC_004"
    assert ei.value.context["reason"] == "no_pid_file"


def test_check_process_bad_pid_file(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    (runtime / "app.pid").write_text("garbage", encoding="utf-8")
    ctx = ProviderContext(project_root=tmp_path, runtime_dir=runtime)
    svc = ServiceCfg(name="app", provider="native", health=HealthCfg(type="process"))
    with pytest.raises(DevctlError) as ei:
        check(svc, ctx)
    assert ei.value.code == "SVC_004"
    assert ei.value.context["reason"] == "bad_pid_file"


def test_check_process_dead_pid(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from devctl_core import health as health_mod

    runtime = tmp_path / "runtime"
    runtime.mkdir()
    (runtime / "app.pid").write_text("12345", encoding="utf-8")

    def fake_kill(pid: int, sig: int) -> None:
        raise ProcessLookupError

    monkeypatch.setattr(health_mod.os, "kill", fake_kill)
    ctx = ProviderContext(project_root=tmp_path, runtime_dir=runtime)
    svc = ServiceCfg(name="app", provider="native", health=HealthCfg(type="process"))
    with pytest.raises(DevctlError) as ei:
        check(svc, ctx)
    assert ei.value.code == "SVC_004"
    assert ei.value.context["reason"] == "dead_pid"
