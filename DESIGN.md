# Design: shuati-agent CLI Transformation

## Overview

Transform `shuati-agent` from a web-only Flask app into a dual-mode CLI + Web application. Users interact primarily via CLI (`shuati` command) for all operations; the web UI becomes an optional visualization/print辅助工具.

## Reference Design: bilibili-cli

Key patterns borrowed from bilibili-cli:
- Click-based CLI with command groups
- `--yaml` / `--json` structured output for AI agent friendliness
- Unified error envelope schema
- `SKILL.md` for AI agent integration
- `pyproject.toml` for package installation (`shuati` command)

## Architecture

### New Directory Structure

```
shuati-agent/
├── pyproject.toml              # Package config + CLI entry point
├── src/shuati_cli/             # New CLI package
│   ├── __init__.py
│   ├── cli.py                  # Main Click group, global options
│   ├── formatter.py            # YAML/JSON/Rich output formatting
│   ├── exceptions.py           # Structured error classes
│   ├── context.py              # Click context helper
│   ├── config.py               # CLI-specific config (shared with app)
│   └── commands/
│       ├── __init__.py
│       ├── login.py            # login, status
│       ├── sync.py             # sync, sync-status
│       ├── list.py             # list, list-questions
│       ├── generate.py         # generate (word doc)
│       └── server.py           # server (start web)
├── app.py                      # Flask web app (refactored to use shared modules)
├── auth.py                     # Shared auth (Playwright + token mgmt)
├── sync.py                     # Shared sync engine
├── jielong_api.py              # Shared API client
├── database.py                 # Shared DB operations
├── docgen.py                   # Shared doc generation
├── ocr_utils.py                # Shared OCR utils
├── config.py                   # Shared config
├── templates/                  # Web UI templates
├── data/                       # Runtime data
├── requirements.txt
├── CLAUDE.md
└── SKILL.md                    # AI agent skill definition
```

### CLI Command Groups

| Command | Description |
|---------|-------------|
| `shuati login` | Launch Playwright browser for WeChat QR login |
| `shuati status` | Check login status (token validity, expiry) |
| `shuati sync` | Sync new questions from Jielong |
| `shuati sync --force` | Re-fetch all favorites (debug) |
| `shuati list` | List synced threads |
| `shuati list --date 2026-03-01` | Filter by date |
| `shuati list --page 2` | Pagination |
| `shuati show <thread-id>` | Show thread detail with questions |
| `shuati generate` | Generate Word doc |
| `shuati generate --start 2026-03-01 --end 2026-03-07` | Date range |
| `shuati generate --output /path/to/doc.docx` | Custom output path |
| `shuati server` | Start Flask web UI |
| `shuati server --port 9000` | Custom port |

**Global options:**
- `--yaml` / `--json` — structured output (default: YAML when non-TTY, Rich when TTY)
- `-v` / `--verbose` — verbose logging

### Dual-Mode Operation

The package works in two modes:

1. **CLI mode** (`shuati <command>`): Direct command execution, structured output
2. **Web mode** (`shuati server` or `python app.py`): Flask web UI

Both modes share the same underlying modules (`auth.py`, `database.py`, `sync.py`, etc.). The CLI and web app share configuration via `config.py`.

### Output Schema

All CLI commands use a unified envelope:

**Success:**
```yaml
ok: true
schema_version: "1"
data: ...
```

**Error:**
```yaml
ok: false
schema_version: "1"
error:
  code: <error_code>
  message: <message>
```

Error codes: `not_authenticated`, `invalid_token`, `sync_failed`, `no_data`, `generation_failed`, `network_error`, `internal_error`

### Login Flow (Unchanged)

Login is handled by `auth.py` (Playwright + WeChat scan). The CLI `login` command calls `ensure_logged_in(wait=True)` which opens the Playwright browser. The browser profile is persisted in `data/browser_profile/` so subsequent logins don't need re-scanning.

Token expiry is ~3 days. After expiry, `sync` and other auth-required commands will prompt to re-login.

### Sync Behavior

`sync` fetches favorites from the Jielong API, downloads images, runs OCR classification, and stores structured questions. It's a blocking long-running operation.

### Document Generation

`generate` produces a Word doc. If no date range is given, it generates for all available data. The output path is printed (or returned as `output_path` in structured output).

### Installation

```bash
# Via uv (recommended)
uv tool install .

# Via pipx
pipx install .

# Via pip
pip install .
```

### Dependency Strategy

- `click` — CLI framework (replacing direct argparse)
- `flask` — Web server
- `requests` — HTTP client
- `python-docx` — Word doc generation
- `playwright` — Browser automation (login)
- `ocrmac` — Image text analysis
- `schedule` — Scheduling (for web server's background sync)
- `pyyaml` — YAML output
- `rich` — Rich terminal output for TTY

New dependency: `click`, `pyyaml`, `rich`
