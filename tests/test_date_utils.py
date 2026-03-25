"""
Tests for date_utils.normalize_datetime_text().
"""
import re
from datetime import datetime, timedelta

from shuati.core.date_utils import normalize_datetime_text


class TestStandardDates:
    """Standard date format parsing."""

    def test_full_datetime(self):
        result = normalize_datetime_text("2026-03-12 18:20:30")
        assert result == "2026-03-12 18:20:30"

    def test_date_with_dots(self):
        result = normalize_datetime_text("2026.03.12 18:20")
        assert result == "2026-03-12 18:20:00"

    def test_date_with_slashes(self):
        result = normalize_datetime_text("2026/03/12 18:20")
        assert result == "2026-03-12 18:20:00"

    def test_date_only(self):
        result = normalize_datetime_text("2026-03-12")
        assert result == "2026-03-12 00:00:00"


class TestRelativeDates:
    """Relative date expressions like '昨天', '前天', 'N天前'."""

    def test_today(self):
        result = normalize_datetime_text("今天 18:20")
        now = datetime.now()
        expected_date = now.strftime("%Y-%m-%d")
        assert result == f"{expected_date} 18:20:00"

    def test_yesterday(self):
        result = normalize_datetime_text("昨天 09:00")
        expected = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        assert result == f"{expected} 09:00:00"

    def test_day_before_yesterday(self):
        result = normalize_datetime_text("前天 14:30")
        expected = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
        assert result == f"{expected} 14:30:00"

    def test_n_days_ago(self):
        result = normalize_datetime_text("3天前 18:20")
        expected = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")
        assert result == f"{expected} 18:20:00"


class TestMonthDayFormat:
    """Month.Day HH:MM format."""

    def test_month_day_with_dot(self):
        result = normalize_datetime_text("3.12 18:20")
        # Should produce a date in the current year
        assert re.match(r"\d{4}-03-12 18:20:00", result)


class TestSubjectFallback:
    """Extracting date from subject when raw text is empty."""

    def test_extract_from_subject(self):
        result = normalize_datetime_text("", "20260312小六打卡")
        assert result == "2026-03-12 00:00:00"

    def test_empty_subject_returns_empty(self):
        result = normalize_datetime_text("", "")
        assert result == ""

    def test_subject_no_date(self):
        result = normalize_datetime_text("", "每日打卡题")
        assert result == ""

    def test_subject_fallback_when_raw_unrecognized(self):
        result = normalize_datetime_text("不认识的格式", "20260315小六打卡")
        assert result == "2026-03-15 00:00:00"


class TestEdgeCases:
    """Edge cases and unusual inputs."""

    def test_empty_input(self):
        result = normalize_datetime_text("")
        assert result == ""

    def test_none_input(self):
        result = normalize_datetime_text(None)
        assert result == ""

    def test_unrecognized_format_passthrough(self):
        # If nothing matches and no subject, return raw text
        result = normalize_datetime_text("unknown_format")
        assert result == "unknown_format"
