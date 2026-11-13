# Photo Backup System

[![CI](https://github.com/borisvu/photo-backup/actions/workflows/ci.yml/badge.svg)](https://github.com/borisvu/photo-backup/actions/workflows/ci.yml)

A Python-based automated backup solution that monitors a local photo collection on an external SSD and maintains synchronized copies on Wasabi S3 storage, following the 3-2-1 backup methodology.

## Project Overview

This system provides:

- **Automated Monitoring**: Detects when external SSD is connected and triggers backup
- **S3 Storage**: Syncs photos to Wasabi S3-compatible storage
- **Integrity Verification**: Validates backup integrity and provides auto-repair
- **Comprehensive Logging**: Detailed logging and progress reporting
- **Flexible Configuration**: Support for multiple credential providers and storage backends
- **Test Mode**: Local testing with MinIO for development without Wasabi costs

Under the hood it drives [rclone](https://rclone.org/) for transfers and listing; the Python layer handles configuration, credentials, scheduling, state, verification and logging.

## Requirements

- **Python 3.13+** (uv installs it for you if missing)
- **[uv](https://docs.astral.sh/uv/)** — manages the virtualenv and dependencies
- **rclone** — required for all S3 operations
- **Docker** — only for the functional test suite (MinIO container)
- **Make** — optional, for the convenience targets
- **1Password CLI** — optional credential provider

## Quick Start

```bash
git clone https://github.com/borisvu/photo-backup.git && cd photo-backup && uv sync
```

`uv sync` creates `.venv/` from `pyproject.toml` + `uv.lock` and installs the project as editable, so the `photo-backup` command is available via `uv run` (or directly after `source .venv/bin/activate`).

```bash
uv run photo-backup --help          # list commands
uv run photo-backup check-deps      # rclone & system checks
uv run photo-backup setup-config    # copy config.yaml.example into your user config dir
uv run photo-backup validate        # validate configuration
```

For a real Wasabi deployment (credentials, launchd service), follow the [Production Setup Guide](docs/PRODUCTION_SETUP.md).

## Basic Usage

| Command | What it does |
|---|---|
| `photo-backup status` | Service health, last sync/verify, drive state (`--json`, `-v`) |
| `photo-backup sync` | Run a backup sync now (`-v` for detail) |
| `photo-backup verify` | Compare local vs remote by size + existence (`--repair`, `--save-report`) |
| `photo-backup logs` | View logs (`--tail N`, `--errors`, `--follow`, `--level`) |
| `photo-backup start` / `stop` / `restart` | Manage the backup service (`start --foreground` / `--background`) |
| `photo-backup config` | Show the effective configuration |
| `photo-backup test-auth` | Check credentials and S3 access |

Global flags go **before** the subcommand:

```bash
photo-backup --test-mode sync      # MinIO on localhost:9000, temp paths, debug logging
photo-backup --dry-run sync        # show what would happen
```

`./check-status.sh` (repo root) gives a one-screen health check of the production service. Day-to-day workflows and troubleshooting are in the [User Guide](docs/USER_GUIDE.md).

## Development

```bash
uv sync                      # == make install-dev
uv run pre-commit install    # optional: ruff + mypy on every commit
```

| Target | Runs |
|---|---|
| `make test` | All tests (`uv run pytest tests/ -v`) |
| `make test-unit` / `make test-integration` / `make test-functional` | One suite |
| `make lint` | `ruff check` + `mypy photo_backup/` |
| `make lint-fix` | `ruff check --fix` |
| `make format` | `ruff format` |
| `make check` | `ruff format --check` (formatting gate) |
| `make pre-commit` | `format` + `lint` + `test` |
| `make clean` | Remove caches and build artefacts |

Any tool can be run ad hoc with `uv run`, e.g. `uv run pytest tests/unit -q` or `uv run pytest tests/ --cov=photo_backup --cov-report=html`. Ruff and mypy are configured in `pyproject.toml`; pre-commit hooks in `.pre-commit-config.yaml`.

### Tests

- **Unit** (`tests/unit/`) — fast, mock-based, no external services.
- **Integration** (`tests/integration/`) — component interactions, no external services.
- **Functional** (`tests/functional/`) — end-to-end against a real S3 server. **Needs Docker and `rclone` on `PATH`.** The tests start and stop their own MinIO container using the digest-pinned image in `tests/fixtures/minio.py` (`pgsty/minio@sha256:…`, since the official MinIO image is no longer pullable from Docker Hub). Override with `MINIO_TEST_IMAGE=<image>`.

CI (`.github/workflows/ci.yml`) runs `ruff check`, `ruff format --check` and `mypy`, then the unit, integration and functional suites on Ubuntu with Docker and rclone. Installer tests (`-m launchd`, which need `launchctl`) are skipped there and run in a separate macOS job.

### Test mode and a manual MinIO

`--test-mode` swaps in MinIO at `localhost:9000` (`minioadmin`/`minioadmin`, plain HTTP), source `/tmp/photo-backup-test-photos`, logs under `/tmp/photo-backup-test/`, shortened timers, and skips 1Password. To try it by hand, start MinIO with the same pinned image the tests use:

```bash
docker run -d --name photo-backup-minio -p 9000:9000 -p 9090:9001 \
  -e MINIO_ROOT_USER=minioadmin -e MINIO_ROOT_PASSWORD=minioadmin \
  "$(uv run python -c 'from tests.fixtures.minio import MINIO_IMAGE; print(MINIO_IMAGE)')" \
  server /data --console-address :9001

uv run photo-backup --test-mode sync      # console: http://localhost:9090
docker rm -f photo-backup-minio           # clean up
```

### End-to-end verification skill

`.agents/skills/verify-photo-backup/` is a project-local Claude/Codex skill that runs the real daemon from the working tree against a TLS MinIO stand-in for Wasabi and drives `sync` / `verify --repair` / `status`, capturing bucket, state and log evidence. Use it to prove a behaviour change end to end; see its `SKILL.md`.

### Troubleshooting

- **Functional tests can't reach MinIO** — check `docker ps`, and that nothing else holds port 9000 (`lsof -i :9000`).
- **Stale test state** — `rm -rf /tmp/photo-backup-test/`.
- **Broken environment** — `rm -rf .venv && uv sync`.
- **Dependency changes** — edit `pyproject.toml`, then `uv lock` and `uv sync`.

## Repository Layout

```
photo-backup/
├── photo_backup/          # Application package (CLI, backup engine, config, credentials,
│                          #   logger, monitor, service)
├── tests/                 # unit/, integration/, functional/, fixtures/
├── scripts/               # Performance test script + manual test runbooks
├── docs/                  # Architecture, user, production and key-rotation guides
├── install.py             # Installer: prerequisite checks, directories, launchd setup
├── check-status.sh        # Quick production health check
├── config.yaml.example    # Configuration template
├── pyproject.toml         # Project metadata, dependencies, ruff/mypy config
├── uv.lock                # Locked dependency versions
├── pytest.ini             # Pytest configuration
├── Makefile               # Convenience targets (wrap uv run)
├── .pre-commit-config.yaml
├── CHANGELOG.md
└── LICENSE
```

## Documentation

- [User Guide](docs/USER_GUIDE.md) — everyday commands, workflows, troubleshooting
- [Production Setup](docs/PRODUCTION_SETUP.md) — deploying against Wasabi as a launchd service
- [Key Rotation](docs/KEY_ROTATION.md) — rotating Wasabi keys and reloading the service
- [Architecture](docs/ARCHITECTURE.md) — system design and technical specification
- [Performance test](scripts/PERFORMANCE_TEST.md) and [error-recovery test](scripts/ERROR_RECOVERY_TEST.md) runbooks
- [Changelog](CHANGELOG.md)

## License

MIT License — see [LICENSE](LICENSE).
