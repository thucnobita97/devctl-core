from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from devctl_core.config import (
    load_all_services,
    load_config,
    load_session,
    validate_service_references,
)
from devctl_core.config.models import Config, ServiceCfg
from devctl_core.errors import DevctlError
from devctl_core.hooks import DEFAULT_TIMEOUT, PHASES, run_phase
from devctl_core.init import init_devctl
from devctl_core.providers import ProviderContext, all_providers
from devctl_core.providers import get as get_provider

app = typer.Typer(
    name="devctl",
    help="devctl-core CLI",
    no_args_is_help=True,
    add_completion=False,
)

hook_app = typer.Typer(help="Hook commands.", no_args_is_help=True)
provider_app = typer.Typer(help="Provider commands.", no_args_is_help=True)
app.add_typer(hook_app, name="hook")
app.add_typer(provider_app, name="provider")


@app.callback()
def _root() -> None:
    """devctl-core CLI."""


_EXIT_CODES: dict[str, int] = {
    "MAN_001": 10,
    "MAN_002": 11,
    "MAN_003": 12,
    "CFG_001": 1,
    "CFG_002": 2,
    "CFG_003": 3,
    "CFG_004": 4,
    "CFG_005": 5,
    "HOK_001": 6,
    "HOK_002": 7,
    "HOK_003": 8,
    "PRV_001": 20,
    "PRV_002": 21,
    "PRV_003": 22,
    "PRV_004": 23,
    "SVC_001": 30,
    "SVC_002": 31,
    "SVC_003": 32,
    "SVC_004": 33,
    "SVC_005": 34,
}
_UNKNOWN_EXIT = 99


def _die(err: DevctlError) -> None:
    typer.echo(err.render(), err=True)
    raise typer.Exit(code=_EXIT_CODES.get(err.code, _UNKNOWN_EXIT))


def _build_context(
    config_dir: Path,
) -> tuple[Config, dict[str, ServiceCfg], ProviderContext]:
    if not config_dir.exists():
        raise DevctlError("MAN_001", context={"dir": str(config_dir)})

    project_root = config_dir.parent

    cfg_path = config_dir / "config.yaml"
    if not cfg_path.exists():
        raise DevctlError("MAN_002", context={"file": str(cfg_path)})
    cfg = load_config(cfg_path)

    services_dir = config_dir / "services"
    if not services_dir.exists():
        raise DevctlError("MAN_003", context={"dir": str(services_dir)})
    services = load_all_services(services_dir)

    hooks_dir = project_root / cfg.paths.hooks
    validate_service_references(
        services,
        project_root=project_root,
        hooks_dir=hooks_dir if hooks_dir.exists() else None,
    )

    compose_file: Path | None = None
    dc = cfg.providers.get("docker-compose")
    if isinstance(dc, dict) and "compose_file" in dc:
        compose_file = project_root / str(dc["compose_file"])

    ctx = ProviderContext(
        project_root=project_root,
        runtime_dir=project_root / cfg.paths.runtime,
        compose_file=compose_file,
        stop_timeout=cfg.defaults.stop_timeout,
    )
    return cfg, services, ctx


@app.command("validate")
def validate_cmd(
    config_dir: Annotated[
        Path,
        typer.Option("--config-dir", "-c", help="Thư mục chứa config."),
    ] = Path(".devctl"),
) -> None:
    """Validate .devctl/ (config.yaml + session.yaml + services/)."""
    try:
        if not config_dir.exists():
            raise DevctlError("MAN_001", context={"dir": str(config_dir)})

        project_root = config_dir.parent

        cfg_path = config_dir / "config.yaml"
        if not cfg_path.exists():
            raise DevctlError("MAN_002", context={"file": str(cfg_path)})
        cfg = load_config(cfg_path)

        session_path = config_dir / "session.yaml"
        if session_path.exists():
            load_session(session_path)

        services_dir = config_dir / "services"
        if not services_dir.exists():
            raise DevctlError("MAN_003", context={"dir": str(services_dir)})
        has_yaml = any(
            p.is_file() and p.suffix in {".yaml", ".yml"}
            for p in services_dir.iterdir()
        )
        if not has_yaml:
            raise DevctlError("MAN_003", context={"dir": str(services_dir)})
        services = load_all_services(services_dir)

        hooks_dir = project_root / cfg.paths.hooks
        validate_service_references(
            services,
            project_root=project_root,
            hooks_dir=hooks_dir if hooks_dir.exists() else None,
        )
    except DevctlError as err:
        _die(err)

    typer.echo("OK")


