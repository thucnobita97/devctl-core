from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from devctl_core.config.models import Config, ServiceCfg
from devctl_core.errors import DevctlError


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise DevctlError(
            "CFG_002",
            context={"reason": "file_not_found", "file": str(path)},
        )

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise DevctlError(
            "CFG_002",
            context={"reason": "file_not_found", "file": str(path)},
        ) from exc

    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        line = (mark.line + 1) if mark is not None else 0
        column = (mark.column + 1) if mark is not None else 0
        first_line = str(exc).splitlines()[0] if str(exc) else "parse error"
        raise DevctlError(
            "CFG_001",
            context={
                "file": str(path),
                "line": str(line),
                "column": str(column),
                "message": first_line,
            },
        ) from exc

    if data is None:
        return {}
    if not isinstance(data, dict):
        raise DevctlError(
            "CFG_002",
            context={
                "file": str(path),
                "field": "<root>",
                "value": type(data).__name__,
                "message": "top-level is not a mapping",
            },
        )
    return data


def _wrap_validation_error(path: Path, exc: ValidationError) -> DevctlError:
    first = exc.errors()[0]
    loc = ".".join(str(p) for p in first.get("loc", ()))
    return DevctlError(
        "CFG_002",
        context={
            "file": str(path),
            "field": loc or "<root>",
            "value": str(first.get("input", "")),
            "message": str(first.get("msg", "validation error")),
        },
    )


def load_config(path: Path) -> Config:
    """Load & validate .devctl/config.yaml."""
    data = _read_yaml(path)

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
        raise _wrap_validation_error(path, exc) from exc


def load_service(path: Path) -> ServiceCfg:
    """Load & validate một file .devctl/services/*.yaml."""
    data = _read_yaml(path)
    try:
        return ServiceCfg.model_validate(data)
    except DevctlError:
        raise
    except ValidationError as exc:
        raise _wrap_validation_error(path, exc) from exc


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


__all__ = ["load_config", "load_service", "load_all_services"]
