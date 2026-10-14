from __future__ import annotations

import platform
import sys
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version
from pathlib import Path

from devctl_core.providers import all_providers


def _core_version() -> str:
    try:
        return _pkg_version("devctl-core")
    except PackageNotFoundError:
        return "0.0.0+unknown"


def collect_info(*, config_dir: Path | None = None) -> dict[str, object]:
    """Thu thập thông tin runtime của devctl-core.

    Trả về dict JSON-serializable.
    """
    info: dict[str, object] = {
        "core_version": _core_version(),
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "providers": sorted(all_providers()),
    }
    if config_dir is not None:
        info["config_dir"] = str(config_dir)
        info["config_exists"] = config_dir.exists()
        info["config_path"] = str(config_dir / "config.yaml")
        info["services_dir"] = str(config_dir / "services")
    return info


__all__ = ["collect_info"]
