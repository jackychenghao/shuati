"""
Show command for thread detail.
"""
import os
import json as json_lib

import click
from rich.console import Console

from shuati.cli.formatter import print_envelope_success
from shuati.cli.options import get_ctx_output_mode, add_output_options
from shuati.cli.exceptions import NoDataError

console = Console()


@click.command(name="show")
@click.argument("thread_id")
@click.pass_context
@add_output_options
def show(ctx, thread_id, yaml, json):
    """Show detailed view of a thread with all questions."""
    from shuati.core.database import get_threads_by_ids, get_questions_by_thread, get_blocks_by_thread

    threads = get_threads_by_ids([thread_id])
    if not threads:
        raise NoDataError(f"未找到 thread_id={thread_id}")

    thread = threads[0]
    questions = get_questions_by_thread(thread_id)
    blocks = get_blocks_by_thread(thread_id)

    mode = get_ctx_output_mode(ctx)
    if mode == "rich":
        console.print(f"\n[bold cyan]{thread['subject']}[/bold cyan]")
        console.print(f"  日期: {thread.get('date_str', '未知')[:10]}")
        console.print(f"  作者: {thread.get('author') or '未知'}")
        console.print(f"  类型: {thread.get('type', '接龙管家打卡接龙')}")
        console.print()

        if questions:
            console.print("[bold]题目结构:[/bold]")
            for q in questions:
                seq = q.get("seq", "?")
                content = q.get("content", "") or "(无文本)"
                images = json_lib.loads(q.get("images") or "[]")
                answers = json_lib.loads(q.get("answers") or "[]")

                console.print(f"\n  [{seq}] {content[:100]}")
                if images:
                    for img in images:
                        console.print(f"      📷 {os.path.basename(img)}")
                if answers:
                    for ans in answers:
                        console.print(f"      ✅ {os.path.basename(ans)}")
        else:
            console.print("[yellow]无结构化题目[/yellow]")

        if blocks:
            console.print(f"\n[bold]原始内容块:[/bold] ({len(blocks)} 个)")
            for i, b in enumerate(blocks[:5]):
                ctype = b.get("content_type")
                if ctype == 11:
                    text = (b.get("text") or "")[:80]
                    console.print(f"  [{i+1}] 文字: {text}")
                elif ctype == 4:
                    console.print(f"  [{i+1}] 图片: {b.get('image_url', '')[:50]}")
            if len(blocks) > 5:
                console.print(f"  ... 还有 {len(blocks) - 5} 个块")

        return

    print_envelope_success({
        "thread": thread,
        "questions": questions,
        "blocks": blocks,
    }, ctx)
