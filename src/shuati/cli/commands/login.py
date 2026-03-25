"""
Login and authentication commands.
"""
import click
from rich.console import Console

from shuati.cli.formatter import print_envelope_success, print_envelope_error
from shuati.cli.options import get_ctx_output_mode, add_output_options

console = Console()


@click.command()
@click.pass_context
@add_output_options
def login(ctx, yaml, json):
    """Launch Playwright browser for WeChat QR login."""
    from shuati.core.auth import ensure_logged_in, is_token_valid

    if is_token_valid():
        console.print("[green]✓[/green] 已登录，无需重复扫码")
        data = _build_status_data()
        mode = get_ctx_output_mode(ctx)
        if mode == "rich":
            return
        print_envelope_success(data, ctx)
        return

    console.print("[yellow]正在启动浏览器，请用微信扫码登录...[/yellow]")
    console.print("[dim]提示：登录后浏览器会自动关闭，无需手动操作[/dim]")

    success = ensure_logged_in(wait=True)

    mode = get_ctx_output_mode(ctx)
    if success:
        console.print("[green]✓[/green] 登录成功！")
        data = _build_status_data()
        if mode == "rich":
            return
        print_envelope_success(data, ctx)
    else:
        print_envelope_error("not_authenticated", "登录失败或超时，请重试", ctx)


@click.command(name="status")
@click.pass_context
@add_output_options
def status(ctx, yaml, json):
    """Check login status and token validity."""
    from shuati.core.auth import is_token_valid, load_token
    from datetime import datetime

    valid = is_token_valid()
    token_data = load_token()

    mode = get_ctx_output_mode(ctx)
    if mode == "rich":
        if valid:
            exp = token_data.get("exp", 0) if token_data else 0
            exp_str = datetime.fromtimestamp(exp).strftime("%Y-%m-%d %H:%M:%S") if exp else "未知"
            console.print(f"[green]✓[/green] 已登录 (有效期至: {exp_str})")
        else:
            console.print("[red]✗[/red] 未登录，请运行 [bold]shuati login[/bold]")
        return

    data = _build_status_data(token_data, valid)
    print_envelope_success(data, ctx)


def _build_status_data(token_data=None, valid=None):
    from shuati.core.auth import is_token_valid, load_token
    from datetime import datetime

    if valid is None:
        valid = is_token_valid()
    if token_data is None:
        token_data = load_token()

    exp = token_data.get("exp", 0) if token_data else 0
    exp_str = datetime.fromtimestamp(exp).strftime("%Y-%m-%d %H:%M:%S") if exp else None

    return {
        "logged_in": valid,
        "exp": exp,
        "exp_str": exp_str,
        "saved_at": token_data.get("saved_at") if token_data else None,
    }
