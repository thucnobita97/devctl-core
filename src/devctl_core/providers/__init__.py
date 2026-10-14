from __future__ import annotations

from devctl_core.providers.base import (
    Provider,
    ProviderContext,
    all_providers,
    get,
    register,
)
from devctl_core.providers.docker_compose import DockerComposeProvider
from devctl_core.providers.native import NativeProvider

register(NativeProvider())
register(DockerComposeProvider())

__all__ = [
    "DockerComposeProvider",
    "NativeProvider",
    "Provider",
    "ProviderContext",
    "all_providers",
    "get",
    "register",
]
