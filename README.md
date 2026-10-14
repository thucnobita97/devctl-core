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
| 33 | SVC_004 — health timeout |
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

Liệt kê các provider đã đăng ký.

Providers:
- `native` — chạy subprocess, quản lý PID file. Hỗ trợ start/stop/status.
- `docker-compose` — gọi `docker compose`. Hỗ trợ start/stop/status.
- `systemd` — gọi `systemctl [--user|--system]`. Hỗ trợ start/stop/status.
- `external` — detect-only, không start/stop được (raise `PRV_001`).
- `docker-external` — detect-only, check `docker ps`. Không start/stop được.

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

### `devctl status [SERVICE]`

In trạng thái service: provider, running/stopped, health.
Bỏ trống SERVICE → list toàn bộ. Exit code `33` nếu health fail.

```bash
devctl status
devctl status backend
```

### `devctl restart <SERVICE>`

Restart service: nếu đang chạy → stop (cùng hooks), rồi start (cùng hooks + health).
Nếu không chạy → start bình thường.

```bash
devctl restart backend
devctl restart backend --ignore-hooks --skip-health
```

### `devctl ps`

Liệt kê nhanh `service\tstate`. Không gọi health check.

```bash
devctl ps
```

### `devctl logs <SERVICE>`

Xem log service (`.devctl/logs/{svc}.log`).

```bash
devctl logs backend
devctl logs backend --tail 100
devctl logs backend --follow
```

### Health check

Khi `devctl start`, health check chạy tự động sau khi provider start
(poll tới `health.timeout` giây). Bỏ qua bằng `--skip-health`.

### `devctl info [--json]`

In thông tin runtime: version core, python, platform, providers, config paths.

```bash
devctl info
devctl info --json
```

### `--json` cho `validate` và `status`

```bash
devctl validate --json
# {"ok": true, "errors": []}

devctl status --json
# [{"name": "app", "provider": "native", "state": "running",
#   "health": "healthy", "pid": 12345}]
```

### `devctl config migrate`

Migrate `.devctl/config.yaml` lên version mới (backup `.bak` trước khi ghi).

```bash
devctl config migrate --dry-run       # in diff
devctl config migrate                 # backup + ghi
devctl config migrate --target 2      # đích cụ thể
```

Chi tiết framework: xem `docs/02-CONFIG-SCHEMA.md#migration-path`.

## Error codes

Xem `04-ERROR-FORMAT.md` cho bảng đầy đủ.

## Phát triển

```bash
uv sync
uv run ruff check .
uv run mypy src
uv run pytest
```
