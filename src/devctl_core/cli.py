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
from devctl_core.errors import DevctlError
from devctl_core.init import init_devctl

app = typer.Typer(
    name="devctl",
    help="devctl-core CLI",
    no_args_is_help=True,
    add_completion=False,
)


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
}
_UNKNOWN_EXIT = 99


def _die(err: DevctlError) -> None:
    typer.echo(err.render(), err=True)
    raise typer.Exit(code=_EXIT_CODES.get(err.code, _UNKNOWN_EXIT))


@app.command("validate")
def validate_cmd(
    config_dir: Annotated[
        Path,
        typer.Option(
            "--config-dir",
            "-c",
            help="Thư mục chứa config (mặc định .devctl).",
        ),
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
        typer.Argument(help="Thư mục project (mặc định: thư mục hiện tại)."),
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


if __name__ == "__main__":  # pragma: no cover
    app()
