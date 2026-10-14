from __future__ import annotations

from pathlib import Path

from devctl_core.config.models import ServiceCfg
from devctl_core.providers.base import ProviderContext
from devctl_core.runtime import ensure_runtime_dirs, log_file, pid_file


def _svc() -> ServiceCfg:
    return ServiceCfg(name="app", provider="native")


def test_pid_file_path(tmp_path: Path) -> None:
    ctx = ProviderContext(project_root=tmp_path, runtime_dir=tmp_path / "rt")
    assert pid_file(ctx, _svc()) == tmp_path / "rt" / "app.pid"


def test_log_file_with_logs_dir(tmp_path: Path) -> None:
    ctx = ProviderContext(
        project_root=tmp_path,
        runtime_dir=tmp_path / "rt",
        logs_dir=tmp_path / "logs",
    )
    assert log_file(ctx, _svc()) == tmp_path / "logs" / "app.log"


def test_log_file_fallback(tmp_path: Path) -> None:
    ctx = ProviderContext(project_root=tmp_path, runtime_dir=tmp_path / "rt")
    assert log_file(ctx, _svc()) == tmp_path / ".devctl" / "logs" / "app.log"


def test_ensure_runtime_dirs(tmp_path: Path) -> None:
    ctx = ProviderContext(
        project_root=tmp_path,
        runtime_dir=tmp_path / "rt",
        logs_dir=tmp_path / "lg",
    )
    ensure_runtime_dirs(ctx)
    assert (tmp_path / "rt").is_dir()
    assert (tmp_path / "lg").is_dir()

    # idempotent
    ensure_runtime_dirs(ctx)


def test_ensure_runtime_dirs_no_logs(tmp_path: Path) -> None:
    ctx = ProviderContext(project_root=tmp_path, runtime_dir=tmp_path / "rt")
    ensure_runtime_dirs(ctx)
    assert (tmp_path / "rt").is_dir()
