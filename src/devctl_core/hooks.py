from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Literal

from devctl_core.errors import DevctlError

Phase = Literal["pre-start", "post-start", "pre-stop", "post-stop"]
PHASES: tuple[Phase, ...] = ("pre-start", "post-start", "pre-stop", "post-stop")

DEFAULT_TIMEOUT = 60.0


def discover_hooks(
    service_name: str, phase: str, hooks_dir: Path
) -> list[Path]:
    """Trả về các hook file cho phase, theo thứ tự chạy.

    Thứ tự:
      1. `{phase}.sh`      — global, chạy trước.
      2. `{svc}.{phase}.sh` — per-service, chạy sau.

    Chỉ trả về file tồn tại. Không kiểm tra executable (việc đó ở `_execute`).
    """
    candidates = [
        hooks_dir / f"{phase}.sh",
        hooks_dir / f"{service_name}.{phase}.sh",
    ]
    return [p for p in candidates if p.is_file()]


def _execute(hook: Path, *, timeout: float | None = DEFAULT_TIMEOUT) -> None:
    """Chạy 1 hook. Raise HOK_002/003 nếu không thoả, HOK_001 nếu exit ≠ 0."""
    if not hook.exists():
        raise DevctlError("HOK_003", context={"hook": str(hook)})

    if not os.access(hook, os.X_OK):
        raise DevctlError("HOK_002", context={"hook": str(hook)})

    try:
        result = subprocess.run(  # noqa: S603
            [str(hook)],
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise DevctlError(
            "HOK_001",
            context={"hook": str(hook), "exit_code": "timeout"},
        ) from exc
    except OSError as exc:
        raise DevctlError(
            "HOK_001",
            context={"hook": str(hook), "exit_code": "oserror", "message": str(exc)},
        ) from exc

    if result.returncode != 0:
        raise DevctlError(
            "HOK_001",
            context={"hook": str(hook), "exit_code": str(result.returncode)},
        )


def run_phase(
    service_name: str,
    phase: str,
    hooks_dir: Path,
    *,
    ignore_hooks: bool = False,
    timeout: float | None = DEFAULT_TIMEOUT,
) -> list[Path]:
    """Chạy toàn bộ hook cho phase. Fail-fast.

    Trả về list hook file đã chạy (rỗng nếu ignore hoặc không có hook nào).
    """
    if ignore_hooks:
        return []
    if not hooks_dir.exists():
        return []

    ran: list[Path] = []
    for hook in discover_hooks(service_name, phase, hooks_dir):
        _execute(hook, timeout=timeout)
        ran.append(hook)
    return ran


__all__ = ["DEFAULT_TIMEOUT", "PHASES", "Phase", "discover_hooks", "run_phase"]
