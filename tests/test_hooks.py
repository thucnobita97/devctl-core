from __future__ import annotations

import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from devctl_core.cli import app
from devctl_core.errors import DevctlError
from devctl_core.hooks import discover_hooks, run_phase

runner = CliRunner()


def _make_executable(path: Path) -> None:
    os.chmod(path, 0o755)


def _write_hook(path: Path, *, exit_code: int = 0, marker: Path | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "#!/usr/bin/env bash\n"
    if marker is not None:
        body += f'echo "{exit_code}" >> "{marker}"\n'
    body += f"exit {exit_code}\n"
    path.write_text(body, encoding="utf-8")
    _make_executable(path)


# ------------------------------ discover_hooks -----------------------------


def test_discover_none(tmp_path: Path) -> None:
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()
    assert discover_hooks("svc", "pre-start", hooks_dir) == []


def test_discover_global_only(tmp_path: Path) -> None:
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()
    g = hooks_dir / "pre-start.sh"
    g.write_text("", encoding="utf-8")
    assert discover_hooks("svc", "pre-start", hooks_dir) == [g]


def test_discover_per_service_only(tmp_path: Path) -> None:
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()
    p = hooks_dir / "svc.pre-start.sh"
    p.write_text("", encoding="utf-8")
    assert discover_hooks("svc", "pre-start", hooks_dir) == [p]


def test_discover_order_global_then_service(tmp_path: Path) -> None:
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()
    g = hooks_dir / "pre-start.sh"
    p = hooks_dir / "svc.pre-start.sh"
    g.write_text("", encoding="utf-8")
    p.write_text("", encoding="utf-8")
    assert discover_hooks("svc", "pre-start", hooks_dir) == [g, p]


# -------------------------------- run_phase --------------------------------


def test_run_phase_no_hooks(tmp_path: Path) -> None:
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()
    assert run_phase("svc", "pre-start", hooks_dir) == []


def test_run_phase_missing_dir(tmp_path: Path) -> None:
    assert run_phase("svc", "pre-start", tmp_path / "nope") == []


def test_run_phase_ignore(tmp_path: Path) -> None:
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()
    marker = tmp_path / "marker"
    _write_hook(hooks_dir / "pre-start.sh", marker=marker)
    ran = run_phase("svc", "pre-start", hooks_dir, ignore_hooks=True)
    assert ran == []
    assert not marker.exists()


def test_run_phase_both_hooks_in_order(tmp_path: Path) -> None:
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()
    marker = tmp_path / "order"
    _write_hook(hooks_dir / "pre-start.sh", marker=marker)
    _write_hook(hooks_dir / "svc.pre-start.sh", marker=marker)

    ran = run_phase("svc", "pre-start", hooks_dir)
    assert len(ran) == 2
    lines = marker.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2  # cả 2 hook chạy


def test_run_phase_fail_fast(tmp_path: Path) -> None:
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()
    marker = tmp_path / "order"
    _write_hook(hooks_dir / "pre-start.sh", exit_code=1, marker=marker)
    _write_hook(hooks_dir / "svc.pre-start.sh", exit_code=0, marker=marker)

    with pytest.raises(DevctlError) as ei:
        run_phase("svc", "pre-start", hooks_dir)

    assert ei.value.code == "HOK_001"
    assert ei.value.context["exit_code"] == "1"
    # hook thứ 2 không chạy
    assert not marker.exists() or marker.read_text().count("\n") == 1


def test_run_phase_not_executable(tmp_path: Path) -> None:
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()
    h = hooks_dir / "pre-start.sh"
    h.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    os.chmod(h, 0o644)

    with pytest.raises(DevctlError) as ei:
        run_phase("svc", "pre-start", hooks_dir)
    assert ei.value.code == "HOK_002"


# ------------------------------------ CLI ---------------------------------


def test_cli_hook_run_ok(tmp_path: Path) -> None:
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()
    _write_hook(hooks_dir / "svc.pre-start.sh")

    result = runner.invoke(
        app,
        ["hook", "run", "svc", "pre-start", "--hooks-dir", str(hooks_dir)],
    )
    assert result.exit_code == 0, result.output
    assert "ran:" in result.output


def test_cli_hook_run_none(tmp_path: Path) -> None:
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()

    result = runner.invoke(
        app,
        ["hook", "run", "svc", "pre-start", "--hooks-dir", str(hooks_dir)],
    )
    assert result.exit_code == 0
    assert "no hooks for svc.pre-start" in result.output


def test_cli_hook_run_fail(tmp_path: Path) -> None:
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()
    _write_hook(hooks_dir / "svc.pre-start.sh", exit_code=2)

    result = runner.invoke(
        app,
        ["hook", "run", "svc", "pre-start", "--hooks-dir", str(hooks_dir)],
    )
    assert result.exit_code == 6
    assert "HOK_001" in result.output


def test_cli_hook_run_not_executable(tmp_path: Path) -> None:
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()
    h = hooks_dir / "svc.pre-start.sh"
    h.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    os.chmod(h, 0o644)

    result = runner.invoke(
        app,
        ["hook", "run", "svc", "pre-start", "--hooks-dir", str(hooks_dir)],
    )
    assert result.exit_code == 7
    assert "HOK_002" in result.output


def test_cli_hook_ignore(tmp_path: Path) -> None:
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()
    _write_hook(hooks_dir / "svc.pre-start.sh")

    result = runner.invoke(
        app,
        [
            "hook",
            "run",
            "svc",
            "pre-start",
            "--hooks-dir",
            str(hooks_dir),
            "--ignore-hooks",
        ],
    )
    assert result.exit_code == 0
    assert "no hooks" in result.output


def test_cli_hook_bad_phase(tmp_path: Path) -> None:
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()

    result = runner.invoke(
        app,
        ["hook", "run", "svc", "wrong-phase", "--hooks-dir", str(hooks_dir)],
    )
    assert result.exit_code == 2
    assert "CFG_002" in result.output


def test_run_phase_timeout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import subprocess

    from devctl_core import hooks as hooks_mod

    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()
    h = hooks_dir / "pre-start.sh"
    h.write_text("#!/usr/bin/env bash\nsleep 5\n", encoding="utf-8")
    _make_executable(h)

    real_run = subprocess.run

    def fake_run(*args: object, **kwargs: object) -> object:
        raise subprocess.TimeoutExpired(cmd=str(args[0]), timeout=kwargs.get("timeout", 1))

    monkeypatch.setattr(hooks_mod.subprocess, "run", fake_run)

    with pytest.raises(DevctlError) as ei:
        run_phase("svc", "pre-start", hooks_dir, timeout=0.01)
    assert ei.value.code == "HOK_001"
    assert ei.value.context["exit_code"] == "timeout"

    # Khôi phục (không thực sự cần vì pytest tự dọn monkeypatch)
    monkeypatch.setattr(hooks_mod.subprocess, "run", real_run)


def test_run_phase_oserror(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from devctl_core import hooks as hooks_mod

    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()
    h = hooks_dir / "pre-start.sh"
    h.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    _make_executable(h)

    def fake_run(*args: object, **kwargs: object) -> object:
        raise OSError("exec format error")

    monkeypatch.setattr(hooks_mod.subprocess, "run", fake_run)

    with pytest.raises(DevctlError) as ei:
        run_phase("svc", "pre-start", hooks_dir)
    assert ei.value.code == "HOK_001"
    assert ei.value.context["exit_code"] == "oserror"
