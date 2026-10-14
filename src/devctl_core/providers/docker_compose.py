from __future__ import annotations

import subprocess

from devctl_core.config.models import ServiceCfg
from devctl_core.errors import DevctlError
from devctl_core.providers.base import ProviderContext


class DockerComposeProvider:
    """Quản lý service qua `docker compose`."""

    name = "docker-compose"

    def detect(self, svc: ServiceCfg, ctx: ProviderContext) -> bool:
        if ctx.compose_file is None or not ctx.compose_file.exists():
            raise DevctlError(
                "PRV_002",
                context={
                    "service": svc.name,
                    "compose_file": str(ctx.compose_file) if ctx.compose_file else "<unset>",
                },
            )
        return True

    def start(self, svc: ServiceCfg, ctx: ProviderContext) -> None:
        self.detect(svc, ctx)
        self._run(svc, ctx, "SVC_002", "up", "-d", self._target(svc))

    def stop(self, svc: ServiceCfg, ctx: ProviderContext) -> None:
        self.detect(svc, ctx)
        self._run(svc, ctx, "SVC_003", "stop", self._target(svc))

    def status(self, svc: ServiceCfg, ctx: ProviderContext) -> str:
        self.detect(svc, ctx)
        result = self._exec(ctx, "ps", "-q", self._target(svc))
        if result.returncode != 0:
            return "unknown"
        return "running" if result.stdout.strip() else "stopped"

    # ------------------------- helpers -------------------------

    @staticmethod
    def _target(svc: ServiceCfg) -> str:
        return svc.service or svc.name

    def _run(
        self,
        svc: ServiceCfg,
        ctx: ProviderContext,
        error_code: str,
        *args: str,
    ) -> None:
        result = self._exec(ctx, *args)
        if result.returncode != 0:
            raise DevctlError(
                error_code,
                context={
                    "service": svc.name,
                    "reason": f"docker compose {args[0]} failed",
                    "exit_code": str(result.returncode),
                },
            )

    @staticmethod
    def _exec(ctx: ProviderContext, *args: str) -> subprocess.CompletedProcess[str]:
        cmd = ["docker", "compose", "-f", str(ctx.compose_file), *args]
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
                context={"reason": "docker_missing", "message": str(exc)},
            ) from exc


__all__ = ["DockerComposeProvider"]
