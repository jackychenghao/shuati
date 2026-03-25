import re
from functools import lru_cache


@lru_cache(maxsize=1)
def _get_backend():
    try:
        from ocrmac.ocrmac import OCR
        return ("ocrmac", OCR)
    except Exception:
        pass
    try:
        from rapidocr_onnxruntime import RapidOCR
        return ("rapidocr", RapidOCR())
    except Exception:
        return None


def _normalize_text(s: str) -> str:
    return re.sub(r"\s+", "", (s or ""))


def _parse_question_seq(text: str) -> int | None:
    s = _normalize_text(text)
    patterns = [
        r"^第(\d+)题",
        r"^(\d+)[、.]",
        r"^(\d+)\)",
        r"^(\d+)）",
    ]
    for p in patterns:
        m = re.search(p, s)
        if m:
            try:
                return int(m.group(1))
            except Exception:
                return None
    return None


def _looks_like_question_text(text: str) -> bool:
    s = _normalize_text(text)
    if len(s) < 8:
        return False
    if _parse_question_seq(s) is not None:
        return True
    if "问" in s or "求" in s or "已知" in s:
        return True
    return False


def analyze_image_text(image_path: str) -> dict:
    empty_result = {
        "is_answer": False,
        "question_seq": None,
        "looks_like_question": False,
        "text_head": "",
        "text_full": "",
    }
    backend = _get_backend()
    if backend is None:
        return empty_result
    texts = []
    kind, engine = backend
    if kind == "ocrmac":
        try:
            result = engine(
                image_path,
                recognition_level="accurate",
                language_preference=["zh-Hans", "en-US"],
                confidence_threshold=0.15,
                detail=True,
            ).recognize()
        except Exception:
            return empty_result
        if not result:
            return empty_result
        for item in result:
            if not item or len(item) < 3:
                continue
            text = str(item[0] or "")
            bbox = item[2]
            if not text or not bbox or len(bbox) < 2:
                continue
            texts.append((float(bbox[1]), float(bbox[0]), text))
    else:
        try:
            result, _ = engine(image_path)
        except Exception:
            return empty_result
        if not result:
            return empty_result
        for item in result:
            if not item or len(item) < 2:
                continue
            box = item[0]
            text = item[1]
            if not box or not text:
                continue
            xs = [p[0] for p in box]
            ys = [p[1] for p in box]
            texts.append((min(ys), min(xs), str(text)))
    if not texts:
        return empty_result
    asc = sorted(texts, key=lambda x: (x[0], x[1]))
    desc = sorted(texts, key=lambda x: (-x[0], x[1]))
    asc_texts = [t[2] for t in asc]
    head_asc = _normalize_text("".join(asc_texts[:3]))
    head_desc = _normalize_text("".join([t[2] for t in desc[:3]]))
    full_text = "\n".join(asc_texts)
    seq = _parse_question_seq(head_asc) or _parse_question_seq(_normalize_text(full_text))
    return {
        "is_answer": head_asc.startswith("解答") or head_desc.startswith("解答"),
        "question_seq": seq,
        "looks_like_question": _looks_like_question_text(head_asc) or _looks_like_question_text(full_text),
        "text_head": head_asc,
        "text_full": full_text,
    }


def image_starts_with_answer(image_path: str) -> bool:
    return analyze_image_text(image_path)["is_answer"]
