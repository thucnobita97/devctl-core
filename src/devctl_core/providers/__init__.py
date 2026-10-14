from __future__ import annotations

from devctl_core.providers.base import (
    Provider,
    ProviderContext,
    all_providers,
    get,
    register,
)
from devctl_core.providers.docker_compose import DockerComposeProvider
from devctl_core.providers.docker_external import DockerExternalProvider
from devctl_core.providers.external import ExternalProvider
from devctl_core.providers.native import NativeProvider
from devctl_core.providers.systemd import SystemdProvider

register(NativeProvider())
register(DockerComposeProvider())
register(SystemdProvider())
register(ExternalProvider())
register(DockerExternalProvider())

__all__ = [
    "DockerComposeProvider",
    "DockerExternalProvider",
    "ExternalProvider",
    "NativeProvider",
    "Provider",
    "ProviderContext",
    "SystemdProvider",
    "all_providers",
    "get",
    "register",
]
