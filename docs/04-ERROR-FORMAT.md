# 04 — ERROR FORMAT

## Mục lục
- [Format chuẩn](#format-chuẩn)
- [Bảng error codes](#bảng-error-codes)
- [Ví dụ](#ví-dụ)
- [Mapping error → suggestion](#mapping-error--suggestion)
- [AI parsing guide](#ai-parsing-guide)

## Format chuẩn

    ERROR: <CODE>
    <key>: <value>
    Suggestion:
    <step1>
    <step2>
    Docs: <url>

- `<CODE>`: `<PREFIX>_<NNN>`, uppercase.
- `<key>: <value>`: 1..N dòng context.
- `Suggestion:`: 1..N bước copy-paste được.
- `Docs:`: link nội bộ hoặc file path.

## Bảng error codes

| Code | Nhóm | Mô tả |
|------|------|-------|
| `PKG_001` | package | devctl-core chưa cài |
| `PKG_002` | package | version CLI ≠ core |
| `PKG_003` | package | dependency thiếu (pyyaml, pydantic…) |
| `MAN_001` | manifest | không tìm thấy `.devctl/` |
| `MAN_002` | manifest | `config.yaml` thiếu |
| `MAN_003` | manifest | `services/` rỗng |
| `CFG_001` | config | YAML parse lỗi |
| `CFG_002` | config | schema invalid (Pydantic) |
| `CFG_003` | config | service trùng tên |
| `CFG_004` | config | `depends_on` cycle |
| `CFG_005` | config | tham chiếu dangling (`depends_on`/`env_file`/`hooks`) |
| `PRV_001` | provider | provider không hỗ trợ |
| `PRV_002` | provider | docker-compose file thiếu |
| `PRV_003` | provider | systemd unit không tồn tại |
| `PRV_004` | provider | container external không thấy |
| `SVC_001` | service | service không tồn tại |
| `SVC_002` | service | start fail |
| `SVC_003` | service | stop fail |
| `SVC_004` | service | health timeout |
| `SVC_005` | service | port đã bị chiếm |
| `SES_001` | session | docs thiếu |
| `SES_002` | session | handoff section thiếu |
| `SES_003` | session | template không tồn tại |
| `HOK_001` | hook | hook exit ≠ 0 |
| `HOK_002` | hook | hook không executable |
| `HOK_003` | hook | hook không tồn tại |

## Ví dụ

### CFG_002

    ERROR: CFG_002
    file: .devctl/services/backend.yaml
    field: health.type
    value: "grpc"
    Suggestion:
    Sửa health.type thành một trong: tcp, http, exec, process
    Chạy lại: devctl status backend
    Docs: .devctl/README.md#health

### SVC_004

    ERROR: SVC_004
    service: backend
    url: http://localhost:8000/health
    timeout: 60
    Suggestion:
    Kiểm tra log: devctl logs backend
    Kiểm tra process: ps aux | grep uvicorn
    Tăng timeout trong .devctl/services/backend.yaml nếu cần
    Docs: .devctl/README.md#health

### HOK_001

    ERROR: HOK_001
    hook: postgres.post-start.sh
    exit_code: 1
    Suggestion:
    Chạy thủ công: bash .devctl/hooks/postgres.post-start.sh
    Kiểm tra quyền: chmod +x .devctl/hooks/postgres.post-start.sh
    Docs: .devctl/README.md#hooks

## Mapping error → suggestion

| Code | Suggestion chính |
|------|------------------|
| `PKG_001` | `pip install devctl-core` |
| `PKG_002` | `pip install -U devctl-core devctl-cli` |
| `MAN_001` | `devctl init` |
| `CFG_001` | Chỉ ra line/column từ PyYAML |
| `CFG_002` | Chỉ ra field lỗi từ Pydantic |
| `PRV_002` | Kiểm tra `compose_file` trong config |
| `SVC_002` | `devctl logs <svc>` + kiểm tra port |
| `SVC_004` | Tăng `health.timeout` |
| `SES_001` | Liệt kê docs thiếu, gợi ý tạo |
| `HOK_002` | `chmod +x` |

## AI parsing guide

1. Match dòng đầu `^ERROR: ([A-Z]+_\d{3})$`.
2. Parse các dòng `key: value` tiếp theo vào dict.
3. Bỏ qua `Suggestion:` đến `Docs:`.
4. Đọc steps trong `Suggestion:` để đề xuất hành động.
5. Nếu code thuộc `CFG_*` → yêu cầu user paste nội dung file.
6. Nếu `SVC_004` → hỏi user chạy `devctl logs`.
