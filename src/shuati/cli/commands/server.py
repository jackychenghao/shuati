"""
Start web server command.
"""
import sys
import os

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import click
from rich.console import Console

console = Console()


@click.command(name="server")
@click.option("--port", default=8080, type=int, help="Port to listen on")
@click.option("--host", default="0.0.0.0", help="Host to bind to")
@click.option("--debug", is_flag=True, default=False, help="Enable Flask debug mode")
@click.pass_context
def server(ctx, port, host, debug):
    """Start the Flask web UI."""
    from shuati.web.app import create_app
    import threading

    def run_scheduler():
        """Run background sync scheduler."""
        import schedule
        import time
        from shuati.core.config import SYNC_HOUR, SYNC_MINUTE
        from shuati.core.sync import sync_once
        from shuati.core.auth import is_token_valid

        def job():
            if is_token_valid():
                sync_once()
            else:
                print("[Sync] 未登录，跳过定时同步")

        schedule.every().day.at(f"{SYNC_HOUR:02d}:{SYNC_MINUTE:02d}").do(job)
        while True:
            schedule.run_pending()
            time.sleep(60)

    # Start scheduler in background thread
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()

    console.print(f"[green]✓[/green] Web UI 已启动")
    console.print(f"  访问地址: http://localhost:{port}")
    console.print(f"  Ctrl+C 停止服务器")
    console.print()

    app = create_app()
    app.run(host=host, port=port, debug=debug, use_reloader=False)
