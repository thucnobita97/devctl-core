"""Template cho migration vX → vX+1.

Copy file này thành `v1_to_v2.py` khi bump schema version, đổi tên class
và implement `migrate()`. Sau đó đăng ký trong `migrations/__init__.py`:

    from devctl_core.migrations.v1_to_v2 import V1ToV2
    register(V1ToV2())

Ví dụ:

    class V1ToV2:
        from_version = 1
        to_version = 2

        def migrate(self, data):
            data = dict(data)
            data["version"] = 2
            # Đổi tên field:
            # project = dict(data.get("project", {}))
            # if "root" in project:
            #     project["base_path"] = project.pop("root")
            # data["project"] = project
            return data
"""
from __future__ import annotations

__all__: list[str] = []
