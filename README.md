# devctl-core

Library + CLI quản lý service dev cho project.

## Cài đặt

```bash
uv add devctl-core
# hoặc
pip install devctl-core
```

## Lệnh

### `devctl init [ROOT]`

Sinh skeleton `.devctl/` gồm `config.yaml`, `session.yaml`, `services/`,
`hooks/`, `templates/`. **Idempotent**: file đã có sẽ bị skip. Dùng
`--force` để ghi đè.

```bash
devctl init
devctl init ./my-project
devctl init --force
```

### `devctl validate [--config-dir .devctl]`

Validate `.devctl/`: `config.yaml` + `session.yaml` + `services/*.yaml`.

```bash
devctl validate
devctl validate --config-dir path/to/.devctl
```

Exit code:

| Code | Ý nghĩa |
|------|---------|
| 0 | OK |
| 1 | CFG_001 — YAML parse lỗi |
| 2 | CFG_002 — schema invalid |
| 3 | CFG_003 — service trùng tên |
| 4 | CFG_004 — `depends_on` cycle |
| 5 | CFG_005 — tham chiếu dangling |
| 10 | MAN_001 — `.devctl/` thiếu |
| 11 | MAN_002 — `config.yaml` thiếu |
| 12 | MAN_003 — `services/` rỗng |
| 6 | HOK_001 — hook exit ≠ 0 |
| 7 | HOK_002 — hook không executable |
| 8 | HOK_003 — hook không tồn tại |
| 20 | PRV_001 — provider không hỗ trợ |
| 21 | PRV_002 — compose file thiếu |
| 30 | SVC_001 — service không tồn tại |
| 31 | SVC_002 — start fail |
| 32 | SVC_003 — stop fail |
| 99 | lỗi khác |

### `devctl hook run <SERVICE> <PHASE>`

Chạy hook cho `SERVICE` ở `PHASE` (fail-fast). Phases:
`pre-start`, `post-start`, `pre-stop`, `post-stop`.

Thứ tự chạy:
1. `.devctl/hooks/{phase}.sh` (global)
2. `.devctl/hooks/{service}.{phase}.sh` (per-service)

```bash
devctl hook run postgres pre-start
devctl hook run backend post-start --hooks-dir path/to/hooks
devctl hook run postgres pre-start --ignore-hooks
devctl hook run postgres pre-start --timeout 30
```

Exit code: `6` HOK_001 (hook fail), `7` HOK_002 (không executable),
`8` HOK_003 (không tồn tại).

### `devctl provider list`

Liệt kê các provider đã đăng ký (`native`, `docker-compose`).

```bash
devctl provider list
```

### `devctl start <SERVICE>`

Chạy pre-start hook → `provider.start()` → post-start hook.

```bash
devctl start postgres
devctl start backend --config-dir path/to/.devctl
devctl start backend --ignore-hooks
```

### `devctl stop <SERVICE>`

Chạy pre-stop hook → `provider.stop()` → post-stop hook.

```bash
devctl stop backend
```

## Error codes

Xem `04-ERROR-FORMAT.md` cho bảng đầy đủ.

## Phát triển

```bash
uv sync
uv run ruff check .
uv run mypy src
uv run pytest
```