@app.command("init")
def init_cmd(
    root: Annotated[
        Path,
        typer.Argument(help="Thư mục project."),
    ] = Path("."),
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Ghi đè file đã tồn tại."),
    ] = False,
) -> None:
    """Sinh skeleton .devctl/ cho project (idempotent)."""
    result = init_devctl(root, force=force)

    for path in result.created:
        typer.echo(f"created: {path}")
    for path in result.skipped:
        typer.echo(f"skipped: {path}")

    typer.echo(f"{len(result.created)} created, {len(result.skipped)} skipped")


@hook_app.command("run")
def hook_run_cmd(
    service: Annotated[str, typer.Argument(help="Tên service.")],
    phase: Annotated[str, typer.Argument(help=f"Một trong: {', '.join(PHASES)}")],
    hooks_dir: Annotated[
        Path, typer.Option("--hooks-dir", help="Thư mục chứa hook."),
    ] = Path(".devctl/hooks"),
    ignore_hooks: Annotated[
        bool, typer.Option("--ignore-hooks", help="Bỏ qua toàn bộ hook."),
    ] = False,
    timeout: Annotated[
        float, typer.Option("--timeout", help="Timeout mỗi hook (giây)."),
    ] = DEFAULT_TIMEOUT,
) -> None:
    """Chạy hook cho SERVICE ở PHASE (fail-fast)."""
    if phase not in PHASES:
        typer.echo(
            f"ERROR: CFG_002\nfield: phase\nvalue: {phase}\n"
            f"Suggestion:\nChọn một trong: {', '.join(PHASES)}\n"
            f"Docs: docs/02-CONFIG-SCHEMA.md",
            err=True,
        )
        raise typer.Exit(code=2)

    try:
        ran = run_phase(
            service,
            phase,
            hooks_dir,
            ignore_hooks=ignore_hooks,
            timeout=timeout,
        )
    except DevctlError as err:
        _die(err)

    if not ran:
        typer.echo(f"no hooks for {service}.{phase}")
    else:
        for hook in ran:
            typer.echo(f"ran: {hook}")


@provider_app.command("list")
def provider_list_cmd() -> None:
    """Liệt kê provider đã đăng ký."""
    for name in sorted(all_providers()):
        typer.echo(name)


@app.command("start")
def start_cmd(
    service: Annotated[str, typer.Argument(help="Tên service.")],
    config_dir: Annotated[
        Path, typer.Option("--config-dir", "-c", help="Thư mục chứa config."),
    ] = Path(".devctl"),
    ignore_hooks: Annotated[
        bool, typer.Option("--ignore-hooks", help="Bỏ qua toàn bộ hook."),
    ] = False,
    timeout: Annotated[
        float, typer.Option("--timeout", help="Timeout mỗi hook (giây)."),
    ] = DEFAULT_TIMEOUT,
) -> None:
    """Start một service (pre-start → provider.start → post-start)."""
    try:
        cfg, services, ctx = _build_context(config_dir)
        if service not in services:
            raise DevctlError("SVC_001", context={"service": service})
        svc = services[service]
        provider = get_provider(svc.provider)
        hooks_dir = ctx.project_root / cfg.paths.hooks

        run_phase(
            svc.name, "pre-start", hooks_dir,
            ignore_hooks=ignore_hooks, timeout=timeout,
        )
        provider.start(svc, ctx)
        run_phase(
            svc.name, "post-start", hooks_dir,
            ignore_hooks=ignore_hooks, timeout=timeout,
        )
    except DevctlError as err:
        _die(err)

    typer.echo(f"started: {service}")


@app.command("stop")
def stop_cmd(
    service: Annotated[str, typer.Argument(help="Tên service.")],
    config_dir: Annotated[
        Path, typer.Option("--config-dir", "-c", help="Thư mục chứa config."),
    ] = Path(".devctl"),
    ignore_hooks: Annotated[
        bool, typer.Option("--ignore-hooks", help="Bỏ qua toàn bộ hook."),
    ] = False,
    timeout: Annotated[
        float, typer.Option("--timeout", help="Timeout mỗi hook (giây)."),
    ] = DEFAULT_TIMEOUT,
) -> None:
    """Stop một service (pre-stop → provider.stop → post-stop)."""
    try:
        cfg, services, ctx = _build_context(config_dir)
        if service not in services:
            raise DevctlError("SVC_001", context={"service": service})
        svc = services[service]
        provider = get_provider(svc.provider)
        hooks_dir = ctx.project_root / cfg.paths.hooks

        run_phase(
            svc.name, "pre-stop", hooks_dir,
            ignore_hooks=ignore_hooks, timeout=timeout,
        )
        provider.stop(svc, ctx)
        run_phase(
            svc.name, "post-stop", hooks_dir,
            ignore_hooks=ignore_hooks, timeout=timeout,
        )
    except DevctlError as err:
        _die(err)

    typer.echo(f"stopped: {service}")


if __name__ == "__main__":  # pragma: no cover
    app()
