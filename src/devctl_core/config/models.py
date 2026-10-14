from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from devctl_core.errors import DevctlError

_NAME_RE = re.compile(r"^[a-z][a-z0-9-]*$")

ProviderName = Literal[
    "docker-compose", "docker-external", "native", "systemd", "external"
]
HealthType = Literal["tcp", "http", "exec", "process"]


class _StrictBase(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProjectCfg(_StrictBase):
    name: str
    root: str = "."


class PathsCfg(_StrictBase):
    runtime: str = ".devctl/runtime"
    logs: str = ".devctl/logs"
    hooks: str = ".devctl/hooks"


class DefaultsCfg(_StrictBase):
    provider: str = "docker-compose"
    health_timeout: int = 30
    stop_timeout: int = 15


class SessionFilesCfg(_StrictBase):
    roadmap: str = "00-ROADMAP.md"
    resume: str = "01-RESUME.md"
    patch_rules: str = "02-PATCH-RULES.md"
    decisions: str = "03-DECISIONS.md"
    conventions: str = "04-CONVENTIONS.md"
    changelog: str = "05-CHANGELOG.md"
    known_issues: str = "06-KNOWN-ISSUES.md"
    glossary: str = "07-GLOSSARY.md"


class SessionCfg(_StrictBase):
    docs_dir: str = "docs"
    handoff_dir: str = "handoff-part-1"
    files: SessionFilesCfg = Field(default_factory=SessionFilesCfg)


class Config(_StrictBase):
    version: int
    project: ProjectCfg
    paths: PathsCfg = Field(default_factory=PathsCfg)
    defaults: DefaultsCfg = Field(default_factory=DefaultsCfg)
    providers: dict[str, Any] = Field(default_factory=dict)
    session: SessionCfg = Field(default_factory=SessionCfg)

    @field_validator("version")
    @classmethod
    def _check_version(cls, v: int) -> int:
        if v != 1:
            raise DevctlError(
                "CFG_002",
                context={"field": "version", "value": str(v)},
            )
        return v


class HealthCfg(_StrictBase):
    type: HealthType
    timeout: int = 30
    host: str | None = None
    port: int | None = None
    url: str | None = None
    command: str | None = None
    expect: str | None = None
    expect_status: int | None = None

    @model_validator(mode="after")
    def _check_required(self) -> HealthCfg:
        if self.type == "tcp":
            if not self.host or self.port is None:
                raise DevctlError(
                    "CFG_002",
                    context={"field": "health", "value": self.type},
                )
        elif self.type == "http":
            if not self.url:
                raise DevctlError(
                    "CFG_002",
                    context={"field": "health.url", "value": ""},
                )
        elif self.type == "exec" and not self.command:
            raise DevctlError(
                "CFG_002",
                context={"field": "health.command", "value": ""},
            )
        return self


class ServiceCfg(_StrictBase):
    name: str
    provider: ProviderName
    service: str | None = None
    command: str | None = None
    cwd: str | None = None
    env_file: str | None = None
    health: HealthCfg | None = None
    depends_on: list[str] = Field(default_factory=list)
    hooks: dict[str, str] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def _check_name(cls, v: str) -> str:
        if not _NAME_RE.match(v):
            raise DevctlError(
                "CFG_002",
                context={"field": "name", "value": v},
            )
        return v

    @model_validator(mode="after")
    def _check_self_dep(self) -> ServiceCfg:
        if self.name in self.depends_on:
            raise DevctlError(
                "CFG_002",
                context={"field": "depends_on", "value": self.name},
            )
        return self


__all__ = [
    "Config",
    "DefaultsCfg",
    "HealthCfg",
    "PathsCfg",
    "ProjectCfg",
    "ServiceCfg",
    "SessionCfg",
    "SessionFilesCfg",
]
