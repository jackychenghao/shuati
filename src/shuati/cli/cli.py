"""
Main CLI entry point for shuati.
"""
import sys
import os

# Ensure project root is on path
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import click

from shuati import __version__
from shuati.cli.formatter import print_envelope_error
from shuati.cli.exceptions import ShuatiError


def _make_invoke_with_error_handling(cmd):
    """Wrap a command's invoke with global exception handling."""
    original_invoke = cmd.invoke

    def invoke(ctx):
        try:
            return original_invoke(ctx)
        except ShuatiError as e:
            print_envelope_error(e.code, e.message, ctx=ctx)
            ctx.exit(1)
        except Exception as e:
            print_envelope_error("internal_error", str(e), ctx=ctx)
            ctx.exit(1)

    cmd.invoke = invoke
    return cmd


@click.group(context_settings=dict(help_option_names=["-h", "--help"]))
@click.version_option(version=__version__, prog_name="shuati")
@click.option("-v", "--verbose", is_flag=True, help="开启详细日志输出")
@click.pass_context
def cli(ctx, verbose):
    """
    shuati-agent: 接龙管家每日打卡题采集终端工具。

    你可以运行 'shuati <指令> --help' 来查看任意指令的功能详情。
    或者使用 'shuati help' 罗列所有可用指令。
    """
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose

    if verbose:
        os.environ["SHUATI_VERBOSE"] = "1"


# Register subcommands
from shuati.cli.commands import login, sync, list as list_cmd, generate, server, show

for cmd in [
    login.login,
    login.status,
    sync.sync,
    sync.sync_status,
    list_cmd.list,
    list_cmd.list_questions,
    generate.generate,
    server.server,
    show.show,
]:
    _make_invoke_with_error_handling(cmd)
    cli.add_command(cmd)

@click.command(name="help")
@click.pass_context
def _help_cmd(ctx):
    """显示本帮助信息并退出"""
    click.echo(ctx.parent.get_help())

cli.add_command(_help_cmd)


if __name__ == "__main__":
    cli(obj={})
