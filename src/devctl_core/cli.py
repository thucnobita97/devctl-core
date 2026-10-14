from __future__ import annotations

import json
import subprocess
import time
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
from devctl_core.health import check as health_check
from devctl_core.hooks import DEFAULT_TIMEOUT, PHASES, run_phase
from devctl_core.info import collect_info
from devctl_core.init import init_devctl
from devctl_core.providers import ProviderContext, all_providers
from devctl_core.providers import get as get_provider
from devctl_core.runtime import log_file, pid_file

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


def _err_to_dict(err: DevctlError) -> dict[str, object]:
    return {
        "code": err.code,
        "context": err.context,
        "suggestion": err.suggestion,
        "docs": err.docs,
    }


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

    systemd_scope = "user"
    sd = cfg.providers.get("systemd")
    if isinstance(sd, dict) and "scope" in sd:
        systemd_scope = str(sd["scope"])

    ctx = ProviderContext(
        project_root=project_root,
        runtime_dir=project_root / cfg.paths.runtime,
        logs_dir=project_root / cfg.paths.logs,
        compose_file=compose_file,
        systemd_scope=systemd_scope,
        stop_timeout=cfg.defaults.stop_timeout,
    )
    return cfg, services, ctx


def _wait_for_health(svc: ServiceCfg, ctx: ProviderContext) -> None:
    """Poll health check tới khi pass hoặc hết `svc.health.timeout`."""
    if svc.health is None:
        return
    deadline = time.monotonic() + float(svc.health.timeout)
    while True:
        try:
            health_check(svc, ctx)
            return
        except DevctlError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.1)


def _do_start(
    svc: ServiceCfg,
    ctx: ProviderContext,
    hooks_dir: Path,
    *,
    ignore_hooks: bool,
    timeout: float,
    skip_health: bool,
) -> None:
    provider = get_provider(svc.provider)
    run_phase(
        svc.name, "pre-start", hooks_dir,
        ignore_hooks=ignore_hooks, timeout=timeout,
    )
    provider.start(svc, ctx)
    if not skip_health:
        _wait_for_health(svc, ctx)
    run_phase(
        svc.name, "post-start", hooks_dir,
        ignore_hooks=ignore_hooks, timeout=timeout,
    )


def _do_stop(
    svc: ServiceCfg,
    ctx: ProviderContext,
    hooks_dir: Path,
    *,
    ignore_hooks: bool,
    timeout: float,
) -> None:
    provider = get_provider(svc.provider)
    run_phase(
        svc.name, "pre-stop", hooks_dir,
        ignore_hooks=ignore_hooks, timeout=timeout,
    )
    provider.stop(svc, ctx)
    run_phase(
        svc.name, "post-stop", hooks_dir,
        ignore_hooks=ignore_hooks, timeout=timeout,
    )


# ----------------------------- commands ---------------------------------


