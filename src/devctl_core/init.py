from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

TEMPLATES: dict[str, str] = {
    "config.yaml": (
        "version: 1\n"
        "\n"
        "project:\n"
        "  name: my-project\n"
        "  root: .\n"
        "\n"
        "paths:\n"
        "  runtime: .devctl/runtime\n"
        "  logs: .devctl/logs\n"
        "  hooks: .devctl/hooks\n"
        "\n"
        "defaults:\n"
        "  provider: docker-compose\n"
        "  health_timeout: 30\n"
        "  stop_timeout: 15\n"
    ),
    "session.yaml": (
        "version: 1\n"
        "\n"
        "docs:\n"
        "  roadmap: docs/00-ROADMAP.md\n"
        "  resume: docs/01-RESUME.md\n"
        "  patch_rules: docs/02-PATCH-RULES.md\n"
        "  decisions: docs/03-DECISIONS.md\n"
        "  conventions: docs/04-CONVENTIONS.md\n"
        "  changelog: docs/05-CHANGELOG.md\n"
        "  known_issues: docs/06-KNOWN-ISSUES.md\n"
        "  glossary: docs/07-GLOSSARY.md\n"
        "\n"
        "handoff:\n"
        "  sections:\n"
        "    - UPDATE 00-ROADMAP\n"
        "    - UPDATE 01-RESUME\n"
        "    - UPDATE 03-DECISIONS\n"
        "    - UPDATE 05-CHANGELOG\n"
        "    - UPDATE 06-KNOWN-ISSUES\n"
        "    - PROMPT CHO SESSION\n"
        "\n"
        "prompt:\n"
        "  template: .devctl/templates/session-prompt.md\n"
        "  language: vi\n"
    ),
    "services/.gitkeep": "",
    "hooks/.gitkeep": "",
    "templates/.gitkeep": "",
}


@dataclass
class InitResult:
    """Kết quả `devctl init`: file đã tạo và file bị skip."""

    created: list[Path] = field(default_factory=list)
    skipped: list[Path] = field(default_factory=list)


def init_devctl(root: Path, *, force: bool = False) -> InitResult:
    """Sinh skeleton `.devctl/` dưới `root`.

    Mặc định idempotent: file đã tồn tại sẽ bị skip. Dùng `force=True`
    để ghi đè.
    """
    devctl_dir = root / ".devctl"
    result = InitResult()

    for rel, content in TEMPLATES.items():
        target = devctl_dir / rel
        if target.exists() and not force:
            result.skipped.append(target)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        result.created.append(target)

    return result


__all__ = ["InitResult", "TEMPLATES", "init_devctl"]
