from __future__ import annotations

import pytest

from devctl_core.errors import DevctlError, default_suggestion


@pytest.mark.parametrize("code", ["CFG_001", "CFG_002", "CFG_003", "CFG_004"])
def test_default_suggestion_known_codes(code: str) -> None:
    sug = default_suggestion(code)
    assert isinstance(sug, list)
    assert len(sug) >= 1


def test_default_suggestion_unknown_code() -> None:
    assert default_suggestion("NOPE_999") == []


def test_render_format_matches_04() -> None:
    err = DevctlError(
        "CFG_002",
        context={
            "file": ".devctl/services/backend.yaml",
            "field": "health.type",
            "value": "grpc",
        },
        suggestion=[
            "Sửa health.type thành một trong: tcp, http, exec, process",
            "Chạy lại: devctl status backend",
        ],
        docs=".devctl/README.md#health",
    )
    out = err.render()
    lines = out.splitlines()
    assert lines[0] == "ERROR: CFG_002"
    assert "file: .devctl/services/backend.yaml" in lines
    assert "field: health.type" in lines
    assert "value: grpc" in lines
    assert "Suggestion:" in lines
    idx = lines.index("Suggestion:")
    assert lines[idx + 1].startswith("Sửa health.type")
    assert lines[idx + 2].startswith("Chạy lại")
    assert lines[-1] == "Docs: .devctl/README.md#health"


def test_render_minimal_no_docs() -> None:
    err = DevctlError("CFG_003", context={"name": "dup"}, docs="")
    out = err.render()
    assert out.splitlines()[0] == "ERROR: CFG_003"
    assert "name: dup" in out
    assert "Suggestion:" in out
    assert "Docs:" not in out


def test_render_default_suggestion_used_when_omitted() -> None:
    err = DevctlError("CFG_004", context={"cycle": "a -> b -> a"})
    assert err.suggestion == default_suggestion("CFG_004")
    assert "Suggestion:" in err.render()


def test_render_default_docs_for_cfg_codes() -> None:
    err = DevctlError("CFG_001", context={"file": "x.yaml"})
    assert err.docs is not None
    assert "Docs:" in err.render()


def test_explicit_suggestion_overrides_default() -> None:
    err = DevctlError("CFG_003", suggestion=["custom"])
    assert err.suggestion == ["custom"]


def test_str_of_exception_is_code() -> None:
    err = DevctlError("CFG_002")
    assert str(err) == "CFG_002"
