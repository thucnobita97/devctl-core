from __future__ import annotations

import subprocess

from devctl_core.config.models import ServiceCfg
from devctl_core.errors import DevctlError
from devctl_core.providers.base import ProviderContext


class DockerExternalProvider:
    """Provider detect-only cho container đã chạy ngoài devctl."""

    name = "docker-external"

    @staticmethod
    def _container(svc: ServiceCfg) -> str:
        return svc.service or svc.name

    def detect(self, svc: ServiceCfg, ctx: ProviderContext) -> bool:
        container = self._container(svc)
        try:
            r = subprocess.run(  # noqa: S603
                ["docker", "ps", "--filter", f"name={container}", "-q"],
                check=False,
                capture_output=True,
                text=True,
            )
        except OSError as exc:
            raise DevctlError(
                "PRV_001",
                context={"reason": "docker_missing", "message": str(exc)},
            ) from exc

        if r.returncode != 0 or not r.stdout.strip():
            raise DevctlError(
                "PRV_004",
                context={"service": svc.name, "container": container},
            )
        return True

    def start(self, svc: ServiceCfg, ctx: ProviderContext) -> None:
        raise DevctlError(
            "PRV_001",
            context={
                "provider": "docker-external",
                "service": svc.name,
                "action": "start",
                "reason": "detect_only",
            },
        )

    def stop(self, svc: ServiceCfg, ctx: ProviderContext) -> None:
        raise DevctlError(
            "PRV_001",
            context={
                "provider": "docker-external",
                "service": svc.name,
                "action": "stop",
                "reason": "detect_only",
            },
        )

    def status(self, svc: ServiceCfg, ctx: ProviderContext) -> str:
        container = self._container(svc)
        try:
            r = subprocess.run(  # noqa: S603
                ["docker", "inspect", "-f", "{{.State.Running}}", container],
                check=False,
                capture_output=True,
                text=True,
            )
        except OSError:
            return "unknown"
        if r.returncode != 0:
            return "stopped"
        return "running" if r.stdout.strip() == "true" else "stopped"


__all__ = ["DockerExternalProvider"]
