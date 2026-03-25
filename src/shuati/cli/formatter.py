"""
Output formatting for CLI - supports YAML, JSON, and Rich.
"""
import json
import sys
import os
from typing import Any

import yaml
from rich.console import Console
from rich.table import Table
from rich.syntax import Syntax

OUTPUT_MODE = os.environ.get("OUTPUT", "auto")


def _get_mode(ctx=None) -> str:
    if OUTPUT_MODE not in ("auto", "yaml", "json", "rich"):
        mode = "auto"
    else:
        mode = OUTPUT_MODE

    # Explicit override via click context
    if ctx and ctx.params:
        if ctx.params.get("yaml"):
            return "yaml"
        if ctx.params.get("json"):
            return "json"

    # Auto: yaml for non-TTY, rich for TTY
    if mode == "auto":
        if not sys.stdout.isatty():
            return "yaml"
        return "rich"
    return mode


def format_output(data: Any, ctx=None, **kwargs) -> str:
    """Format data as string based on output mode."""
    mode = _get_mode(ctx)

    if mode == "yaml":
        return yaml.dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False)
    elif mode == "json":
        return json.dumps(data, ensure_ascii=False, indent=2)
    else:
        # Rich - handled separately per command
        return data  # Return raw for rich rendering


def print_envelope(ok: bool, data: Any = None, error: dict = None, ctx=None):
    """Print a structured envelope (success or error)."""
    mode = _get_mode(ctx)
    if mode == "rich":
        console = Console()
        if ok:
            console.print("\n[green]✓[/green] 操作成功")
            if data:
                _print_rich_data(data, console)
        else:
            console.print(f"\n[red]✗[/red] {error.get('message', '未知错误')}")
            console.print(f"  code: {error.get('code', 'unknown')}")
        return

    # Structured output
    envelope = {"ok": ok, "schema_version": "1"}
    if ok:
        envelope["data"] = data
    else:
        envelope["error"] = error

    if mode == "json":
        print(json.dumps(envelope, ensure_ascii=False, indent=2))
    else:
        print(yaml.dump(envelope, allow_unicode=True, default_flow_style=False, sort_keys=False))


def _print_rich_data(data, console: Console, indent: int = 0):
    """Print structured data with rich formatting."""
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                console.print(f"  {key}:")
                _print_rich_data(value, console, indent + 2)
            else:
                console.print(f"  {key}: {value}")
    elif isinstance(data, list):
        for i, item in enumerate(data):
            console.print(f"  [{i}]: {item}")


def print_table(headers: list[str], rows: list[list[Any]], title: str = ""):
    """Print a rich table."""
    console = Console()
    table = Table(title=title, show_header=True, header_style="bold magenta")
    for h in headers:
        table.add_column(h)
    for row in rows:
        table.add_row(*[str(c) for c in row])
    console.print(table)


def print_envelope_success(data: Any, ctx=None):
    print_envelope(True, data=data, ctx=ctx)


def print_envelope_error(code: str, message: str, ctx=None):
    print_envelope(False, error={"code": code, "message": message}, ctx=ctx)
