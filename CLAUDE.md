# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`shuati` collects daily check-in questions (打卡题) from the 接龙管家 platform via WeChat login, stores them in SQLite, and generates printable Word/PDF documents.

## Installation

```bash
pip install -r requirements.txt
playwright install chromium  # first run only
pip install -e .             # installs shuati CLI
```

## Commands

```bash
shuati --help
shuati login               # WeChat QR login (opens browser)
shuati status              # Check login/token status
shuati sync                # Fetch new threads, parse, store
shuati sync --force        # Re-fetch all threads
shuati list                # List threads (Rich table in TTY, YAML otherwise)
shuati list --date 2026-03-01 --end 2026-03-07
shuati show <thread-id>    # Show thread detail with questions
shuati generate            # Generate Word doc
shuati generate --start 2026-03-01 --end 2026-03-07 --format pdf
shuati server              # Start Flask web UI (http://localhost:8080)
```

All commands support `--yaml` / `--json` for structured output (auto-detected in non-TTY).

## Running Tests

```bash
pytest                                    # all tests
pytest tests/test_question_parser.py     # single file
pytest -v                                # verbose
```

## Architecture

### Package Layout (`src/shuati/`)
- `cli/` — Click CLI: `cli.py` (main group), `formatter.py`, `exceptions.py`, `commands/`
- `core/` — Business logic: `auth.py`, `sync.py`, `database.py`, `docgen.py`, `question_parser.py`, `jielong_api.py`, `ocr_utils.py`, `date_utils.py`, `config.py`
- `web/` — Flask app (`app.py`) + HTML templates

### Data Flow
1. **Login** (`auth.py`): Playwright opens Chromium for WeChat QR scan. Token encrypted with machine key in `data/.key`; browser profile cached in `data/browser_profile/`.
2. **Sync** (`sync.py:sync_once()`): Fetches favorites list → fetches thread detail → downloads images + OCR → parses questions → saves to DB.
3. **Parse** (`question_parser.py`): Pure function — no I/O. `parse_questions(all_text, image_metas, use_non_answer_images)` splits text on `\d+、` patterns and attaches images to questions.
4. **Storage** (`database.py`): Raw blocks in `blocks` table; structured output in `questions` table.
5. **DocGen** (`docgen.py`): Reads questions + blocks, generates A4 Word doc. PDF via pandoc + Chrome.

### Database (SQLite at `data/questions.db`)
- `threads` — one row per synced thread
- `blocks` — raw text/image blocks (preserves API order)
- `questions` — parsed questions (seq 1–N, `images` and `answers` as JSON arrays)
- `sync_log` — audit trail
- `app_settings` — key-value config (e.g., `use_non_answer_images_as_diagrams`)

Single global connection (`_db_conn`). Tests use `init_db_from_conn()` with in-memory SQLite.

### OCR Image Classification (`ocr_utils.analyze_image_text()`)
- Returns `is_answer` (answer keywords detected), `question_seq`, `looks_like_question`
- Primary: `ocrmac` (macOS); fallback: `rapidocr_onnxruntime`
- Answer images are stored but excluded from printed documents

### CLI Error Handling
All errors are `ShuatiError` subclasses with structured codes (`not_authenticated`, `sync_failed`, `no_data`, `generation_failed`, etc.). Global handler in `cli.py` emits JSON/YAML error envelopes for AI agent use.

### Configuration (`core/config.py`)
- `DATA_DIR`, `DB_PATH`, `TOKEN_PATH`, `IMAGES_DIR`
- `JIELONG_API_BASE = "https://i-api.jielong.com/api"`
- `FLASK_PORT = 8080`, `SYNC_HOUR = 7`