@app.command("validate")
def validate_cmd(
    config_dir: Annotated[
        Path, typer.Option("--config-dir", "-c", help="Thư mục chứa config.")
    ] = Path(".devctl"),
    json_output: Annotated[
        bool, typer.Option("--json", help="Xuất JSON thay vì text.")
    ] = False,
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
        if json_output:
            typer.echo(
                json.dumps({"ok": False, "errors": [_err_to_dict(err)]})
            )
            raise typer.Exit(code=_EXIT_CODES.get(err.code, _UNKNOWN_EXIT)) from err
        _die(err)

    if json_output:
        typer.echo(json.dumps({"ok": True, "errors": []}))
    else:
        typer.echo("OK")


@app.command("init")
def init_cmd(
    root: Annotated[Path, typer.Argument(help="Thư mục project.")] = Path("."),
    force: Annotated[
        bool, typer.Option("--force", "-f", help="Ghi đè file đã tồn tại.")
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
        Path, typer.Option("--hooks-dir", help="Thư mục chứa hook.")
    ] = Path(".devctl/hooks"),
    ignore_hooks: Annotated[
        bool, typer.Option("--ignore-hooks", help="Bỏ qua toàn bộ hook.")
    ] = False,
    timeout: Annotated[
        float, typer.Option("--timeout", help="Timeout mỗi hook (giây).")
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
        Path, typer.Option("--config-dir", "-c", help="Thư mục chứa config.")
    ] = Path(".devctl"),
    ignore_hooks: Annotated[
        bool, typer.Option("--ignore-hooks", help="Bỏ qua toàn bộ hook.")
    ] = False,
    timeout: Annotated[
        float, typer.Option("--timeout", help="Timeout mỗi hook (giây).")
    ] = DEFAULT_TIMEOUT,
    skip_health: Annotated[
        bool, typer.Option("--skip-health", help="Bỏ qua health check sau start.")
    ] = False,
) -> None:
    """Start service: pre-start hook → provider.start → health check → post-start."""
    try:
        cfg, services, ctx = _build_context(config_dir)
        if service not in services:
            raise DevctlError("SVC_001", context={"service": service})
        svc = services[service]
        hooks_dir = ctx.project_root / cfg.paths.hooks
        _do_start(
            svc, ctx, hooks_dir,
            ignore_hooks=ignore_hooks, timeout=timeout, skip_health=skip_health,
        )
    except DevctlError as err:
        _die(err)

    typer.echo(f"started: {service}")


@app.command("stop")
def stop_cmd(
    service: Annotated[str, typer.Argument(help="Tên service.")],
    config_dir: Annotated[
        Path, typer.Option("--config-dir", "-c", help="Thư mục chứa config.")
    ] = Path(".devctl"),
    ignore_hooks: Annotated[
        bool, typer.Option("--ignore-hooks", help="Bỏ qua toàn bộ hook.")
    ] = False,
    timeout: Annotated[
        float, typer.Option("--timeout", help="Timeout mỗi hook (giây).")
    ] = DEFAULT_TIMEOUT,
) -> None:
    """Stop service: pre-stop hook → provider.stop → post-stop."""
    try:
        cfg, services, ctx = _build_context(config_dir)
        if service not in services:
            raise DevctlError("SVC_001", context={"service": service})
        svc = services[service]
        hooks_dir = ctx.project_root / cfg.paths.hooks
        _do_stop(
            svc, ctx, hooks_dir,
            ignore_hooks=ignore_hooks, timeout=timeout,
        )
    except DevctlError as err:
        _die(err)

    typer.echo(f"stopped: {service}")


@app.command("restart")
def restart_cmd(
    service: Annotated[str, typer.Argument(help="Tên service.")],
    config_dir: Annotated[
        Path, typer.Option("--config-dir", "-c", help="Thư mục chứa config.")
    ] = Path(".devctl"),
    ignore_hooks: Annotated[
        bool, typer.Option("--ignore-hooks", help="Bỏ qua toàn bộ hook.")
    ] = False,
    timeout: Annotated[
        float, typer.Option("--timeout", help="Timeout mỗi hook (giây).")
    ] = DEFAULT_TIMEOUT,
    skip_health: Annotated[
        bool, typer.Option("--skip-health", help="Bỏ qua health check sau start.")
    ] = False,
) -> None:
    """Restart service: stop nếu đang chạy, rồi start (cùng hook + health)."""
    try:
        cfg, services, ctx = _build_context(config_dir)
        if service not in services:
            raise DevctlError("SVC_001", context={"service": service})
        svc = services[service]
        provider = get_provider(svc.provider)
        hooks_dir = ctx.project_root / cfg.paths.hooks

        if provider.status(svc, ctx) == "running":
            _do_stop(
                svc, ctx, hooks_dir,
                ignore_hooks=ignore_hooks, timeout=timeout,
            )
        _do_start(
            svc, ctx, hooks_dir,
            ignore_hooks=ignore_hooks, timeout=timeout, skip_health=skip_health,
        )
    except DevctlError as err:
        _die(err)

    typer.echo(f"restarted: {service}")


@app.command("ps")
def ps_cmd(
    config_dir: Annotated[
        Path, typer.Option("--config-dir", "-c", help="Thư mục chứa config.")
    ] = Path(".devctl"),
) -> None:
    """In trạng thái ngắn gọn (service\\tstate). KHÔNG gọi health check."""
    try:
        _cfg, services, ctx = _build_context(config_dir)
        typer.echo("service\tstate")
        for name in sorted(services):
            svc = services[name]
            provider = get_provider(svc.provider)
            state = provider.status(svc, ctx)
            typer.echo(f"{name}\t{state}")
    except DevctlError as err:
        _die(err)


@app.command("status")
def status_cmd(
    service: Annotated[
        str | None,
        typer.Argument(help="Tên service (bỏ trống → tất cả)."),
    ] = None,
    config_dir: Annotated[
        Path, typer.Option("--config-dir", "-c", help="Thư mục chứa config.")
    ] = Path(".devctl"),
    json_output: Annotated[
        bool, typer.Option("--json", help="Xuất JSON thay vì text.")
    ] = False,
) -> None:
    """In trạng thái service (provider + running/stopped + health)."""
    failed = False
    rows: list[dict[str, object]] = []
    try:
        _cfg, services, ctx = _build_context(config_dir)
        if service is not None and service not in services:
            raise DevctlError("SVC_001", context={"service": service})
        names = [service] if service else sorted(services)
        if not json_output:
            typer.echo("service\tprovider\tstate\thealth")
        for name in names:
            svc = services[name]
            provider = get_provider(svc.provider)
            state = provider.status(svc, ctx)
            health_state: str | None = None
            if svc.health is not None and state == "running":
                try:
                    health_check(svc, ctx)
                    health_state = "healthy"
                except DevctlError:
                    health_state = "unhealthy"
                    failed = True
            pid: int | None = None
            if state == "running":
                pf = pid_file(ctx, svc)
                if pf.exists():
                    try:
                        pid = int(pf.read_text(encoding="utf-8").strip())
                    except (OSError, ValueError):
                        pid = None
            if json_output:
                rows.append(
                    {
                        "name": name,
                        "provider": svc.provider,
                        "state": state,
                        "health": health_state,
                        "pid": pid,
                    }
                )
            else:
                shown_health = health_state if health_state is not None else "-"
                typer.echo(f"{name}\t{svc.provider}\t{state}\t{shown_health}")
    except DevctlError as err:
        if json_output:
            typer.echo(
                json.dumps({"ok": False, "errors": [_err_to_dict(err)]})
            )
            raise typer.Exit(code=_EXIT_CODES.get(err.code, _UNKNOWN_EXIT)) from err
        _die(err)

    if json_output:
        typer.echo(json.dumps(rows))

    if failed:
        raise typer.Exit(code=_EXIT_CODES["SVC_004"])


def _print_tail(path: Path, n: int) -> None:
    with path.open("r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    for line in lines[-n:]:
        typer.echo(line, nl=False)


@app.command("logs")
def logs_cmd(
    service: Annotated[str, typer.Argument(help="Tên service.")],
    config_dir: Annotated[
        Path, typer.Option("--config-dir", "-c", help="Thư mục chứa config.")
    ] = Path(".devctl"),
    tail: Annotated[int, typer.Option("--tail", "-n", help="Số dòng cuối.")] = 50,
    follow: Annotated[
        bool, typer.Option("--follow", "-f", help="Theo dõi (tail -f).")
    ] = False,
) -> None:
    """Xem log của service (`.devctl/logs/{svc}.log`)."""
    try:
        _cfg, services, ctx = _build_context(config_dir)
        if service not in services:
            raise DevctlError("SVC_001", context={"service": service})
        svc = services[service]
        path = log_file(ctx, svc)
        if not path.exists():
            typer.echo(f"no log file: {path}")
            return
        if follow:
            subprocess.call(["tail", "-n", str(tail), "-f", str(path)])  # noqa: S603,S607
        else:
            _print_tail(path, tail)
    except DevctlError as err:
        _die(err)


@app.command("info")
def info_cmd(
    config_dir: Annotated[
        Path, typer.Option("--config-dir", "-c", help="Thư mục chứa config.")
    ] = Path(".devctl"),
    json_output: Annotated[
        bool, typer.Option("--json", help="Xuất JSON thay vì text.")
    ] = False,
) -> None:
    """In thông tin runtime: version core, python, providers, config paths."""
    info = collect_info(config_dir=config_dir)
    if json_output:
        typer.echo(json.dumps(info))
        return
    for key, value in info.items():
        if isinstance(value, list):
            typer.echo(f"{key}: {', '.join(str(v) for v in value)}")
        else:
            typer.echo(f"{key}: {value}")


if __name__ == "__main__":  # pragma: no cover
    app()
