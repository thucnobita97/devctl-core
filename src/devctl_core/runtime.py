from __future__ import annotations

from pathlib import Path

from devctl_core.config.models import ServiceCfg
from devctl_core.providers.base import ProviderContext


def pid_file(ctx: ProviderContext, svc: ServiceCfg) -> Path:
    """Đường dẫn PID file của service."""
    return ctx.runtime_dir / f"{svc.name}.pid"


def log_file(ctx: ProviderContext, svc: ServiceCfg) -> Path:
    """Đường dẫn log file của service (fallback `.devctl/logs`)."""
    if ctx.logs_dir is not None:
        return ctx.logs_dir / f"{svc.name}.log"
    return ctx.project_root / ".devctl" / "logs" / f"{svc.name}.log"


def ensure_runtime_dirs(ctx: ProviderContext) -> None:
    """Tạo `runtime_dir` và `logs_dir` (nếu có) — idempotent."""
    ctx.runtime_dir.mkdir(parents=True, exist_ok=True)
    if ctx.logs_dir is not None:
        ctx.logs_dir.mkdir(parents=True, exist_ok=True)


__all__ = ["ensure_runtime_dirs", "log_file", "pid_file"]
