from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError

from devctl_core.config._io import read_yaml, wrap_validation_error
from devctl_core.config.models import Config, ServiceCfg
from devctl_core.errors import DevctlError


def load_config(path: Path) -> Config:
    """Load & validate .devctl/config.yaml."""
    data = read_yaml(path)

    version = data.get("version")
    if version is not None and version != 1:
        raise DevctlError(
            "CFG_002",
            context={
                "file": str(path),
                "field": "version",
                "value": str(version),
                "message": "unsupported config version",
            },
        )

    try:
        return Config.model_validate(data)
    except DevctlError:
        raise
    except ValidationError as exc:
        raise wrap_validation_error(path, exc) from exc


def load_service(path: Path) -> ServiceCfg:
    """Load & validate một file .devctl/services/*.yaml."""
    data = read_yaml(path)
    try:
        return ServiceCfg.model_validate(data)
    except DevctlError:
        raise
    except ValidationError as exc:
        raise wrap_validation_error(path, exc) from exc


def _detect_cycles(services: dict[str, ServiceCfg]) -> None:
    white, gray, black = 0, 1, 2
    color: dict[str, int] = {name: white for name in services}
    stack: list[str] = []

    def visit(node: str) -> None:
        color[node] = gray
        stack.append(node)
        for dep in services[node].depends_on:
            if dep not in services:
                continue
            if color[dep] == gray:
                idx = stack.index(dep)
                cycle = [*stack[idx:], dep]
                raise DevctlError(
                    "CFG_004",
                    context={"cycle": " -> ".join(cycle)},
                )
            if color[dep] == white:
                visit(dep)
        stack.pop()
        color[node] = black

    for name in services:
        if color[name] == white:
            visit(name)


def validate_service_references(
    services: dict[str, ServiceCfg],
    *,
    project_root: Path | None = None,
    hooks_dir: Path | None = None,
) -> None:
    """Kiểm tra tính toàn vẹn tham chiếu của services.

    - `depends_on` phải trỏ tới service đã khai báo → CFG_005.
    - `env_file` (nếu có, cần `project_root`) phải tồn tại → CFG_005.
    - `hooks.*` (nếu có, cần `hooks_dir`) phải tồn tại → CFG_005.
    """
    for name, svc in services.items():
        for dep in svc.depends_on:
            if dep not in services:
                raise DevctlError(
                    "CFG_005",
                    context={
                        "service": name,
                        "field": "depends_on",
                        "value": dep,
                    },
                )
        if svc.env_file and project_root is not None:
            candidate = project_root / svc.env_file
            if not candidate.exists():
                raise DevctlError(
                    "CFG_005",
                    context={
                        "service": name,
                        "field": "env_file",
                        "value": svc.env_file,
                        "file": str(candidate),
                    },
                )
        if svc.hooks and hooks_dir is not None:
            for hook_name, hook_file in svc.hooks.items():
                candidate = hooks_dir / hook_file
                if not candidate.exists():
                    raise DevctlError(
                        "CFG_005",
                        context={
                            "service": name,
                            "field": f"hooks.{hook_name}",
                            "value": hook_file,
                            "file": str(candidate),
                        },
                    )


def load_all_services(services_dir: Path) -> dict[str, ServiceCfg]:
    """Load mọi *.yaml/*.yml trong services_dir. Raise CFG_002/003/004."""
    if not services_dir.exists() or not services_dir.is_dir():
        raise DevctlError(
            "CFG_002",
            context={"reason": "no_services", "file": str(services_dir)},
        )

    files = sorted(
        p
        for p in services_dir.iterdir()
        if p.is_file() and p.suffix in {".yaml", ".yml"}
    )
    if not files:
        raise DevctlError(
            "CFG_002",
            context={"reason": "no_services", "file": str(services_dir)},
        )

    services: dict[str, ServiceCfg] = {}
    seen: dict[str, Path] = {}

    for f in files:
        svc = load_service(f)
        if svc.name in seen:
            raise DevctlError(
                "CFG_003",
                context={
                    "name": svc.name,
                    "file_a": str(seen[svc.name]),
                    "file_b": str(f),
                },
            )
        seen[svc.name] = f
        services[svc.name] = svc

    _detect_cycles(services)
    return services


__all__ = [
    "load_config",
    "load_service",
    "load_all_services",
    "validate_service_references",
]
