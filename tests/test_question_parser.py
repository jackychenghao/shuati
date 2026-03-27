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
        assert len(result) == 3
        assert result[0]["seq"] == 1
        assert result[0]["content"] == "1、"
        assert result[2]["content"] == "3、"
        assert json.loads(result[0]["images_json"]) == []

    def test_plain_text_single_question(self):
        result = parse_questions("计算三角形面积", [], use_non_answer_images=True)
        assert len(result) == 3
        assert result[0]["content"] == "计算三角形面积"
        assert result[1]["content"] == "2、"
        assert result[2]["content"] == "3、"

    def test_image_fallback_to_question_three(self):
        metas = [{"path": "/img/1.jpg", "meta": _make_meta()}]
        result = parse_questions("题目", metas, use_non_answer_images=True)
        assert len(result) == 3
        assert result[2]["images"] == ["/img/1.jpg"]

    def test_image_in_first_three_blocks_goes_by_block_order(self):
        metas = [{"path": "/img/q2.jpg", "meta": _make_meta(), "block_order": 1}]
        result = parse_questions("", metas, use_non_answer_images=True)
        assert len(result) == 3
        assert result[1]["images"] == ["/img/q2.jpg"]
        assert result[2]["images"] == []

    def test_no_images_when_disabled(self):
        metas = [{"path": "/img/1.jpg", "meta": _make_meta()}]
        result = parse_questions("题目", metas, use_non_answer_images=False)
        assert len(result) == 3
        assert result[2]["images"] == []


class TestNumberedQuestions:
    """When text contains numbered questions like '1、', '2、'."""

    def test_basic_split(self):
        text = "1、求面积\n2、求体积"
        result = parse_questions(text, [], use_non_answer_images=True)
        assert len(result) == 3
        assert result[0]["seq"] == 1
        assert "面积" in result[0]["content"]
        assert result[1]["seq"] == 2
        assert "体积" in result[1]["content"]
        assert result[2]["content"] == "3、"

    def test_three_questions(self):
        text = "1、问题一\n2、问题二\n3、问题三"
        result = parse_questions(text, [], use_non_answer_images=True)
        assert len(result) == 3

    def test_single_numbered_three_maps_to_question_three(self):
        text = "3、问题三"
        result = parse_questions(text, [], use_non_answer_images=True)
        assert result[0]["content"] == "1、"
        assert result[1]["content"] == "2、"
        assert "问题三" in result[2]["content"]

    def test_zero_width_three_maps_to_question_three(self):
        text = "\u200b3、问题三"
        result = parse_questions(text, [], use_non_answer_images=True)
        assert result[0]["content"] == "1、"
        assert result[1]["content"] == "2、"
        assert "问题三" in result[2]["content"]

    def test_non_answer_image_goes_to_question_three(self):
        text = "1、求面积\n2、求体积"
        metas = [{"path": "/img/q2.jpg", "meta": _make_meta(question_seq=2)}]
        result = parse_questions(text, metas, use_non_answer_images=True)
        assert result[2]["images"] == ["/img/q2.jpg"]

    def test_answer_image_goes_to_answers(self):
        text = "1、如图所示，求面积\n2、求体积"
        metas = [{"path": "/img/ans.jpg", "meta": _make_meta(text_head="解答：先化简")}]
        result = parse_questions(text, metas, use_non_answer_images=True)
        assert result[2]["answers"] == ["/img/ans.jpg"]
        assert result[2]["images"] == []

    def test_first_three_blocks_answer_image_prioritized_to_answers(self):
        text = "1、求面积\n2、求体积"
        metas = [{"path": "/img/q1.jpg", "meta": _make_meta(text_head="解答："), "block_order": 0}]
        result = parse_questions(text, metas, use_non_answer_images=True)
        assert result[0]["images"] == []
        assert result[2]["answers"] == ["/img/q1.jpg"]

    def test_no_images_when_disabled(self):
        text = "1、求面积\n2、求体积"
        metas = [{"path": "/img/q1.jpg", "meta": _make_meta(question_seq=1)}]
        result = parse_questions(text, metas, use_non_answer_images=False)
        assert result[0]["images"] == []
        assert result[1]["images"] == []
        assert result[2]["images"] == []


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
        metas = [{"path": "/img/1.jpg", "meta": _make_meta()}]
        result = parse_questions("1、题目", metas, use_non_answer_images=True)
        assert json.loads(result[2]["images_json"]) == ["/img/1.jpg"]
