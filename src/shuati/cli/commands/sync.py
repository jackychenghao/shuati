"""
Sync commands.
"""
import click
from rich.console import Console

from shuati.cli.formatter import print_envelope_success, print_envelope_error
from shuati.cli.options import get_ctx_output_mode, add_output_options

console = Console()


@click.command(name="sync")
@click.option("--force", is_flag=True, help="重新拉取所有条目（忽略已存在，跳过详情页）")
@click.option("--non-answer-images/--no-non-answer-images", default=None,
              help="是否将非答案图片作为配图使用（默认从设置读取）")
@click.pass_context
@add_output_options
def sync(ctx, force, non_answer_images, yaml, json):
    """Sync new questions from Jielong Manager."""
    from shuati.core.auth import is_token_valid
    from shuati.core.sync import sync_once
    from shuati.core.database import init_db, get_bool_setting

    if not is_token_valid():
        print_envelope_error("not_authenticated", "未登录，请先运行 shuati login", ctx)
        return

    init_db()

    use_non_answer = non_answer_images
    if use_non_answer is None:
        use_non_answer = get_bool_setting("use_non_answer_images_as_diagrams", True)

    console.print(f"[cyan]开始同步...[/cyan] (force={force})")

    result = sync_once(force=force, use_non_answer_images=use_non_answer)

    mode = get_ctx_output_mode(ctx)
    if mode == "rich":
        if result["status"] == "success":
            console.print(f"[green]✓[/green] {result['message']}")
        else:
            console.print(f"[red]✗[/red] {result['message']}")
        return

    print_envelope_success(result, ctx)


@click.command(name="sync-status")
@click.pass_context
@add_output_options
def sync_status(ctx, yaml, json):
    """Show last sync status."""
    from shuati.core.database import get_last_sync, get_thread_count

    last = get_last_sync()
    count = get_thread_count()

    mode = get_ctx_output_mode(ctx)
    if mode == "rich":
        if last:
            console.print(f"[cyan]上次同步:[/cyan] {last.get('synced_at', '未知')}")
            console.print(f"[cyan]新增条目:[/cyan] {last.get('new_count', 0)}")
            console.print(f"[cyan]状态:[/cyan] {last.get('status', '未知')}")
            console.print(f"[cyan]当前总数:[/cyan] {count}")
        else:
            console.print("[yellow]尚无同步记录[/yellow]")
        return

    data = {
        "last_sync": last,
        "thread_count": count,
    }
    print_envelope_success(data, ctx)
