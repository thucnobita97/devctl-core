from __future__ import annotations

import shutil
import socket
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from devctl_core.config.models import ServiceCfg

Status = Literal["ok", "warn", "fail"]

ENV_PYTHON = "ENV_001"
ENV_WRITE = "ENV_002"
ENV_PORT = "ENV_003"
ENV_TOOL = "ENV_004"
ENV_DAEMON = "ENV_005"

EXIT_DOCTOR_FAIL = 40

MIN_PYTHON = (3, 12)
MAX_PYTHON_EXCL = (3, 13)


@dataclass
class CheckResult:
    name: str
    status: Status
    code: str | None = None
    detail: str | None = None
    suggestion: str | None = None

    @property
    def ok(self) -> bool:
        return self.status != "fail"


# ----------------------------- individual checks -------------------------


def _check_python() -> CheckResult:
    v = sys.version_info[:2]
    pretty = f"{sys.version_info[0]}.{sys.version_info[1]}.{sys.version_info[2]}"
    if MIN_PYTHON <= v < MAX_PYTHON_EXCL:
        return CheckResult(name="python", status="ok", detail=pretty)
    return CheckResult(
        name="python",
        status="fail",
        code=ENV_PYTHON,
        detail=(
            f"{pretty} "
            f"(cần >={MIN_PYTHON[0]}.{MIN_PYTHON[1]},<{MAX_PYTHON_EXCL[0]}.{MAX_PYTHON_EXCL[1]})"
        ),
        suggestion=f"Cài Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]} rồi chạy lại.",
    )


def _check_tool(name: str) -> CheckResult:
    path = shutil.which(name)
    if path:
        return CheckResult(name=name, status="ok", detail=path)
    return CheckResult(
        name=name,
        status="warn",
        code=ENV_TOOL,
        detail="không tìm thấy trong PATH",
        suggestion=f"Cài `{name}` nếu muốn dùng tính năng tương ứng.",
    )


def _check_docker_daemon() -> CheckResult:
    if shutil.which("docker") is None:
        return CheckResult(
            name="docker-daemon",
            status="warn",
            code=ENV_DAEMON,
            detail="docker CLI không có trong PATH",
        )
    try:
        r = subprocess.run(  # noqa: S603
            ["docker", "info"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return CheckResult(
            name="docker-daemon",
            status="warn",
            code=ENV_DAEMON,
            detail=f"không gọi được docker info: {exc}",
            suggestion="Khởi động docker daemon.",
        )
    if r.returncode != 0:
        return CheckResult(
            name="docker-daemon",
            status="warn",
            code=ENV_DAEMON,
            detail="docker daemon không phản hồi",
            suggestion=(
                "Chạy `docker info` để xem chi tiết; "
                "khởi động Docker Desktop / systemctl start docker."
            ),
        )
    return CheckResult(name="docker-daemon", status="ok")


def _check_git(project_root: Path) -> CheckResult:
    git_dir = project_root / ".git"
    if git_dir.exists():
        return CheckResult(name="git-repo", status="ok", detail=str(project_root))
    return CheckResult(
        name="git-repo",
        status="warn",
        code=ENV_TOOL,
        detail=f"{project_root} không phải git repo",
        suggestion="Chạy `git init` nếu muốn theo dõi thay đổi.",
    )


def _check_write_dir(config_dir: Path) -> CheckResult:
    try:
        config_dir.mkdir(parents=True, exist_ok=True)
        probe = config_dir / ".doctor-probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError as exc:
        return CheckResult(
            name="write-config-dir",
            status="fail",
            code=ENV_WRITE,
            detail=f"không ghi được {config_dir}: {exc}",
            suggestion=f"Kiểm tra quyền: ls -ld {config_dir}",
        )
    return CheckResult(name="write-config-dir", status="ok", detail=str(config_dir))


def _port_free(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((host, port))
        except OSError:
            return False
    return True


def _extract_host_port(entry: str) -> int | None:
    """Parse 'HOST:CONTAINER' / 'IP:HOST:CONTAINER' / 'PORT'."""
    parts = entry.split(":")
    try:
        if len(parts) == 1:
            return int(parts[0])
        # last part = container port; second-to-last = host port
        return int(parts[-2])
    except (ValueError, IndexError):
        return None


def _check_ports(services: dict[str, ServiceCfg]) -> list[CheckResult]:
    results: list[CheckResult] = []
    seen: set[tuple[str, int]] = set()

    for name, svc in services.items():
        if svc.health is None or svc.health.port is None:
            continue
        port = svc.health.port
        key = (name, port)
        if key in seen:
            continue
        seen.add(key)
        if _port_free(port):
            results.append(
                CheckResult(
                    name=f"port:{name}:{port}",
                    status="ok",
                )
            )
        else:
            results.append(
                CheckResult(
                    name=f"port:{name}:{port}",
                    status="fail",
                    code=ENV_PORT,
                    detail=f"port {port} đang bị chiếm",
                    suggestion=(
                        f"Kiểm tra: ss -tlnp | grep {port} — hoặc đổi port trong service YAML."
                    ),
                )
            )
    return results


# ---------------------------- orchestrator -------------------------------


def check_environment(
    *,
    project_root: Path | None = None,
    config_dir: Path | None = None,
    services: dict[str, ServiceCfg] | None = None,
) -> list[CheckResult]:
    """Chạy tất cả environment check. Trả list CheckResult (theo thứ tự cố định)."""
    results: list[CheckResult] = [_check_python()]
    results.append(_check_tool("uv"))
    results.append(_check_tool("systemctl"))
    results.append(_check_tool("docker"))
    results.append(_check_docker_daemon())

    if project_root is not None:
        results.append(_check_git(project_root))

    if config_dir is not None:
        results.append(_check_write_dir(config_dir))

    if services:
        results.extend(_check_ports(services))

    return results


__all__ = [
    "ENV_DAEMON",
    "ENV_PORT",
    "ENV_PYTHON",
    "ENV_TOOL",
    "ENV_WRITE",
    "EXIT_DOCTOR_FAIL",
    "CheckResult",
    "check_environment",
]
