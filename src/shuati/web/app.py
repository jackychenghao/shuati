"""
Flask Web 应用入口。
访问 http://localhost:8080 即可使用。
"""
import os
import json
from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for
from shuati.core.config import FLASK_PORT, FLASK_SECRET, DATA_DIR
from shuati.core.database import (
    init_db, get_all_threads, get_threads_by_date_range,
    get_blocks_by_thread, get_last_sync, get_thread_count, delete_thread,
    get_bool_setting, set_bool_setting, get_threads_page
)
from shuati.core.auth import (
    is_token_valid, load_token,
    ensure_logged_in, get_login_status, start_login_browser
)
from shuati.core.sync import sync_once
from shuati.core.docgen import generate_word
from shuati.core.date_utils import normalize_datetime_text

app = Flask(__name__)
app.secret_key = FLASK_SECRET

# ── 页面路由 ──────────────────────────────────────────────

@app.route("/")
def index():
    logged_in = is_token_valid()
    if not logged_in:
        return redirect(url_for("login"))
    threads = get_all_threads(100)
    for t in threads:
        t["date_str"] = normalize_datetime_text(t.get("date_str", ""), t.get("subject", ""))
    last_sync = get_last_sync()
    count = get_thread_count()
    return render_template("index.html",
        threads=threads,
        last_sync=last_sync,
        count=count,
        logged_in=logged_in,
        use_non_answer_images_as_diagrams=get_bool_setting("use_non_answer_images_as_diagrams", True),
    )


@app.route("/login")
def login():
    """
    登录页：触发 Playwright 打开浏览器，展示等待状态。
    前端轮询 /api/auth/status，登录完成后自动跳转首页。
    """
    ensure_logged_in(wait=False)
    return render_template("login.html")


# ── API 路由 ──────────────────────────────────────────────

@app.route("/api/auth/status")
def auth_status():
    """返回登录状态，供登录页前端轮询"""
    return jsonify(get_login_status())


@app.route("/api/auth/start", methods=["POST"])
def auth_start():
    """手动触发登录（如果浏览器未自动弹出）"""
    start_login_browser()
    return jsonify({"ok": True, "message": "登录浏览器已启动"})


@app.route("/api/sync", methods=["POST"])
def manual_sync():
    """手动触发同步（同步执行）"""
    if not is_token_valid():
        return jsonify({"status": "error", "message": "未登录"}), 401
    body = request.get_json(silent=True) or {}
    use_non_answer_images = bool(body.get("use_non_answer_images_as_diagrams", get_bool_setting("use_non_answer_images_as_diagrams", True)))
    set_bool_setting("use_non_answer_images_as_diagrams", use_non_answer_images)

    result = sync_once(use_non_answer_images=use_non_answer_images)
    return jsonify(result)


@app.route("/api/settings/image-mapping", methods=["GET", "POST"])
def image_mapping_settings():
    if request.method == "GET":
        return jsonify({
            "use_non_answer_images_as_diagrams": get_bool_setting("use_non_answer_images_as_diagrams", True)
        })
    data = request.get_json(silent=True) or {}
    v = bool(data.get("use_non_answer_images_as_diagrams", True))
    set_bool_setting("use_non_answer_images_as_diagrams", v)
    return jsonify({"status": "ok", "use_non_answer_images_as_diagrams": v})


@app.route("/api/sync/status")
def sync_status():
    last = get_last_sync()
    return jsonify(last or {})


@app.route("/api/threads")
def list_threads():
    start = request.args.get("start", "")
    end = request.args.get("end", "")
    page = int(request.args.get("page", 1) or 1)
    page_size = int(request.args.get("page_size", 15) or 15)
    result = get_threads_page(start=start, end=end, page=page, page_size=page_size)
    threads = result["items"]
    for t in threads:
        t["date_str"] = normalize_datetime_text(t.get("date_str", ""), t.get("subject", ""))
    total_pages = (result["total"] + result["page_size"] - 1) // result["page_size"] if result["page_size"] else 0
    return jsonify({
        "items": threads,
        "total": result["total"],
        "page": result["page"],
        "page_size": result["page_size"],
        "total_pages": total_pages
    })


@app.route("/api/sources")
def list_sources():
    start = request.args.get("start", "")
    end = request.args.get("end", "")
    if not start or not end:
        return jsonify([])
    threads = get_threads_by_date_range(start, end)
    for t in threads:
        t["date_str"] = normalize_datetime_text(t.get("date_str", ""), t.get("subject", ""))
    return jsonify([
        {
            "thread_id": t["thread_id"],
            "label": f"{t['date_str']}｜{t['subject']}｜{t.get('author') or '未知'}",
            "subject": t["subject"],
            "author": t.get("author") or "",
            "date": t["date_str"]
        }
        for t in threads
    ])


@app.route("/api/thread/<thread_id>")
def thread_detail(thread_id):
    from shuati.core.database import get_threads_by_ids, get_questions_by_thread

    threads = get_threads_by_ids([thread_id])
    if not threads:
        return jsonify({"error": "Not found"}), 404

    thread = threads[0]
    questions = get_questions_by_thread(thread_id)

    res_qs = []
    for q in questions:
        res_qs.append({
            "seq": q["seq"],
            "content": q["content"],
            "images": json.loads(q["images"] or "[]"),
            "answers": json.loads(q["answers"] or "[]")
        })

    return jsonify({
        "source": {
            "date": normalize_datetime_text(thread.get("date_str", ""), thread.get("subject", "")),
            "author": thread.get("author", ""),
            "type": thread.get("type", "接龙管家打卡接龙"),
            "title": thread.get("subject", "")
        },
        "questions": res_qs
    })


@app.route("/api/thread/<thread_id>", methods=["DELETE"])
def delete_thread_api(thread_id):
    """删除单条接龙"""
    if not is_token_valid():
        return jsonify({"error": "未登录"}), 401
    delete_thread(thread_id)
    return jsonify({"status": "ok", "message": "删除成功"})


@app.route("/api/generate", methods=["POST"])
def generate():
    """生成 Word 文档并返回下载"""
    data = request.get_json()
    start = data.get("start")
    end = data.get("end")
    source_thread_ids = data.get("source_thread_ids") or []
    if (not start or not end) and not source_thread_ids:
        return jsonify({"error": "请选择日期范围"}), 400
    if source_thread_ids and (not start or not end):
        start = "0001-01-01"
        end = "9999-12-31"
    if source_thread_ids and not isinstance(source_thread_ids, list):
        return jsonify({"error": "来源参数格式错误"}), 400
    try:
        path = generate_word(start, end, source_thread_ids=source_thread_ids)
        return send_file(
            path,
            as_attachment=True,
            download_name=os.path.basename(path),
            mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# 提供本地图片访问（供预览用）
@app.route("/images/<path:filename>")
def serve_image(filename):
    images_dir = os.path.join(DATA_DIR, "images")
    return send_file(os.path.join(images_dir, filename))


# ── 启动 ──────────────────────────────────────────────────

def create_app():
    init_db()
    return app


if __name__ == "__main__":
    create_app()
    print(f"\n✅ 打卡题管理工具已启动")
    print(f"   请在浏览器打开：http://localhost:{FLASK_PORT}\n")
    app.run(host="0.0.0.0", port=FLASK_PORT, debug=False)
