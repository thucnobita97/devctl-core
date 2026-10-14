from __future__ import annotations

_DEFAULT_SUGGESTIONS: dict[str, list[str]] = {
    "PKG_001": ["Cài devctl-core: pip install devctl-core"],
    "MAN_001": ["Chạy: devctl init", "Kiểm tra đang ở đúng project root (nơi có .devctl/)."],
    "MAN_002": ["Tạo .devctl/config.yaml hoặc chạy: devctl init"],
    "MAN_003": ["Thêm ít nhất một file .devctl/services/*.yaml."],
    "CFG_001": [
        "Kiểm tra cú pháp YAML (indent, dấu hai chấm, dấu nháy).",
        "Xem line/column ở context để định vị lỗi.",
    ],
    "CFG_002": [
        "Sửa field/value theo schema trong docs/02-CONFIG-SCHEMA.md.",
        "Chạy lại: devctl config validate",
    ],
    "CFG_003": [
        "Đổi tên service để mỗi service có `name` duy nhất.",
        "Rà soát toàn bộ file trong .devctl/services/.",
    ],
    "CFG_004": [
        "Loại bỏ phụ thuộc vòng trong `depends_on`.",
        "Sắp xếp lại service để đồ thị phụ thuộc là DAG.",
    ],
    "CFG_005": [
        "Kiểm tra tên service trong `depends_on` (phải trỏ tới service đã khai báo).",
        "Kiểm tra `env_file` và `hooks.*` có tồn tại trên đĩa.",
    ],
    "HOK_001": [
        "Chạy thủ công để xem lỗi: bash <hook>.",
        "Kiểm tra log chi tiết của hook.",
    ],
    "HOK_002": [
        "Cấp quyền thực thi: chmod +x <hook>.",
    ],
    "HOK_003": [
        "Kiểm tra hook file có tồn tại trong .devctl/hooks/.",
    ],
    "PRV_001": [
        "Kiểm tra field `provider` trong service YAML.",
        "Chạy `devctl provider list` để xem provider khả dụng.",
    ],
    "PRV_002": [
        "Tạo docker-compose.yml hoặc cập nhật `providers.docker-compose.compose_file`.",
    ],
    "PRV_003": [
        "Kiểm tra systemd unit tồn tại: `systemctl --user cat <unit>`.",
        "Kiểm tra field `service` trong service YAML (unit name).",
    ],
    "PRV_004": [
        "Kiểm tra container external đang chạy: `docker ps`.",
    ],
    "SVC_001": [
        "Kiểm tra tên service — chạy `devctl validate` để liệt kê service.",
    ],
    "SVC_002": [
        "Xem log chi tiết: `devctl logs <service>` (khi có).",
        "Kiểm tra port đã bị chiếm chưa.",
    ],
    "SVC_003": [
        "Kiểm tra service có đang chạy: `devctl status <service>`.",
    ],
    "SVC_004": [
        "Tăng `health.timeout` trong service YAML.",
        "Kiểm tra process bằng `ps aux | grep <service>`.",
    ],
    "SVC_005": [
        "Đổi port hoặc dừng process đang chiếm port.",
        "Kiểm tra với `ss -tlnp | grep <port>`.",
    ],
}

_DEFAULT_DOCS: dict[str, str] = {
    "MAN_001": "docs/02-CONFIG-SCHEMA.md",
    "MAN_002": "docs/02-CONFIG-SCHEMA.md",
    "MAN_003": "docs/02-CONFIG-SCHEMA.md",
    "CFG_001": "docs/04-ERROR-FORMAT.md#cfg_001",
    "CFG_002": "docs/02-CONFIG-SCHEMA.md",
    "CFG_003": "docs/02-CONFIG-SCHEMA.md#validation-rules",
    "CFG_004": "docs/02-CONFIG-SCHEMA.md#validation-rules",
    "CFG_005": "docs/02-CONFIG-SCHEMA.md#validation-rules",
    "HOK_001": "docs/04-ERROR-FORMAT.md#hok_001",
    "HOK_002": "docs/04-ERROR-FORMAT.md#hok_002",
    "HOK_003": "docs/04-ERROR-FORMAT.md#hok_003",
    "PRV_001": "docs/04-ERROR-FORMAT.md",
    "PRV_002": "docs/04-ERROR-FORMAT.md",
    "PRV_003": "docs/04-ERROR-FORMAT.md",
    "PRV_004": "docs/04-ERROR-FORMAT.md",
    "SVC_001": "docs/04-ERROR-FORMAT.md",
    "SVC_002": "docs/04-ERROR-FORMAT.md",
    "SVC_003": "docs/04-ERROR-FORMAT.md",
    "SVC_004": "docs/04-ERROR-FORMAT.md",
    "SVC_005": "docs/04-ERROR-FORMAT.md",
}


def default_suggestion(code: str) -> list[str]:
    """Gợi ý mặc định cho một error code. Code lạ → []."""
    return list(_DEFAULT_SUGGESTIONS.get(code, []))


class DevctlError(Exception):
    """Base exception cho mọi lỗi public của devctl-core."""

    def __init__(
        self,
        code: str,
        *,
        context: dict[str, str] | None = None,
        suggestion: list[str] | None = None,
        docs: str | None = None,
    ) -> None:
        super().__init__(code)
        self.code: str = code
        self.context: dict[str, str] = dict(context or {})
        self.suggestion: list[str] = (
            list(suggestion) if suggestion is not None else default_suggestion(code)
        )
        self.docs: str | None = docs if docs is not None else _DEFAULT_DOCS.get(code)

    def render(self) -> str:
        """Render theo format 04-ERROR-FORMAT.md."""
        lines: list[str] = [f"ERROR: {self.code}"]
        for key, value in self.context.items():
            lines.append(f"{key}: {value}")
        if self.suggestion:
            lines.append("Suggestion:")
            lines.extend(self.suggestion)
        if self.docs:
            lines.append(f"Docs: {self.docs}")
        return "\n".join(lines)

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"DevctlError(code={self.code!r}, context={self.context!r})"


__all__ = ["DevctlError", "default_suggestion"]
