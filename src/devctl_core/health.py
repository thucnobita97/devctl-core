from __future__ import annotations

import os
import shlex
import socket
import subprocess
import urllib.error
import urllib.request

from devctl_core.config.models import HealthCfg, ServiceCfg
from devctl_core.errors import DevctlError
from devctl_core.providers.base import ProviderContext


def check(svc: ServiceCfg, ctx: ProviderContext) -> None:
    """Chạy health check cho service.

    No-op nếu `svc.health is None`. Raise `SVC_004` khi fail.
    """
    if svc.health is None:
        return

    h = svc.health
    try:
        if h.type == "tcp":
            _check_tcp(h)
        elif h.type == "http":
            _check_http(h)
        elif h.type == "exec":
            _check_exec(h)
        elif h.type == "process":
            _check_process(svc, ctx)
    except DevctlError:
        raise
    except Exception as exc:
        raise DevctlError(
            "SVC_004",
            context={
                "service": svc.name,
                "type": h.type,
                "message": str(exc),
            },
        ) from exc


def _check_tcp(h: HealthCfg) -> None:
    assert h.host is not None
    assert h.port is not None
    try:
        with socket.create_connection((h.host, h.port), timeout=h.timeout):
            pass
    except OSError as exc:
        raise DevctlError(
            "SVC_004",
            context={"type": "tcp", "host": h.host, "port": str(h.port), "message": str(exc)},
        ) from exc


def _check_http(h: HealthCfg) -> None:
    assert h.url is not None
    try:
        with urllib.request.urlopen(h.url, timeout=h.timeout) as resp:  # noqa: S310
            status = getattr(resp, "status", None) or resp.getcode()
    except urllib.error.URLError as exc:
        raise DevctlError(
            "SVC_004",
            context={"type": "http", "url": h.url, "message": str(exc)},
        ) from exc

    if h.expect_status is not None and status != h.expect_status:
        raise DevctlError(
            "SVC_004",
            context={
                "type": "http",
                "url": h.url,
                "status": str(status),
                "expected": str(h.expect_status),
            },
        )


def _check_exec(h: HealthCfg) -> None:
    assert h.command is not None
    argv = shlex.split(h.command)
    try:
        result = subprocess.run(  # noqa: S603
            argv,
            check=False,
            capture_output=True,
            text=True,
            timeout=h.timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise DevctlError(
            "SVC_004",
            context={"type": "exec", "command": h.command, "message": "timeout"},
        ) from exc
    except OSError as exc:
        raise DevctlError(
            "SVC_004",
            context={"type": "exec", "command": h.command, "message": str(exc)},
        ) from exc

    if result.returncode != 0:
        raise DevctlError(
            "SVC_004",
            context={"type": "exec", "command": h.command, "exit_code": str(result.returncode)},
        )

    if h.expect is not None and h.expect.strip() not in result.stdout:
        raise DevctlError(
            "SVC_004",
            context={
                "type": "exec",
                "command": h.command,
                "expected": h.expect,
                "stdout": result.stdout.strip()[:200],
            },
        )


def _check_process(svc: ServiceCfg, ctx: ProviderContext) -> None:
    pid_file = ctx.runtime_dir / f"{svc.name}.pid"
    if not pid_file.exists():
        raise DevctlError(
            "SVC_004",
            context={"service": svc.name, "type": "process", "reason": "no_pid_file"},
        )
    try:
        pid = int(pid_file.read_text(encoding="utf-8").strip())
    except (OSError, ValueError) as exc:
        raise DevctlError(
            "SVC_004",
            context={"service": svc.name, "type": "process", "reason": "bad_pid_file"},
        ) from exc
    try:
        os.kill(pid, 0)
    except OSError as exc:
        raise DevctlError(
            "SVC_004",
            context={"service": svc.name, "type": "process", "reason": "dead_pid"},
        ) from exc


__all__ = ["check"]
