"""
Question parser — extracts structured questions from raw text and OCR image metadata.

This module contains pure functions (no I/O) that can be easily unit-tested.
"""
import re
import json


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
    # Split text into questions by numbered patterns like "1、", "2.", etc.
    normalized_text = "\n" + all_text
    raw_qs = re.split(r'(?=\n\s*[\u200B-\u200D\uFEFF]*\d+[、.])', normalized_text)
    qs = [q.strip() for q in raw_qs if q.strip()]

    # Separate answer images from content images
    # (Currently answers are not used, but kept for future compatibility)
    answer_images = []
    content_images = image_metas

    if not qs:
        questions_data = _parse_no_text_questions(content_images, answer_images, use_non_answer_images, all_text)
    else:
        questions_data = _parse_numbered_questions(qs, content_images, answer_images, use_non_answer_images)

    # Serialize image/answer lists to JSON
    for q in questions_data:
        q["images_json"] = json.dumps(q["images"])
        q["answers_json"] = json.dumps(q["answers"])

    return questions_data


def _parse_no_text_questions(
    content_images: list[dict],
    answer_images: list[dict],
    use_non_answer_images: bool,
    all_text: str,
) -> list[dict]:
    """Handle case where no numbered questions were found in text."""
    questions_data = [{
        "seq": 1,
        "content": all_text.strip(),
        "images": [],
        "answers": [],
    }]

    if use_non_answer_images:
        for item in content_images:
            meta = item["meta"]
            if meta["question_seq"] and meta["question_seq"] > len(questions_data):
                seq = meta["question_seq"]
                while len(questions_data) < seq:
                    questions_data.append({
                        "seq": len(questions_data) + 1,
                        "content": f"第{len(questions_data) + 1}题（图片题）",
                        "images": [],
                        "answers": [],
                    })
                questions_data[seq - 1]["images"].append(item["path"])
            elif (meta["looks_like_question"]
                  and len(questions_data) == 1
                  and questions_data[0]["content"] == ""):
                questions_data[0]["content"] = meta["text_full"][:240] or "图片题"
                questions_data[0]["images"].append(item["path"])
            else:
                questions_data[-1]["images"].append(item["path"])

    for i, item in enumerate(answer_images):
        idx = i if i < len(questions_data) else len(questions_data) - 1
        questions_data[idx]["answers"].append(item["path"])

    return questions_data


def _parse_numbered_questions(
    qs: list[str],
    content_images: list[dict],
    answer_images: list[dict],
    use_non_answer_images: bool,
) -> list[dict]:
    """Handle case where numbered questions were found in text."""
    diagram_needs = [bool(re.search(r'如图', q)) for q in qs]

    questions_data = []
    for i, q in enumerate(qs):
        questions_data.append({
            "seq": i + 1,
            "content": q,
            "images": [],
            "answers": [],
        })

    if use_non_answer_images:
        pending_diagrams = []
        for item in content_images:
            meta = item["meta"]
            seq = meta["question_seq"]
            if seq and 1 <= seq <= len(questions_data):
                questions_data[seq - 1]["images"].append(item["path"])
            elif seq and seq > len(questions_data):
                while len(questions_data) < seq:
                    questions_data.append({
                        "seq": len(questions_data) + 1,
                        "content": f"第{len(questions_data) + 1}题（图片题）",
                        "images": [],
                        "answers": [],
                    })
                questions_data[seq - 1]["images"].append(item["path"])
            elif meta["looks_like_question"]:
                questions_data.append({
                    "seq": len(questions_data) + 1,
                    "content": meta["text_full"][:240] or f"第{len(questions_data) + 1}题（图片题）",
                    "images": [item["path"]],
                    "answers": [],
                })
            else:
                pending_diagrams.append(item["path"])

        # Assign pending diagrams to questions that mention "如图"
        need_indices = [
            i for i in range(min(len(qs), len(questions_data)))
            if diagram_needs[i] and not questions_data[i]["images"]
        ]
        for path in pending_diagrams:
            if need_indices:
                idx = need_indices.pop(0)
                questions_data[idx]["images"].append(path)
            else:
                questions_data[min(len(qs), len(questions_data)) - 1]["images"].append(path)

    for i, item in enumerate(answer_images):
        seq = item["meta"]["question_seq"]
        if seq and 1 <= seq <= len(questions_data):
            idx = seq - 1
        else:
            idx = i if i < len(questions_data) else len(questions_data) - 1
        questions_data[idx]["answers"].append(item["path"])

    return questions_data
