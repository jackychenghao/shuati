# SKILL.md

## Overview

`shuati-agent` is a CLI tool for collecting daily check-in questions (打卡题) from the "接龙管家" (Jielong Manager) platform. It stores questions in SQLite and generates printable Word documents.

**Command prefix:** `shuati`

**Version:** 1.0.0

## Installation

```bash
pip install -e .
playwright install chromium  # first run only
```

## Quick Start

```bash
shuati login           # WeChat QR code login
shuati sync            # Fetch new questions
shuati list            # View synced threads
shuati generate        # Generate Word doc for all questions
shuati generate --start 2026-03-01 --end 2026-03-07  # Date range
shuati server          # Start web UI at http://localhost:8080
```

## Command Reference

### Authentication

| Command | Description |
|---------|-------------|
| `shuati login` | Launch Playwright browser for WeChat QR login. Persistent browser profile means only first login requires scanning. |
| `shuati status` | Check login status, token expiry time |

**Login notes:**
- Token expires ~3 days after capture
- Playwright browser profile persisted at `data/browser_profile/` - WeChat session survives, no re-scan needed
- If `sync` or other commands fail with `not_authenticated`, run `shuati login`

### Sync

| Command | Description |
|---------|-------------|
| `shuati sync` | Sync new questions from Jielong (differential - only new items) |
| `shuati sync --force` | Re-fetch all favorites, ignore existing (debug) |
| `shuati sync-status` | Show last sync time, new count, total threads |

### Viewing Data

| Command | Description |
|---------|-------------|
| `shuati list` | List all synced threads (paginated) |
| `shuati list --date 2026-03-01 --end 2026-03-07` | Filter by date range |
| `shuati list --page 2 --page-size 20` | Pagination |
| `shuati list-questions <thread-id>` | List structured questions for a thread |
| `shuati show <thread-id>` | Full detail view of a thread (questions + blocks) |

### Document Generation

| Command | Description |
|---------|-------------|
| `shuati generate` | Generate Word doc for all synced questions |
| `shuati generate --start 2026-03-01 --end 2026-03-07` | Date range filter |
| `shuati generate --threads <id1> --threads <id2>` | Specific threads only |
| `shuati generate --output /path/to/doc.docx` | Custom output path |

Output file path is returned in structured output as `output_path`.

### Web Server

| Command | Description |
|---------|-------------|
| `shuati server` | Start Flask web UI (http://localhost:8080) |
| `shuati server --port 9000` | Custom port |
| `shuati server --debug` | Enable Flask debug mode |

Web UI features: thread browser, manual sync button, date-range Word doc generation.

## Output Modes

All commands support structured output for AI agent consumption:

```bash
shuati <command> --yaml   # YAML output (token-efficient, default for non-TTY)
shuati <command> --json   # JSON output
# Default: Rich terminal output when stdout is a TTY, YAML otherwise
```

### Success Envelope

```yaml
ok: true
schema_version: "1"
data: ...
```

### Error Envelope

```yaml
ok: false
schema_version: "1"
error:
  code: <error_code>
  message: <human-readable message>
```

### Error Codes

| Code | Meaning |
|------|---------|
| `not_authenticated` | Not logged in - run `shuati login` |
| `invalid_token` | Token expired - run `shuati login` |
| `sync_failed` | Sync operation failed (network/API error) |
| `no_data` | No threads found for given criteria |
| `generation_failed` | Word document generation failed |
| `network_error` | Network request failed |
| `internal_error` | Unexpected error |

## Data Model

### Thread

A "thread" (接龙) corresponds to one check-in session (one day's assignment):

```json
{
  "thread_id": "2X7C9XMVJV",
  "subject": "20260314小五打卡",
  "date_str": "2026-03-14 12:09:00",
  "author": "甜米米",
  "type": "接龙管家打卡接龙"
}
```

### Question

Each thread contains one or more questions (parsed from raw text):

```json
{
  "seq": 1,
  "content": "2、小星、小锐、小强一起买文具...",
  "images": [],           // diagram image paths
  "answers": ["/path/to/answer/image.jpg"]  // answer image paths
}
```

### Block

Raw content blocks from the API:

- `content_type: 11` = text
- `content_type: 4` = image

## Architecture

```
shuati-agent/
├── shuati_cli/           # CLI package (click-based)
│   ├── cli.py            # Main entry point
│   ├── formatter.py      # YAML/JSON/Rich output
│   ├── exceptions.py     # Structured error codes
│   └── commands/         # Subcommands
├── app.py                # Flask web app
├── auth.py               # Playwright + WeChat login
├── sync.py               # Sync engine (fetch → OCR → parse → store)
├── jielong_api.py        # Jielong API client
├── database.py           # SQLite operations
├── docgen.py             # Word document generation
├── ocr_utils.py          # Image text analysis (ocrmac)
├── config.py             # Configuration
└── data/                 # Runtime data (gitignored)
    ├── questions.db      # SQLite database
    ├── token.json        # Encrypted auth token
    ├── images/           # Downloaded images
    └── browser_profile/  # Playwright persistent profile
```

## Configuration

Edit `config.py`:

```python
SYNC_HOUR = 7       # Daily sync hour (24h)
SYNC_MINUTE = 0     # Daily sync minute
FLASK_PORT = 8080   # Web server port
```

## OCR Image Classification

Images are classified via `ocr_utils.analyze_image_text()`:

- **`is_answer`**: image contains answer keywords (解答, 答案, etc.) → excluded from print
- **`looks_like_question`**: image appears to be a question diagram → included
- **`question_seq`**: detected question number for mapping

This determines whether images appear as student-facing diagrams or are hidden as teacher answer keys.

## Word Document Layout

Generated documents include:
- A4 page, 2.5cm margins
- Thread title per section
- Question text + diagrams
- Answer images excluded (per OCR classification)

## Environment Variables

| Variable | Effect |
|----------|--------|
| `OUTPUT=json\|yaml\|rich\|auto` | Override default output mode |
| `SHUATI_VERBOSE=1` | Enable verbose logging |
