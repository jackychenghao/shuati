"""
Question parser — extracts structured questions from raw text and OCR image metadata.

This module contains pure functions (no I/O) that can be easily unit-tested.
"""
import re
import json


def _extract_leading_seq(text: str) -> int | None:
    s = str(text or "").lstrip("\u200b\u200c\u200d\ufeff\xa0 \t\r\n")
    m = re.search(r"(\d+)[、\.\)]", s[:24])
    if not m:
        return None
    try:
        return int(m.group(1))
    except Exception:
        return None


def parse_questions(
    all_text: str,
    image_metas: list[dict],
    use_non_answer_images: bool = True,
) -> list[dict]:
    """
    Parse raw text + image OCR metadata into structured question list.

    Args:
        all_text: Concatenated text from all text blocks.
        image_metas: List of dicts with keys:
            - path (str): local image path
            - meta (dict): OCR analysis result from analyze_image_text()
        use_non_answer_images: Whether to assign non-answer images as diagrams.

    Returns:
        List of question dicts, each with:
            {seq, content, images, answers, images_json, answers_json}
    """
    normalized_text = "\n" + all_text
    raw_qs = re.split(r'(?=\n\s*[\u200B-\u200D\uFEFF]*\d+[、.])', normalized_text)
    qs = [q.strip() for q in raw_qs if q.strip()]
    questions_data = _build_three_questions(qs, all_text)
    _attach_images(questions_data, image_metas, use_non_answer_images)

    for q in questions_data:
        q["images_json"] = json.dumps(q["images"])
        q["answers_json"] = json.dumps(q["answers"])

    return questions_data


def _build_three_questions(qs: list[str], all_text: str) -> list[dict]:
    ordered = [None, None, None]
    if qs:
        overflow = []
        for q in qs:
            seq = _extract_leading_seq(q)
            if seq and 1 <= seq <= 3 and not ordered[seq - 1]:
                ordered[seq - 1] = q
                continue
            overflow.append(q)
        for q in overflow:
            for i in range(3):
                if not ordered[i]:
                    ordered[i] = q
                    break
    elif all_text.strip():
        ordered[0] = all_text.strip()

    questions_data = []
    for i in range(3):
        content = ordered[i] if ordered[i] else f"{i + 1}、"
        questions_data.append({
            "seq": i + 1,
            "content": content,
            "images": [],
            "answers": [],
        })
    return questions_data


def _is_answer_image(meta: dict) -> bool:
    if not isinstance(meta, dict):
        return False
    text_head = str(meta.get("text_head") or "").strip()
    return bool(meta.get("is_answer")) or text_head.startswith(("解答", "答案", "答：", "答:"))


def _attach_images(questions_data: list[dict], image_metas: list[dict], use_non_answer_images: bool):
    # 目的：稳定落图策略，首3个块内的图片按块位映射到题干，后续非答案图统一归到第3题。
    for item in image_metas:
        path = item.get("path")
        if not path:
            continue

        block_order = item.get("block_order")
        meta = item.get("meta") or {}
        if _is_answer_image(meta):
            questions_data[2]["answers"].append(path)
            continue

        if isinstance(block_order, int) and block_order < 3:
            idx = min(block_order, 2)
            questions_data[idx]["images"].append(path)
            continue

        if use_non_answer_images:
            questions_data[2]["images"].append(path)
