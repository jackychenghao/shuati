"""
List commands.
"""
import click
from rich.console import Console
from rich.table import Table

from shuati.cli.formatter import print_envelope_success
from shuati.cli.options import get_ctx_output_mode, add_output_options
from shuati.core.date_utils import normalize_datetime_text

console = Console()


@click.command(name="list")
@click.option("--date", "start", default="", help="Start date (YYYY-MM-DD)")
@click.option("--end", default="", help="End date (YYYY-MM-DD)")
@click.option("--page", default=1, type=int, help="Page number")
@click.option("--page-size", default=15, type=int, help="Items per page")
@click.option("--max", "limit", default=None, type=int, help="Max items to show (overrides page)")
@click.pass_context
@add_output_options
def list(ctx, start, end, page, page_size, limit, yaml, json):
    """List synced threads."""
    from shuati.core.database import get_threads_page

    page_size = limit or page_size
    result = get_threads_page(start=start, end=end, page=page, page_size=page_size)
    threads = result["items"]

    for t in threads:
        t["date_str"] = normalize_datetime_text(t.get("date_str", ""), t.get("subject", ""))

    mode = get_ctx_output_mode(ctx)
    if mode == "rich":
        if not threads:
            console.print("[yellow]没有找到题目[/yellow]")
            return

        table = Table(title="打卡题列表", show_header=True, header_style="bold magenta")
        table.add_column("日期", style="cyan")
        table.add_column("标题", style="white")
        table.add_column("作者", style="dim")

        for t in threads:
            date = str(t.get("date_str", ""))[:10]
            table.add_row(date, t.get("subject", ""), t.get("author") or "-")

        console.print(table)
        total_pages = max(1, (result['total'] + page_size - 1) // page_size)
        console.print(f"\n共 {result['total']} 条，第 {result['page']}/{total_pages} 页")
        return

    print_envelope_success(result, ctx)


@click.command(name="list-questions")
@click.argument("thread_id", required=False)
@click.option("--thread-id", "tid_opt", help="Thread ID (alternative)")
@click.pass_context
@add_output_options
def list_questions(ctx, thread_id, tid_opt, yaml, json):
    """List questions for a thread."""
    t_id = thread_id or tid_opt
    if not t_id:
        console.print("[red]需要提供 thread-id[/red]")
        return

    import json as json_lib
    from shuati.core.database import get_questions_by_thread, get_threads_by_ids
    from shuati.cli.exceptions import NoDataError

    threads = get_threads_by_ids([t_id])
    if not threads:
        raise NoDataError(f"未找到 thread_id={t_id}")

    questions = get_questions_by_thread(t_id)

    mode = get_ctx_output_mode(ctx)
    if mode == "rich":
        if not questions:
            console.print("[yellow]该接龙没有结构化题目[/yellow]")
            return

        thread = threads[0]
        console.print(f"\n[bold]{thread['subject']}[/bold] ({thread.get('date_str', '')[:10]})")
        console.print()

        for q in questions:
            seq = q.get("seq", "?")
            content = q.get("content", "")
            images = json_lib.loads(q.get("images") or "[]")
            answers = json_lib.loads(q.get("answers") or "[]")

            console.print(f"  [{seq}] {content[:80]}")
            if images:
                console.print(f"      📷 配图: {len(images)} 张")
            if answers:
                console.print(f"      ✅ 答案: {len(answers)} 张")
        return

    print_envelope_success({"thread": threads[0], "questions": questions}, ctx)
