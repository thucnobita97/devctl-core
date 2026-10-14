from __future__ import annotations

import contextlib
import os
import shlex
import signal
import subprocess
import time
from pathlib import Path
from typing import IO

from devctl_core.config.models import ServiceCfg
from devctl_core.errors import DevctlError
from devctl_core.providers.base import ProviderContext


class NativeProvider:
    """Chạy service như subprocess native, quản lý qua PID file."""

    name = "native"

    def detect(self, svc: ServiceCfg, ctx: ProviderContext) -> bool:
        return bool(svc.command)

    def start(self, svc: ServiceCfg, ctx: ProviderContext) -> None:
        if not svc.command:
            raise DevctlError(
                "SVC_002",
                context={"service": svc.name, "reason": "no_command"},
            )

        pid_file = ctx.runtime_dir / f"{svc.name}.pid"
        if pid_file.exists() and self._is_alive(self._read_pid(pid_file)):
            raise DevctlError(
                "SVC_002",
                context={"service": svc.name, "reason": "already_running"},
            )

        argv = shlex.split(svc.command)
        if not argv:
            raise DevctlError(
                "SVC_002",
                context={"service": svc.name, "reason": "empty_command"},
            )

        cwd = ctx.project_root / svc.cwd if svc.cwd else ctx.project_root

        log_f: IO[str] | None = None
        if ctx.logs_dir is not None:
            ctx.logs_dir.mkdir(parents=True, exist_ok=True)
            log_f = (ctx.logs_dir / f"{svc.name}.log").open("a", encoding="utf-8")

        try:
            proc = subprocess.Popen(  # noqa: S603
                argv,
                cwd=cwd,
                stdout=log_f if log_f is not None else subprocess.DEVNULL,
                stderr=subprocess.STDOUT if log_f is not None else subprocess.DEVNULL,
                start_new_session=True,
            )
        except OSError as exc:
            raise DevctlError(
                "SVC_002",
                context={
                    "service": svc.name,
                    "reason": "oserror",
                    "message": str(exc),
                },
            ) from exc
        finally:
            if log_f is not None:
                log_f.close()

        ctx.runtime_dir.mkdir(parents=True, exist_ok=True)
        pid_file.write_text(str(proc.pid), encoding="utf-8")

    def stop(self, svc: ServiceCfg, ctx: ProviderContext) -> None:
        pid_file = ctx.runtime_dir / f"{svc.name}.pid"
        if not pid_file.exists():
            raise DevctlError(
                "SVC_003",
                context={"service": svc.name, "reason": "not_running"},
            )
        pid = self._read_pid(pid_file)
        if pid is None:
            raise DevctlError(
                "SVC_003",
                context={"service": svc.name, "reason": "bad_pid_file"},
            )
        self._terminate(pid, ctx.stop_timeout)
        pid_file.unlink(missing_ok=True)

    def status(self, svc: ServiceCfg, ctx: ProviderContext) -> str:
        pid_file = ctx.runtime_dir / f"{svc.name}.pid"
        if not pid_file.exists():
            return "stopped"
        pid = self._read_pid(pid_file)
        if pid is None:
            return "unknown"
        return "running" if self._is_alive(pid) else "stopped"

    # ------------------------- helpers -------------------------

    @staticmethod
    def _read_pid(pid_file: Path) -> int | None:
        try:
            return int(pid_file.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            return None

    @staticmethod
    def _is_alive(pid: int | None) -> bool:
        if pid is None:
            return False
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        except OSError:
            return False
        return True

    @staticmethod
    def _terminate(pid: int, timeout: int) -> None:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            return

        deadline = time.monotonic() + max(timeout, 0)
        while time.monotonic() < deadline:
            try:
                os.kill(pid, 0)
            except OSError:
                return
            time.sleep(0.05)

        with contextlib.suppress(OSError):
            os.kill(pid, signal.SIGKILL)


__all__ = ["NativeProvider"]
