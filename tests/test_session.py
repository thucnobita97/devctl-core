from __future__ import annotations

from pathlib import Path

import pytest

from devctl_core.config import load_session
from devctl_core.errors import DevctlError

FIXTURES = Path(__file__).parent / "fixtures"


def test_load_session_valid() -> None:
    cfg = load_session(FIXTURES / "session" / "valid" / "full.yaml")
    assert cfg.version == 1
    assert cfg.docs.decisions == "docs/03-DECISIONS.md"
    assert cfg.prompt.language == "vi"
    assert len(cfg.handoff.sections) == 6


def test_load_session_missing_file() -> None:
    with pytest.raises(DevctlError) as ei:
        load_session(FIXTURES / "session" / "nope.yaml")
    assert ei.value.code == "CFG_002"
    assert ei.value.context["reason"] == "file_not_found"


def test_load_session_bad_version() -> None:
    with pytest.raises(DevctlError) as ei:
        load_session(FIXTURES / "session" / "invalid" / "bad_version.yaml")
    assert ei.value.code == "CFG_002"
    assert ei.value.context["field"] == "version"


def test_load_session_extra_field(tmp_path: Path) -> None:
    p = tmp_path / "s.yaml"
    p.write_text(
        "version: 1\n"
        "docs:\n"
        "  roadmap: a\n  resume: b\n  patch_rules: c\n  decisions: d\n"
        "  conventions: e\n  changelog: f\n  known_issues: g\n  glossary: h\n"
        "prompt:\n  template: t\n"
        "unexpected: 1\n"
    )
    with pytest.raises(DevctlError) as ei:
        load_session(p)
    assert ei.value.code == "CFG_002"


def test_load_session_missing_required(tmp_path: Path) -> None:
    p = tmp_path / "s.yaml"
    p.write_text("version: 1\n")
    with pytest.raises(DevctlError) as ei:
        load_session(p)
    assert ei.value.code == "CFG_002"
