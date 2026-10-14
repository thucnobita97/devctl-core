# 02 — CONFIG SCHEMA

## Mục lục
- [.devctl/config.yaml](#devctlconfigyaml)
- [.devctl/services/*.yaml](#devctlservicesyaml)
- [.devctl/session.yaml](#devctlsessionyaml)
- [Pydantic models](#pydantic-models)
- [Validation rules](#validation-rules)
- [Migration path](#migration-path)

## .devctl/config.yaml

```yaml
version: 1

project:
  name: menu-platform
  root: .

paths:
  runtime: .devctl/runtime
  logs: .devctl/logs
  hooks: .devctl/hooks

defaults:
  provider: docker-compose
  health_timeout: 30
  stop_timeout: 15

providers:
  docker-compose:
    compose_file: docker-compose.yml
    project_name: menu-platform
  docker-external:
    detect_only: true
  native:
    pid_dir: .devctl/runtime
  systemd:
    scope: user
  external:
    detect_only: true

session:
  docs_dir: docs
  handoff_dir: handoff-part-1
  files:
    roadmap: 00-ROADMAP.md
    resume: 01-RESUME.md
    patch_rules: 02-PATCH-RULES.md
    decisions: 03-DECISIONS.md
    conventions: 04-CONVENTIONS.md
    changelog: 05-CHANGELOG.md
    known_issues: 06-KNOWN-ISSUES.md
    glossary: 07-GLOSSARY.md
```

## .devctl/services/*.yaml

### postgres.yaml

```yaml
name: postgres
provider: docker-compose
service: postgres
health:
  type: tcp
  host: localhost
  port: 5432
  timeout: 30
depends_on: []
hooks:
  post-start: postgres.post-start.sh
```

### redis.yaml

```yaml
name: redis
provider: docker-compose
service: redis
health:
  type: exec
  command: redis-cli ping
  expect: PONG
depends_on: []
```

### minio.yaml

```yaml
name: minio
provider: docker-compose
service: minio
health:
  type: http
  url: http://localhost:9000/minio/health/live
  expect_status: 200
depends_on: []
```

### backend.yaml

```yaml
name: backend
provider: native
command: uvicorn app.main:app --reload --port 8000
cwd: backend
env_file: backend/.env
health:
  type: http
  url: http://localhost:8000/health
  expect_status: 200
  timeout: 60
depends_on:
  - postgres
  - redis
  - minio
```

### worker.yaml

```yaml
name: worker
provider: native
command: python -m app.worker
cwd: backend
env_file: backend/.env
health:
  type: process
depends_on:
  - postgres
  - redis
```

### frontend.yaml

```yaml
name: frontend
provider: native
command: npm run dev
cwd: frontend
health:
  type: http
  url: http://localhost:3000
  expect_status: 200
  timeout: 60
depends_on:
  - backend
```

## .devctl/session.yaml

```yaml
version: 1

docs:
  roadmap: docs/00-ROADMAP.md
  resume: docs/01-RESUME.md
  patch_rules: docs/02-PATCH-RULES.md
  decisions: docs/03-DECISIONS.md
  conventions: docs/04-CONVENTIONS.md
  changelog: docs/05-CHANGELOG.md
  known_issues: docs/06-KNOWN-ISSUES.md
  glossary: docs/07-GLOSSARY.md

handoff:
  sections:
    - UPDATE 00-ROADMAP
    - UPDATE 01-RESUME
    - UPDATE 03-DECISIONS
    - UPDATE 05-CHANGELOG
    - UPDATE 06-KNOWN-ISSUES
    - PROMPT CHO SESSION

prompt:
  template: .devctl/templates/session-prompt.md
  language: vi
```

## Pydantic models

```python
from pydantic import BaseModel, Field
from typing import Literal

class ProjectCfg(BaseModel):
    name: str
    root: str = "."

class PathsCfg(BaseModel):
    runtime: str
    logs: str
    hooks: str

class DefaultsCfg(BaseModel):
    provider: str
    health_timeout: int = 30
    stop_timeout: int = 15

class Config(BaseModel):
    version: Literal[1]
    project: ProjectCfg
    paths: PathsCfg
    defaults: DefaultsCfg
    providers: dict
    session: dict

class HealthCfg(BaseModel):
    type: Literal["tcp", "http", "exec", "process"]
    timeout: int = 30
    host: str | None = None
    port: int | None = None
    url: str | None = None
    command: str | None = None
    expect: str | None = None
    expect_status: int | None = None

class ServiceCfg(BaseModel):
    name: str
    provider: Literal["docker-compose", "docker-external", "native", "systemd", "external"]
    service: str | None = None
    command: str | None = None
    cwd: str | None = None
    env_file: str | None = None
    health: HealthCfg | None = None
    depends_on: list[str] = Field(default_factory=list)
    hooks: dict[str, str] = Field(default_factory=dict)
```

## Validation rules

| Rule | Mô tả |
|------|-------|
| `version` | Phải là `1`; từ chối nếu khác. |
| `name` (service) | Unique, `[a-z][a-z0-9-]*`. |
| `provider` | Thuộc 5 giá trị hợp lệ. |
| `depends_on` | Phải trỏ tới service đã khai báo; không cycle. |
| `health.type` | Bắt buộc field tương ứng (`tcp`→host/port, `http`→url). |
| `env_file` | File phải tồn tại nếu khai báo. |
| `hooks.*` | File phải tồn tại trong `.devctl/hooks/`. |

## Migration path

- Schema có field `version`. Khi bump:
  1. Thêm `migrations/<from>_to_<to>.py` trong `devctl-core`.
  2. CLI `devctl config migrate` chạy tuần tự.
  3. Ghi changelog + cập nhật docs.
- Không hỗ trợ downgrade tự động; user backup trước.
