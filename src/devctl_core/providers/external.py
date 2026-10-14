from __future__ import annotations

from devctl_core.config.models import ServiceCfg
from devctl_core.errors import DevctlError
from devctl_core.providers.base import ProviderContext


class ExternalProvider:
    """Provider detect-only: devctl không start/stop, chỉ nhận biết service tồn tại."""

    name = "external"

    def detect(self, svc: ServiceCfg, ctx: ProviderContext) -> bool:
        return True

    def start(self, svc: ServiceCfg, ctx: ProviderContext) -> None:
        raise DevctlError(
            "PRV_001",
            context={
                "provider": "external",
                "service": svc.name,
                "action": "start",
                "reason": "detect_only",
            },
        )

    def stop(self, svc: ServiceCfg, ctx: ProviderContext) -> None:
        raise DevctlError(
            "PRV_001",
            context={
                "provider": "external",
                "service": svc.name,
                "action": "stop",
                "reason": "detect_only",
            },
        )

    def status(self, svc: ServiceCfg, ctx: ProviderContext) -> str:
        return "external"


__all__ = ["ExternalProvider"]
