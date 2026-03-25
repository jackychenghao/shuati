"""
Shared CLI options and utilities.

Provides common output-format options and helper functions
used across all CLI command modules.
"""
import click

from shuati.cli.formatter import _get_mode


def get_ctx_output_mode(ctx) -> str:
    """Get output mode from click context params."""
    if ctx.params.get("yaml"):
        return "yaml"
    if ctx.params.get("json"):
        return "json"
    return _get_mode(ctx)


def add_output_options(cmd):
    """Add --yaml and --json options to a click command."""
    cmd = click.option("--json", is_flag=True, default=False, help="Output in JSON format")(cmd)
    cmd = click.option("--yaml", is_flag=True, default=False, help="Output in YAML format")(cmd)
    return cmd
