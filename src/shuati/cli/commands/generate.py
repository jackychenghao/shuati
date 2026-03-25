"""
Generate Word document command.
"""
import click
from rich.console import Console

from shuati.cli.formatter import print_envelope_success, print_envelope_error
from shuati.cli.options import get_ctx_output_mode, add_output_options
from shuati.cli.exceptions import NoDataError, GenerationError

console = Console()


@click.command(name="generate")
@click.option("--start", default="", help="起始日期 (YYYY-MM-DD)")
@click.option("--end", default="", help="结束日期 (YYYY-MM-DD)")
@click.option("--threads", "thread_ids", multiple=True, help="要包含的特定主题 ID 列表")
@click.option("--output", "-o", "output_path", default="", help="输出文件路径")
@click.option("--format", "output_format", default="docx", type=click.Choice(["docx", "pdf"]), help="输出格式 (docx 或 pdf)")
@click.option("--preprocess-images/--no-preprocess-images", default=True, help="是否自动裁剪图片题目四周的留白并缩放排版")
@click.pass_context
@add_output_options
def generate(ctx, start, end, thread_ids, output_path, output_format, preprocess_images, yaml, json):
    """根据已同步的题库内容生成 Word 或 PDF 文档。"""
    from shuati.core.database import get_threads_by_date_range, get_threads_by_ids
    from shuati.core.docgen import generate_word, generate_pdf

    if not start and not end and not thread_ids:
        # Default: use all available
        pass

    threads = []
    if thread_ids:
        threads = get_threads_by_ids(list(thread_ids))
        if not threads:
            raise NoDataError("未找到指定的 thread_ids")
    elif start and end:
        threads = get_threads_by_date_range(start, end)
        if not threads:
            raise NoDataError(f"在 {start} 到 {end} 之间没有题目")
    else:
        # Generate for all - need to find date range
        from shuati.core.database import get_all_threads
        all_threads = get_all_threads(limit=1000)
        if all_threads:
            dates = [t.get("date_str", "")[:10] for t in all_threads if t.get("date_str")]
            if dates:
                start = min(dates)
                end = max(dates)
                threads = get_threads_by_date_range(start, end)

    if not threads:
        raise NoDataError("没有可生成的题目，请先运行 shuati sync")

    format_label = "PDF" if output_format == "pdf" else "Word"
    console.print(f"[cyan]正在生成 {format_label} 文档...[/cyan]")
    console.print(f"  题目数量: {len(threads)} 条")

    try:
        if output_format == "pdf":
            out_path = generate_pdf(
                start_date=start or "0001-01-01",
                end_date=end or "9999-12-31",
                output_path=output_path or None,
                source_thread_ids=[t["thread_id"] for t in threads] if thread_ids else None,
                preprocess_images=preprocess_images,
            )
        else:
            out_path = generate_word(
                start_date=start or "0001-01-01",
                end_date=end or "9999-12-31",
                output_path=output_path or None,
                source_thread_ids=[t["thread_id"] for t in threads] if thread_ids else None,
                preprocess_images=preprocess_images,
            )

        mode = get_ctx_output_mode(ctx)
        if mode == "rich":
            console.print(f"[green]✓[/green] 已生成: {out_path}")
        else:
            print_envelope_success({"output_path": out_path, "thread_count": len(threads)}, ctx)

    except Exception as e:
        raise GenerationError(f"生成失败: {e}")
