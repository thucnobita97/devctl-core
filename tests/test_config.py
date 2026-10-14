from __future__ import annotations

from pathlib import Path

import pytest

from devctl_core.config import load_all_services, load_config, load_service
from devctl_core.errors import DevctlError

FIXTURES = Path(__file__).parent / "fixtures"


def test_load_minimal_config() -> None:
    cfg = load_config(FIXTURES / "config" / "valid" / "minimal.yaml")
    assert cfg.version == 1
    assert cfg.project.name == "demo"
    assert cfg.paths.runtime == ".devctl/runtime"
    assert cfg.defaults.health_timeout == 30


def test_load_full_config() -> None:
    cfg = load_config(FIXTURES / "config" / "valid" / "full.yaml")
    assert cfg.project.name == "menu-platform"
    assert cfg.session.files.decisions == "03-DECISIONS.md"
    assert cfg.session.handoff_dir == "handoff-part-1"
    assert "docker-compose" in cfg.providers


def test_load_config_missing_file() -> None:
    with pytest.raises(DevctlError) as ei:
        load_config(FIXTURES / "config" / "nope.yaml")
    assert ei.value.code == "CFG_002"
    assert ei.value.context["reason"] == "file_not_found"
    assert ei.value.context["file"].endswith("nope.yaml")


def test_load_config_bad_yaml() -> None:
    with pytest.raises(DevctlError) as ei:
        load_config(FIXTURES / "config" / "invalid" / "bad_yaml.yaml")
    assert ei.value.code == "CFG_001"
    assert ei.value.context["file"].endswith("bad_yaml.yaml")
    assert "line" in ei.value.context
    assert "column" in ei.value.context
    assert "message" in ei.value.context


def test_load_config_bad_version() -> None:
    with pytest.raises(DevctlError) as ei:
        load_config(FIXTURES / "config" / "invalid" / "bad_version.yaml")
    assert ei.value.code == "CFG_002"
    assert ei.value.context["field"] == "version"
    assert ei.value.context["value"] == "2"


def test_load_config_extra_field_forbidden(tmp_path: Path) -> None:
    p = tmp_path / "extra.yaml"
    p.write_text("version: 1\nproject:\n  name: demo\nunexpected: 1\n")
    with pytest.raises(DevctlError) as ei:
        load_config(p)
    assert ei.value.code == "CFG_002"


def test_load_config_top_level_not_mapping(tmp_path: Path) -> None:
    p = tmp_path / "list.yaml"
    p.write_text("- 1\n- 2\n")
    with pytest.raises(DevctlError) as ei:
        load_config(p)
    assert ei.value.code == "CFG_002"


def test_load_service_bad_health() -> None:
    with pytest.raises(DevctlError) as ei:
        load_service(FIXTURES / "config" / "invalid" / "bad_health.yaml")
    assert ei.value.code == "CFG_002"


def test_load_service_bad_name() -> None:
    with pytest.raises(DevctlError) as ei:
        load_service(FIXTURES / "config" / "invalid" / "bad_name.yaml")
    assert ei.value.code == "CFG_002"


def test_load_service_self_dependency(tmp_path: Path) -> None:
    p = tmp_path / "self.yaml"
    p.write_text("name: a\nprovider: native\ndepends_on: [a]\n")
    with pytest.raises(DevctlError) as ei:
        load_service(p)
    assert ei.value.code == "CFG_002"


def test_load_service_valid() -> None:
    svc = load_service(FIXTURES / "services" / "valid" / "postgres.yaml")
    assert svc.name == "postgres"
    assert svc.provider == "docker-compose"
    assert svc.health is not None
    assert svc.health.type == "tcp"
    assert svc.health.port == 5432


def test_load_all_services_valid() -> None:
    services = load_all_services(FIXTURES / "services" / "valid")
    assert set(services) == {"postgres", "redis", "backend"}
    assert services["backend"].depends_on == ["postgres", "redis"]
    assert services["redis"].health is not None
    assert services["redis"].health.type == "exec"


def test_load_all_services_missing_dir() -> None:
    with pytest.raises(DevctlError) as ei:
        load_all_services(FIXTURES / "services" / "not-there")
    assert ei.value.code == "CFG_002"
    assert ei.value.context["reason"] == "no_services"


def test_load_all_services_empty_dir(tmp_path: Path) -> None:
    with pytest.raises(DevctlError) as ei:
        load_all_services(tmp_path)
    assert ei.value.code == "CFG_002"
    assert ei.value.context["reason"] == "no_services"


def test_load_all_services_duplicate(tmp_path: Path) -> None:
    (tmp_path / "a.yaml").write_text("name: dup\nprovider: native\ncommand: a\n")
    (tmp_path / "b.yaml").write_text("name: dup\nprovider: native\ncommand: b\n")
    with pytest.raises(DevctlError) as ei:
        load_all_services(tmp_path)
    assert ei.value.code == "CFG_003"
    assert ei.value.context["name"] == "dup"
    assert "file_a" in ei.value.context
    assert "file_b" in ei.value.context


def test_load_all_services_cycle(tmp_path: Path) -> None:
    (tmp_path / "a.yaml").write_text(
        "name: a\nprovider: native\ncommand: a\ndepends_on: [b]\n"
    )
    (tmp_path / "b.yaml").write_text(
        "name: b\nprovider: native\ncommand: b\ndepends_on: [a]\n"
    )
    with pytest.raises(DevctlError) as ei:
        load_all_services(tmp_path)
    assert ei.value.code == "CFG_004"
    assert "cycle" in ei.value.context
    assert ei.value.context["cycle"].count("->") >= 2


def test_load_all_services_cycle_three_nodes(tmp_path: Path) -> None:
    (tmp_path / "a.yaml").write_text(
        "name: a\nprovider: native\ncommand: a\ndepends_on: [b]\n"
    )
    (tmp_path / "b.yaml").write_text(
        "name: b\nprovider: native\ncommand: b\ndepends_on: [c]\n"
    )
    (tmp_path / "c.yaml").write_text(
        "name: c\nprovider: native\ncommand: c\ndepends_on: [a]\n"
    )
    with pytest.raises(DevctlError) as ei:
        load_all_services(tmp_path)
    assert ei.value.code == "CFG_004"
    assert ei.value.context["cycle"].count("->") >= 3

def test_load_config_read_text_oserror(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pathlib import Path as _Path

    target = tmp_path / "c.yaml"
    target.write_text("version: 1\nproject:\n  name: x\n", encoding="utf-8")

    def boom(*_args: object, **_kwargs: object) -> str:
        raise OSError("permission denied")

    monkeypatch.setattr(_Path, "read_text", boom)

    with pytest.raises(DevctlError) as ei:
        load_config(target)
    assert ei.value.code == "CFG_002"
    assert ei.value.context["reason"] == "file_not_found"


def test_load_config_empty_file(tmp_path: Path) -> None:
    p = tmp_path / "c.yaml"
    p.write_text("", encoding="utf-8")
    with pytest.raises(DevctlError) as ei:
        load_config(p)
    assert ei.value.code == "CFG_002"


def test_load_config_no_version(tmp_path: Path) -> None:
    p = tmp_path / "c.yaml"
    p.write_text("project:\n  name: x\n", encoding="utf-8")
    with pytest.raises(DevctlError) as ei:
        load_config(p)
    assert ei.value.code == "CFG_002"


def test_load_service_top_level_not_mapping(tmp_path: Path) -> None:
    p = tmp_path / "s.yaml"
    p.write_text("- 1\n", encoding="utf-8")
    with pytest.raises(DevctlError) as ei:
        load_service(p)
    assert ei.value.code == "CFG_002"
