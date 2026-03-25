"""
Tests for database.py using in-memory SQLite.
"""
import sqlite3
import json

import shuati.core.database as database
from shuati.core.database import (
    init_db_from_conn, reset_connection,
    save_thread, thread_exists, thread_subject_date_exists,
    get_all_threads, get_threads_by_date_range, get_threads_by_ids, get_threads_page,
    get_questions_by_thread, get_blocks_by_thread,
    delete_thread, get_thread_count,
    log_sync, get_last_sync,
    get_setting, set_setting, get_bool_setting, set_bool_setting,
)


def _setup_memory_db():
    """Create an in-memory DB and initialize tables."""
    reset_connection()
    conn = sqlite3.connect(":memory:")
    init_db_from_conn(conn)
    return conn


def _save_sample_thread(thread_id="T001", subject="20260312小六打卡", date_str="2026-03-12 18:00:00", author="老师"):
    """Save a sample thread with blocks and questions."""
    blocks = [
        {"content_type": 11, "text": "1、求面积", "image_url": None, "image_local": None},
        {"content_type": 4, "text": None, "image_url": "https://example.com/img.jpg", "image_local": "/img/1.jpg"},
    ]
    questions = [
        {"seq": 1, "content": "求面积", "images_json": json.dumps(["/img/1.jpg"]), "answers_json": "[]"},
        {"seq": 2, "content": "求体积", "images_json": "[]", "answers_json": "[]"},
    ]
    save_thread(thread_id, subject, date_str, author, blocks, questions)


class TestInitDB:
    def test_init_creates_tables(self):
        conn = _setup_memory_db()
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        table_names = {t[0] for t in tables}
        assert "threads" in table_names
        assert "questions" in table_names
        assert "blocks" in table_names
        assert "sync_log" in table_names
        assert "app_settings" in table_names
        reset_connection()


class TestSaveAndQuery:
    def setup_method(self):
        _setup_memory_db()

    def teardown_method(self):
        reset_connection()

    def test_save_and_exists(self):
        _save_sample_thread()
        assert thread_exists("T001") is True
        assert thread_exists("NONEXISTENT") is False

    def test_subject_date_exists(self):
        _save_sample_thread()
        assert thread_subject_date_exists("20260312小六打卡", "2026-03-12 18:00:00") is True
        assert thread_subject_date_exists("20260312小六打卡", "2026-03-13 18:00:00") is False
        assert thread_subject_date_exists("不存在的标题", "2026-03-12 18:00:00") is False

    def test_get_all_threads(self):
        _save_sample_thread("T001")
        _save_sample_thread("T002", subject="20260313打卡", date_str="2026-03-13 08:00:00")
        threads = get_all_threads(100)
        assert len(threads) == 2
        # Should be sorted by date DESC
        assert threads[0]["thread_id"] == "T002"

    def test_get_threads_by_date_range(self):
        _save_sample_thread("T001", date_str="2026-03-12 18:00:00")
        _save_sample_thread("T002", date_str="2026-03-15 08:00:00")
        result = get_threads_by_date_range("2026-03-12", "2026-03-13")
        assert len(result) == 1
        assert result[0]["thread_id"] == "T001"

    def test_get_threads_by_ids(self):
        _save_sample_thread("T001")
        _save_sample_thread("T002")
        result = get_threads_by_ids(["T001"])
        assert len(result) == 1
        assert result[0]["thread_id"] == "T001"

    def test_get_threads_by_ids_empty(self):
        assert get_threads_by_ids([]) == []

    def test_get_questions_by_thread(self):
        _save_sample_thread()
        questions = get_questions_by_thread("T001")
        assert len(questions) == 2
        assert questions[0]["seq"] == 1
        assert questions[1]["seq"] == 2

    def test_get_blocks_by_thread(self):
        _save_sample_thread()
        blocks = get_blocks_by_thread("T001")
        assert len(blocks) == 2
        assert blocks[0]["content_type"] == 11
        assert blocks[1]["content_type"] == 4


class TestPagination:
    def setup_method(self):
        _setup_memory_db()

    def teardown_method(self):
        reset_connection()

    def test_basic_pagination(self):
        for i in range(10):
            _save_sample_thread(f"T{i:03d}", date_str=f"2026-03-{i+1:02d} 08:00:00")
        result = get_threads_page(page=1, page_size=3)
        assert result["total"] == 10
        assert result["page"] == 1
        assert result["page_size"] == 3
        assert len(result["items"]) == 3

    def test_page_2(self):
        for i in range(5):
            _save_sample_thread(f"T{i:03d}", date_str=f"2026-03-{i+1:02d} 08:00:00")
        result = get_threads_page(page=2, page_size=3)
        assert len(result["items"]) == 2

    def test_date_filtered_pagination(self):
        for i in range(10):
            _save_sample_thread(f"T{i:03d}", date_str=f"2026-03-{i+1:02d} 08:00:00")
        result = get_threads_page(start="2026-03-03", end="2026-03-07", page=1, page_size=100)
        assert result["total"] == 5


class TestDeleteThread:
    def setup_method(self):
        _setup_memory_db()

    def teardown_method(self):
        reset_connection()

    def test_delete_removes_thread_and_related(self):
        _save_sample_thread()
        assert thread_exists("T001") is True
        delete_thread("T001")
        assert thread_exists("T001") is False
        assert get_questions_by_thread("T001") == []
        assert get_blocks_by_thread("T001") == []


class TestThreadCount:
    def setup_method(self):
        _setup_memory_db()

    def teardown_method(self):
        reset_connection()

    def test_count(self):
        assert get_thread_count() == 0
        _save_sample_thread("T001")
        assert get_thread_count() == 1
        _save_sample_thread("T002")
        assert get_thread_count() == 2


class TestSyncLog:
    def setup_method(self):
        _setup_memory_db()

    def teardown_method(self):
        reset_connection()

    def test_log_and_get(self):
        assert get_last_sync() is None
        log_sync(5, "success", "同步完成")
        last = get_last_sync()
        assert last is not None
        assert last["new_count"] == 5
        assert last["status"] == "success"

    def test_latest_log_returned(self):
        log_sync(3, "success", "第一次")
        log_sync(7, "success", "第二次")
        last = get_last_sync()
        assert last["new_count"] == 7


class TestSettings:
    def setup_method(self):
        _setup_memory_db()

    def teardown_method(self):
        reset_connection()

    def test_get_default(self):
        assert get_setting("nonexistent") is None
        assert get_setting("nonexistent", "default") == "default"

    def test_set_and_get(self):
        set_setting("key1", "value1")
        assert get_setting("key1") == "value1"

    def test_overwrite(self):
        set_setting("key1", "old")
        set_setting("key1", "new")
        assert get_setting("key1") == "new"

    def test_bool_setting_true(self):
        set_bool_setting("flag", True)
        assert get_bool_setting("flag") is True

    def test_bool_setting_false(self):
        set_bool_setting("flag", False)
        assert get_bool_setting("flag") is False

    def test_bool_setting_default(self):
        assert get_bool_setting("unset", True) is True
        assert get_bool_setting("unset", False) is False
