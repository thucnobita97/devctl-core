from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from devctl_core.config.models import ServiceCfg
from devctl_core.errors import DevctlError


@dataclass
class ProviderContext:
    """Bối cảnh cần thiết để provider thao tác trên service."""

    project_root: Path
    runtime_dir: Path
    compose_file: Path | None = None
    stop_timeout: int = 15


class Provider(Protocol):
    """Giao diện mọi provider phải thoả."""

    name: str

    def detect(self, svc: ServiceCfg, ctx: ProviderContext) -> bool: ...

    def start(self, svc: ServiceCfg, ctx: ProviderContext) -> None: ...

    def stop(self, svc: ServiceCfg, ctx: ProviderContext) -> None: ...

    def status(self, svc: ServiceCfg, ctx: ProviderContext) -> str: ...


_REGISTRY: dict[str, Provider] = {}


def register(provider: Provider) -> None:
    """Đăng ký provider (ghi đè nếu trùng tên)."""
    _REGISTRY[provider.name] = provider


def get(name: str) -> Provider:
    """Lấy provider theo tên. Raise PRV_001 nếu không có."""
    if name not in _REGISTRY:
        raise DevctlError(
            "PRV_001",
            context={
                "provider": name,
                "available": ", ".join(sorted(_REGISTRY)) or "<none>",
            },
        )
    return _REGISTRY[name]


def all_providers() -> dict[str, Provider]:
    """Trả về bản sao registry."""
    return dict(_REGISTRY)


__all__ = [
    "Provider",
    "ProviderContext",
    "all_providers",
    "get",
    "register",
]
