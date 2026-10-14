# 00 — DECISIONS

## Mục lục
- [Bảng quyết định](#bảng-quyết-định)
- [Ghi chú](#ghi-chú)

## Bảng quyết định

| # | Câu hỏi | Quyết định | Lý do |
|---|---------|------------|-------|
| 1 | Package manager & build backend? | `uv` + `hatchling` | uv nhanh, lock chuẩn; hatchling nhẹ, hỗ trợ PEP 621 tốt. |
| 2 | Python version pinning? | `requires-python = ">=3.12,<3.13"` | Tránh drift; 3.13 chưa cần. |
| 3 | Monorepo hay multi-repo? | 2 repo: `devctl-core`, `devctl-cli` | Tách trách nhiệm, CLI có thể thay đổi độc lập; core là library ổn định. |
| 4 | Config format? | YAML | Human-friendly, hỗ trợ comment, ecosystem rộng. |
| 5 | Config root? | `.devctl/` trong project | Cô lập với code nghiệp vụ; dễ backup/gitignore từng phần. |
| 6 | Provider registration? | Registry + entry point (`importlib.metadata`) | Cho phép mở rộng provider ngoài core; không hard-code. |
| 7 | Service definition granularity? | 1 file YAML / service (`.devctl/services/*.yaml`) | Dễ diff, dễ review, không conflict khi nhiều người sửa. |
| 8 | Runtime state (PID, log)? | `.devctl/runtime/{svc}.pid`, `.devctl/logs/{svc}.log` | Tách khỏi config; thêm vào `.gitignore`. |
| 9 | Hook naming? | `{phase}.sh` (global), `{svc}.{phase}.sh` (per-service) | Rõ ràng, sortable, dễ glob. |
| 10 | Hook failure behavior? | Fail-fast, dừng chuỗi hook | Tránh trạng thái nửa vời; user có thể `--ignore-hooks` khi cần. |
| 11 | Session docs location? | `handoff-part-N/` với 9 file cố định | Versioned theo part; dễ archive. |
| 12 | Error code scheme? | `<PREFIX>_<NNN>` (VD: `CFG_001`) | Dễ parse, dễ tra cứu, có namespace. |
| 13 | Versioning? | SemVer: `0.x.y-dev` → `1.0.0-rcN` → `1.0.0` | Theo milestone; rõ ràng cho consumer. |
| 14 | Testing strategy? | pytest + coverage ≥80% core; ruff + mypy strict | Chất lượng library; CLI test bằng `typer.testing.CliRunner`. |
| 15 | Distribution? | Local editable → Git URL → private PyPI | Lộ trình tăng dần, không phức tạp hoá sớm. |

## Ghi chú
- GHICHU: Câu 1 — nếu team chưa quen `uv`, có thể dùng `pip-tools` + `setuptools`; nhưng đã chốt `uv` để đồng bộ tooling.
- GHICHU: Câu 6 — entry point chỉ áp dụng từ `0.3.0`; trước đó dùng registry nội bộ.
