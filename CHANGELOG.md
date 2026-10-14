# Changelog

All notable changes to `devctl-core` are documented here.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning: [SemVer](https://semver.org/).

## [Unreleased]

## [0.2.0.dev0] - 2026-10-14

Milestone đầu tiên của library: config loader, hook executor, provider
registry, health check, runtime state, observability, và schema migration
framework.

### Added

**Errors**
- `devctl_core.errors.DevctlError` + `default_suggestion`.
- Render theo `docs/04-ERROR-FORMAT.md` (`ERROR: <CODE>` + `key: value` + `Suggestion:` + `Docs:`).
- Error code groups: `MAN_*` (001..003), `CFG_*` (001..005), `HOK_*` (001..003),
  `PRV_*` (001..004), `SVC_*` (001..005).

**Config**
- Pydantic v2 models: `Config`, `ProjectCfg`, `PathsCfg`, `DefaultsCfg`,
  `SessionCfg`, `SessionFilesCfg`, `HealthCfg`, `ServiceCfg`,
  `SessionConfig`, `SessionDocCfg`, `SessionHandoffCfg`, `SessionPromptCfg`.
- Loader: `load_config`, `load_service`, `load_all_services`, `load_session`.
- `validate_service_references` — `CFG_005` cho dangling refs
  (`depends_on` / `env_file` / `hooks.*`).
- Cycle detection DFS 3-màu — `CFG_004`.

**Hooks**
- `discover_hooks(service, phase, hooks_dir)` — global trước, per-service sau.
- `run_phase(...)` — fail-fast, 4 phase (`pre-start` / `post-start` / `pre-stop` / `post-stop`).
- Exit code mới: `HOK_001` (fail), `HOK_002` (không executable), `HOK_003` (không tồn tại).

**Providers**
- Registry nội bộ + `Provider` Protocol + `ProviderContext`.
- `native`: subprocess + PID file; stop `SIGTERM` → `SIGKILL` sau `stop_timeout`.
- `docker-compose`: `docker compose -f <file> {up -d, stop, ps -q}`.
- `systemd`: `systemctl [--user|--system] {cat, start, stop, is-active}`.
- `external`, `docker-external`: detect-only (start/stop raise `PRV_001`).

**Health**
- `check(svc, ctx)` cho 4 type: `tcp`, `http`, `exec`, `process`.
- Raise `SVC_004` khi fail.

**Runtime**
- `pid_file`, `log_file`, `ensure_runtime_dirs`.
- Native provider redirect stdout/stderr → `.devctl/logs/{svc}.log`.

**Migrations**
- `Migration` Protocol + registry + `run_migrations(from, to, data)`.
- Template `migrations/_template.py`.
- CLI `devctl config migrate [--target N] [--dry-run]` với backup `.bak`.

**Info / Observability**
- `collect_info(config_dir=None)` — core version, python, platform, providers, paths.
- CLI `--json` cho `validate`, `status`; command `info [--json]`.

**CLI (Typer)**
- `devctl validate [--config-dir] [--json]`
- `devctl init [ROOT] [--force]`
- `devctl start <SVC> [--ignore-hooks] [--skip-health]`
- `devctl stop <SVC> [--ignore-hooks]`
- `devctl restart <SVC> [--ignore-hooks] [--skip-health]`
- `devctl status [SVC] [--json]`
- `devctl ps`
- `devctl logs <SVC> [--tail N] [--follow]`
- `devctl hook run <SVC> <PHASE> [--hooks-dir] [--ignore-hooks] [--timeout]`
- `devctl provider list`
- `devctl config migrate [--target N] [--dry-run]`
- `devctl info [--json]`

**Exit code map**
- `MAN_*` (10..12), `CFG_*` (1..5), `HOK_*` (6..8), `PRV_*` (20..23),
  `SVC_*` (30..34), unknown = 99.

### Changed

- Dev dependencies gộp về `[dependency-groups].dev` (PEP 735).
- Build backend: `hatchling` + `uv`.
- `types-PyYAML` thêm vào dev group (mypy strict).

### Documentation

- `README.md`: install, commands, exit-code table.
- `docs/00-DECISIONS.md`, `docs/02-CONFIG-SCHEMA.md`, `docs/04-ERROR-FORMAT.md`.

### Tests

- 189 tests, coverage 96%.
- `ruff check` + `mypy --strict` clean.

[Unreleased]: https://github.com/thucnobita97/devctl-core/compare/v0.2.0.dev0...HEAD
[0.2.0.dev0]: https://github.com/thucnobita97/devctl-core/releases/tag/v0.2.0.dev0
