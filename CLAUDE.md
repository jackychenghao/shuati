# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`shuati-agent` is a Python application that automatically collects daily check-in questions (打卡题) from the "接龙管家" (Jielong Manager) platform via WeChat login, stores them in SQLite, and generates printable Word documents.

It provides both a **CLI** (`shuati` command) and an optional **Web UI** (Flask).

## Installation

```bash
pip install -r requirements.txt
playwright install chromium  # first run only
```

## Commands

### CLI

```bash
pip install -e .   # 安装一次，之后直接用 shuati 命令
shuati --help              # Show all commands
shuati login               # WeChat QR login (opens browser)
shuati status              # Check login status
shuati sync                # Sync new questions
shuati sync --force        # Force re-sync all
shuati sync-status         # Show last sync info
shuati list                # List synced threads
shuati list --date 2026-03-01 --end 2026-03-07  # date filter
shuati show <thread-id>    # Show thread detail
shuati generate            # Generate Word doc (all)
shuati generate --start 2026-03-01 --end 2026-03-07  # date range
shuati server              # Start web UI (http://localhost:8080)
```

### Original scripts

```bash
python app.py        # Flask web server on port 8080
python sync.py       # Manual sync (blocking, requires terminal login)
```

### Output formats

All CLI commands support `--yaml` (default for non-TTY) and `--json` output:
```bash
shuati list --yaml
shuati list --json
```

## Architecture

### Data Flow

1. **Login** (`auth.py`): Playwright opens Chromium, user scans WeChat QR code. Token captured from `localStorage`/`Cookie`/network requests, encrypted with machine-specific key in `data/.key`. Browser profile persisted in `data/browser_profile/` so subsequent logins don't need re-scanning.

2. **Sync** (`sync.py`): Fetches favorites list from Jielong API (`/Thread/Threads` with `listType=5`), fetches detail per thread (`/CheckIn/Detail`). Images downloaded locally. OCR (`ocrmac`) categorizes each image as answer or diagram. Questions parsed from raw text using regex splitting on numbered patterns (`\d+、`).

3. **Storage** (`database.py`): Single global SQLite connection (`_db_conn`). Tables: `threads`, `blocks` (raw content), `questions` (structured), `sync_log`, `app_settings`.

4. **CLI** (`shuati_cli/`): Click-based CLI. Unified error envelope schema. `--yaml`/`--json` structured output for AI agent friendliness.

5. **Web UI** (`app.py`): Flask serves `templates/`. API for auth polling, sync, thread CRUD, Word generation.

6. **DocGen** (`docgen.py`): Generates A4 Word documents. OCR-classified answer images excluded; diagram images embedded near questions.

### Key Files

- `pyproject.toml` — Package config, `shuati` CLI entry point
- `shuati_cli/` — CLI package
  - `cli.py` — Main Click group, error handling
  - `formatter.py` — YAML/JSON/Rich output formatting
  - `exceptions.py` — Structured error codes
  - `commands/` — Subcommands (login, sync, list, generate, server, show)
- `app.py` — Flask web app
- `auth.py` — Playwright + WeChat login, token encryption
- `sync.py` — Sync engine, OCR classification
- `jielong_api.py` — Jielong API client
- `database.py` — SQLite operations
- `docgen.py` — Word document generation
- `ocr_utils.py` — Image text analysis (ocrmac)
- `config.py` — Configuration
- `data/` — Runtime data (gitignored): `questions.db`, `token.json`, `images/`, `browser_profile/`
- `SKILL.md` — AI agent skill definition

### Configuration

Edit `config.py`:
```python
SYNC_HOUR = 7       # Scheduled sync hour (24h)
SYNC_MINUTE = 0     # Scheduled sync minute
FLASK_PORT = 8080    # Web server port
```

### Error Codes (CLI)

| Code | Meaning |
|------|---------|
| `not_authenticated` | Not logged in — run `shuati login` |
| `invalid_token` | Token expired — run `shuati login` |
| `sync_failed` | Sync failed (network/API error) |
| `no_data` | No threads found |
| `generation_failed` | Word doc generation failed |
| `network_error` | Network request failed |
| `internal_error` | Unexpected error |

### OCR Image Classification

`ocr_utils.analyze_image_text()` returns:
- `is_answer`: image contains answer keywords → excluded from print
- `question_seq`: detected question number
- `looks_like_question`: image appears to be a question diagram → included
