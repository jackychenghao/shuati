"""
Tests for ocr_utils pure functions (no OCR engine needed).
"""
from shuati.core.ocr_utils import _normalize_text, _parse_question_seq, _looks_like_question_text


class TestNormalizeText:
    """Tests for whitespace normalization."""

    def test_strips_spaces(self):
        assert _normalize_text("  hello  world  ") == "helloworld"

    def test_strips_newlines(self):
        assert _normalize_text("hello\nworld") == "helloworld"

    def test_strips_tabs(self):
        assert _normalize_text("hello\tworld") == "helloworld"

    def test_empty_string(self):
        assert _normalize_text("") == ""

    def test_none_input(self):
        assert _normalize_text(None) == ""


class TestParseQuestionSeq:
    """Tests for question number extraction."""

    def test_chinese_number_format(self):
        # "1、题目内容"
        assert _parse_question_seq("1、求三角形面积") == 1

    def test_dot_format(self):
        assert _parse_question_seq("2.计算下列各题") == 2

    def test_parenthesis_format(self):
        assert _parse_question_seq("3)求解方程") == 3

    def test_chinese_parenthesis(self):
        assert _parse_question_seq("4）已知条件") == 4

    def test_di_n_ti_format(self):
        assert _parse_question_seq("第5题 求解") == 5

    def test_multidigit_number(self):
        assert _parse_question_seq("12、填空题") == 12

    def test_no_match(self):
        assert _parse_question_seq("这是一段普通文字") is None

    def test_empty_string(self):
        assert _parse_question_seq("") is None

    def test_with_whitespace(self):
        # Whitespace is stripped before matching
        assert _parse_question_seq("  1、 题目  ") == 1


class TestLooksLikeQuestionText:
    """Tests for question text detection."""

    def test_short_text_not_question(self):
        # < 8 chars after normalization
        assert _looks_like_question_text("你好") is False

    def test_with_question_number(self):
        assert _looks_like_question_text("1、计算下列各题的面积") is True

    def test_with_wen_keyword(self):
        assert _looks_like_question_text("这道题问的是什么答案呢请回答") is True

    def test_with_qiu_keyword(self):
        assert _looks_like_question_text("求三角形的面积是多少平方厘米") is True

    def test_with_yizhi_keyword(self):
        assert _looks_like_question_text("已知三角形的底是十厘米高是五厘米") is True

    def test_plain_text_not_question(self):
        assert _looks_like_question_text("请各位同学将当日完成的作业拍照上传到群里") is False

    def test_empty_not_question(self):
        assert _looks_like_question_text("") is False
