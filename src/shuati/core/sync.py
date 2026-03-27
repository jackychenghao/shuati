"""
采集引擎：从接龙管家拉取新题目并入库。
可手动调用，也可由定时任务触发。
"""
from shuati.core.auth import ensure_logged_in, is_token_valid
from shuati.core.jielong_api import fetch_all_favorites, fetch_thread_detail, download_image
from shuati.core.database import thread_exists, thread_subject_date_exists, save_thread, update_image_local, log_sync, init_db, get_bool_setting
from shuati.core.date_utils import normalize_datetime_text
from shuati.core.ocr_utils import analyze_image_text
from shuati.core.question_parser import parse_questions


def sync_once(force: bool = False, use_non_answer_images: bool | None = None) -> dict:
    """
    执行一次同步。
    force=True 时重新拉取已存在的条目（用于调试）。
    返回 {'new_count': int, 'status': str, 'message': str}
    """
    if not is_token_valid():
        return {"new_count": 0, "status": "error", "message": "未登录，请先扫码"}
    if use_non_answer_images is None:
        use_non_answer_images = get_bool_setting("use_non_answer_images_as_diagrams", True)

    try:
        print("[Sync] 开始同步...")
        favorites = fetch_all_favorites()
        new_count = 0

        for fav in favorites:
            tid = fav["thread_id"]
            if not tid:
                continue

            if not force and thread_exists(tid):
                print(f"[Sync] 已存在，跳过：{fav['subject']}")
                continue

            list_date = normalize_datetime_text(fav.get("date_created", ""), fav.get("subject", ""))
            if list_date and thread_subject_date_exists(fav["subject"], list_date):
                print(f"[Sync] 已存在相同标题和日期的题目，跳过：{fav['subject']} ({list_date})")
                continue

            print(f"[Sync] 新增：{fav['subject']}")
            detail = fetch_thread_detail(tid)
            if not detail:
                print(f"[Sync] 获取详情失败：{tid}")
                continue

            # 再次检查去重（使用详情中更准确的日期）
            if thread_subject_date_exists(detail["subject"], detail["date_str"]):
                print(f"[Sync] 已存在相同标题和日期的题目（二次检查），跳过：{detail['subject']} ({detail['date_str']})")
                continue

            # 提取所有文本和图片，下载图片并做 OCR 分析
            all_text, image_metas = _collect_content(detail["blocks"], tid)

            # 使用提取的解析器生成结构化题目
            questions_data = parse_questions(all_text, image_metas, use_non_answer_images)

            # 入库
            save_thread(
                thread_id=detail["thread_id"],
                subject=detail["subject"],
                date_str=detail["date_str"],
                author=detail["author"],
                blocks=detail["blocks"],
                questions=questions_data
            )
            new_count += 1

        msg = f"同步完成，新增 {new_count} 条"
        print(f"[Sync] {msg}")
        log_sync(new_count, "success", msg)
        return {"new_count": new_count, "status": "success", "message": msg}

    except Exception as e:
        msg = str(e)
        print(f"[Sync] 出错：{msg}")
        log_sync(0, "error", msg)
        return {"new_count": 0, "status": "error", "message": msg}


def _collect_content(blocks: list[dict], thread_id: str) -> tuple[str, list[dict]]:
    """
    Extract text and download/analyze images from thread blocks.

    Returns:
        (all_text, image_metas) where image_metas is a list of
        {"path": str, "meta": dict} items.
    """
    all_text = ""
    all_images = []

    for i, block in enumerate(blocks):
        if block["content_type"] == 11 and block.get("text"):
            all_text += block["text"] + "\n"
        elif block["content_type"] == 4 and block.get("image_url"):
            local = download_image(block["image_url"], thread_id)
            block["image_local"] = local
            if local:
                all_images.append((local, i))

    image_metas = []
    for img, block_order in all_images:
        meta = analyze_image_text(img)
        if not isinstance(meta, dict):
            meta = {
                "is_answer": False,
                "question_seq": None,
                "looks_like_question": False,
                "text_head": "",
                "text_full": "",
            }
        # 目的：把原始块顺序传给解析器，支持稳定题图归类。
        image_metas.append({"path": img, "meta": meta, "block_order": block_order})

    return all_text, image_metas


if __name__ == "__main__":
    init_db()
    ensure_logged_in(wait=True)
    result = sync_once()
    print(result)
