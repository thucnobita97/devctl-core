from __future__ import annotations

import subprocess

from devctl_core.config.models import ServiceCfg
from devctl_core.errors import DevctlError
from devctl_core.providers.base import ProviderContext


class SystemdProvider:
    """Quản lý service qua `systemctl` (user hoặc system scope)."""

    name = "systemd"

    @staticmethod
    def _unit(svc: ServiceCfg) -> str:
        return svc.service or svc.name

    def _systemctl(
        self, ctx: ProviderContext, *args: str
    ) -> subprocess.CompletedProcess[str]:
        cmd = ["systemctl"]
        if ctx.systemd_scope == "user":
            cmd.append("--user")
        cmd.extend(args)
        try:
            return subprocess.run(  # noqa: S603
                cmd,
                check=False,
                capture_output=True,
                text=True,
            )
        except OSError as exc:
            raise DevctlError(
                "PRV_001",
                context={"reason": "systemctl_missing", "message": str(exc)},
            ) from exc

    def detect(self, svc: ServiceCfg, ctx: ProviderContext) -> bool:
        unit = self._unit(svc)
        r = self._systemctl(ctx, "cat", unit)
        if r.returncode != 0:
            raise DevctlError(
                "PRV_003",
                context={"service": svc.name, "unit": unit},
            )
        return True

    def start(self, svc: ServiceCfg, ctx: ProviderContext) -> None:
        self.detect(svc, ctx)
        unit = self._unit(svc)
        r = self._systemctl(ctx, "start", unit)
        if r.returncode != 0:
            raise DevctlError(
                "SVC_002",
                context={
                    "service": svc.name,
                    "unit": unit,
                    "exit_code": str(r.returncode),
                },
            )

    def stop(self, svc: ServiceCfg, ctx: ProviderContext) -> None:
        self.detect(svc, ctx)
        unit = self._unit(svc)
        r = self._systemctl(ctx, "stop", unit)
        if r.returncode != 0:
            raise DevctlError(
                "SVC_003",
                context={
                    "service": svc.name,
                    "unit": unit,
                    "exit_code": str(r.returncode),
                },
            )

    def status(self, svc: ServiceCfg, ctx: ProviderContext) -> str:
        unit = self._unit(svc)
        r = self._systemctl(ctx, "is-active", unit)
        if r.returncode != 0:
            return "stopped"
        return "running" if r.stdout.strip() == "active" else "stopped"


__all__ = ["SystemdProvider"]
