from __future__ import annotations

from typing import Protocol

from devctl_core.errors import DevctlError


class Migration(Protocol):
    """Chuyển đổi config dict từ version X sang X+1."""

    from_version: int
    to_version: int

    def migrate(self, data: dict[str, object]) -> dict[str, object]: ...


_MIGRATIONS: dict[tuple[int, int], Migration] = {}


def register(migration: Migration) -> None:
    """Đăng ký migration. Key = (from_version, to_version)."""
    key = (migration.from_version, migration.to_version)
    _MIGRATIONS[key] = migration


def all_migrations() -> dict[tuple[int, int], Migration]:
    """Trả về bản sao registry."""
    return dict(_MIGRATIONS)


def reset_for_tests() -> None:
    """Xoá toàn bộ registry — chỉ dùng trong tests."""
    _MIGRATIONS.clear()


def run_migrations(
    from_version: int,
    to_version: int,
    data: dict[str, object],
) -> dict[str, object]:
    """Chạy tuần tự các migration từ `from_version` lên `to_version`.

    Raise `DevctlError(code=CFG_002)` nếu:
      - `to_version < from_version` (downgrade không hỗ trợ).
      - thiếu migration cho 1 bước.
    """
    if to_version < from_version:
        raise DevctlError(
            "CFG_002",
            context={
                "reason": "downgrade_not_supported",
                "from": str(from_version),
                "to": str(to_version),
            },
        )

    result = dict(data)
    current = from_version
    while current < to_version:
        m = _MIGRATIONS.get((current, current + 1))
        if m is None:
            raise DevctlError(
                "CFG_002",
                context={
                    "reason": "migration_path_missing",
                    "from": str(current),
                    "to": str(current + 1),
                },
            )
        result = m.migrate(result)
        current += 1
    return result


__all__ = [
    "Migration",
    "all_migrations",
    "register",
    "reset_for_tests",
    "run_migrations",
]
