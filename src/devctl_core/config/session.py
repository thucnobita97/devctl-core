from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from devctl_core.config._io import read_yaml, wrap_validation_error
from devctl_core.errors import DevctlError


class _StrictBase(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SessionDocCfg(_StrictBase):
    roadmap: str
    resume: str
    patch_rules: str
    decisions: str
    conventions: str
    changelog: str
    known_issues: str
    glossary: str


class SessionHandoffCfg(_StrictBase):
    sections: list[str] = Field(default_factory=list)


class SessionPromptCfg(_StrictBase):
    template: str
    language: str = "vi"


class SessionConfig(_StrictBase):
    version: int
    docs: SessionDocCfg
    handoff: SessionHandoffCfg = Field(default_factory=SessionHandoffCfg)
    prompt: SessionPromptCfg

    @field_validator("version")
    @classmethod
    def _check_version(cls, v: int) -> int:
        if v != 1:
            raise DevctlError(
                "CFG_002",
                context={"field": "version", "value": str(v)},
            )
        return v


def load_session(path: Path) -> SessionConfig:
    """Load & validate .devctl/session.yaml."""
    data = read_yaml(path)

    version = data.get("version")
    if version is not None and version != 1:
        raise DevctlError(
            "CFG_002",
            context={
                "file": str(path),
                "field": "version",
                "value": str(version),
                "message": "unsupported session version",
            },
        )

    try:
        return SessionConfig.model_validate(data)
    except DevctlError:
        raise
    except ValidationError as exc:
        raise wrap_validation_error(path, exc) from exc


__all__ = [
    "SessionConfig",
    "SessionDocCfg",
    "SessionHandoffCfg",
    "SessionPromptCfg",
    "load_session",
]
