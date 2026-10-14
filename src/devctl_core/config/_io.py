from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from devctl_core.errors import DevctlError


def read_yaml(path: Path) -> dict[str, Any]:
    """Đọc file YAML. Raise CFG_001 (parse) hoặc CFG_002 (not found/not mapping)."""
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


def wrap_validation_error(path: Path, exc: ValidationError) -> DevctlError:
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
