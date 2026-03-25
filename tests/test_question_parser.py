"""
Tests for question_parser.parse_questions() — pure function, no I/O.
"""
import json

from shuati.core.question_parser import parse_questions


def _make_meta(is_answer=False, question_seq=None, looks_like_question=False, text_head="", text_full=""):
    return {
        "is_answer": is_answer,
        "question_seq": question_seq,
        "looks_like_question": looks_like_question,
        "text_head": text_head,
        "text_full": text_full,
    }


class TestNoText:
    """When no numbered questions exist in text."""

    def test_empty_text_no_images(self):
        result = parse_questions("", [], use_non_answer_images=True)
        assert len(result) == 1
        assert result[0]["seq"] == 1
        assert result[0]["content"] == ""
        assert result[0]["images"] == []
        assert json.loads(result[0]["images_json"]) == []

    def test_plain_text_single_question(self):
        result = parse_questions("计算三角形面积", [], use_non_answer_images=True)
        assert len(result) == 1
        assert result[0]["content"] == "计算三角形面积"

    def test_image_assigned_to_single_question(self):
        metas = [{"path": "/img/1.jpg", "meta": _make_meta()}]
        result = parse_questions("题目", metas, use_non_answer_images=True)
        assert len(result) == 1
        assert result[0]["images"] == ["/img/1.jpg"]

    def test_image_with_seq_creates_new_questions(self):
        metas = [{"path": "/img/q3.jpg", "meta": _make_meta(question_seq=3)}]
        result = parse_questions("", metas, use_non_answer_images=True)
        assert len(result) == 3
        assert result[2]["images"] == ["/img/q3.jpg"]
        assert result[0]["content"] == ""  # original empty question
        assert result[1]["content"] == "第2题（图片题）"

    def test_no_images_when_disabled(self):
        metas = [{"path": "/img/1.jpg", "meta": _make_meta()}]
        result = parse_questions("题目", metas, use_non_answer_images=False)
        assert len(result) == 1
        assert result[0]["images"] == []


class TestNumberedQuestions:
    """When text contains numbered questions like '1、', '2、'."""

    def test_basic_split(self):
        text = "1、求面积\n2、求体积"
        result = parse_questions(text, [], use_non_answer_images=True)
        assert len(result) == 2
        assert result[0]["seq"] == 1
        assert "面积" in result[0]["content"]
        assert result[1]["seq"] == 2
        assert "体积" in result[1]["content"]

    def test_three_questions(self):
        text = "1、问题一\n2、问题二\n3、问题三"
        result = parse_questions(text, [], use_non_answer_images=True)
        assert len(result) == 3

    def test_image_assigned_by_seq(self):
        text = "1、求面积\n2、求体积"
        metas = [{"path": "/img/q2.jpg", "meta": _make_meta(question_seq=2)}]
        result = parse_questions(text, metas, use_non_answer_images=True)
        assert result[1]["images"] == ["/img/q2.jpg"]
        assert result[0]["images"] == []

    def test_diagram_assigned_to_rutu(self):
        text = "1、如图所示，求面积\n2、求体积"
        metas = [{"path": "/img/diagram.jpg", "meta": _make_meta()}]
        result = parse_questions(text, metas, use_non_answer_images=True)
        # Question 1 mentions "如图" so pending diagram goes there
        assert result[0]["images"] == ["/img/diagram.jpg"]

    def test_diagram_fallback_to_last_question(self):
        text = "1、求面积\n2、求体积"
        metas = [{"path": "/img/extra.jpg", "meta": _make_meta()}]
        result = parse_questions(text, metas, use_non_answer_images=True)
        # No question mentions "如图", so goes to last question
        assert result[1]["images"] == ["/img/extra.jpg"]

    def test_looks_like_question_creates_new(self):
        text = "1、求面积"
        metas = [{"path": "/img/q_img.jpg", "meta": _make_meta(
            looks_like_question=True, text_full="第2题 图片题内容"
        )}]
        result = parse_questions(text, metas, use_non_answer_images=True)
        assert len(result) == 2
        assert result[1]["images"] == ["/img/q_img.jpg"]

    def test_no_images_when_disabled(self):
        text = "1、求面积\n2、求体积"
        metas = [{"path": "/img/q1.jpg", "meta": _make_meta(question_seq=1)}]
        result = parse_questions(text, metas, use_non_answer_images=False)
        assert result[0]["images"] == []
        assert result[1]["images"] == []


class TestJsonSerialization:
    """Verify images_json and answers_json are properly serialized."""

    def test_json_fields_present(self):
        result = parse_questions("1、题目", [], use_non_answer_images=True)
        for q in result:
            assert "images_json" in q
            assert "answers_json" in q
            assert json.loads(q["images_json"]) == q["images"]
            assert json.loads(q["answers_json"]) == q["answers"]

    def test_json_with_images(self):
        metas = [{"path": "/img/1.jpg", "meta": _make_meta(question_seq=1)}]
        result = parse_questions("1、题目", metas, use_non_answer_images=True)
        assert json.loads(result[0]["images_json"]) == ["/img/1.jpg"]
