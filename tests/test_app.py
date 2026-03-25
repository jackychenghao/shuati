"""
Tests for Flask web app routes using test client.
"""
import json
import sqlite3
from unittest.mock import patch

import shuati.core.database as database
from shuati.core.database import init_db_from_conn, reset_connection, save_thread


def _setup_test_app():
    """Create a test Flask app with in-memory DB."""
    reset_connection()
    conn = sqlite3.connect(":memory:")
    init_db_from_conn(conn)

    from shuati.web.app import app
    app.config["TESTING"] = True
    return app.test_client()


def _save_sample_thread(thread_id="T001", subject="20260312小六打卡", date_str="2026-03-12 18:00:00"):
    blocks = [
        {"content_type": 11, "text": "1、求面积", "image_url": None, "image_local": None},
    ]
    questions = [
        {"seq": 1, "content": "求面积", "images_json": json.dumps([]), "answers_json": "[]"},
    ]
    save_thread(thread_id, subject, date_str, "老师", blocks, questions)


class TestIndexRoute:
    def setup_method(self):
        self.client = _setup_test_app()

    def teardown_method(self):
        reset_connection()

    @patch("shuati.web.app.is_token_valid", return_value=False)
    def test_redirect_when_not_logged_in(self, mock_valid):
        resp = self.client.get("/")
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]

    @patch("shuati.web.app.is_token_valid", return_value=True)
    def test_index_when_logged_in(self, mock_valid):
        resp = self.client.get("/")
        assert resp.status_code == 200


class TestThreadsAPI:
    def setup_method(self):
        self.client = _setup_test_app()

    def teardown_method(self):
        reset_connection()

    def test_list_threads_empty(self):
        resp = self.client.get("/api/threads")
        data = json.loads(resp.data)
        assert data["total"] == 0
        assert data["items"] == []

    def test_list_threads_with_data(self):
        _save_sample_thread("T001")
        _save_sample_thread("T002", subject="20260313打卡", date_str="2026-03-13 08:00:00")
        resp = self.client.get("/api/threads")
        data = json.loads(resp.data)
        assert data["total"] == 2

    def test_list_threads_pagination(self):
        for i in range(5):
            _save_sample_thread(f"T{i:03d}", date_str=f"2026-03-{i+1:02d} 08:00:00")
        resp = self.client.get("/api/threads?page=1&page_size=2")
        data = json.loads(resp.data)
        assert len(data["items"]) == 2
        assert data["total"] == 5


class TestThreadDetailAPI:
    def setup_method(self):
        self.client = _setup_test_app()

    def teardown_method(self):
        reset_connection()

    def test_not_found(self):
        resp = self.client.get("/api/thread/NONEXISTENT")
        assert resp.status_code == 404

    def test_found(self):
        _save_sample_thread()
        resp = self.client.get("/api/thread/T001")
        data = json.loads(resp.data)
        assert "source" in data
        assert "questions" in data
        assert data["source"]["title"] == "20260312小六打卡"


class TestDeleteThreadAPI:
    def setup_method(self):
        self.client = _setup_test_app()

    def teardown_method(self):
        reset_connection()

    @patch("shuati.web.app.is_token_valid", return_value=False)
    def test_delete_unauthorized(self, mock_valid):
        resp = self.client.delete("/api/thread/T001")
        assert resp.status_code == 401

    @patch("shuati.web.app.is_token_valid", return_value=True)
    def test_delete_success(self, mock_valid):
        _save_sample_thread()
        resp = self.client.delete("/api/thread/T001")
        data = json.loads(resp.data)
        assert data["status"] == "ok"


class TestGenerateAPI:
    def setup_method(self):
        self.client = _setup_test_app()

    def teardown_method(self):
        reset_connection()

    def test_generate_missing_params(self):
        resp = self.client.post("/api/generate",
            data=json.dumps({}),
            content_type="application/json"
        )
        assert resp.status_code == 400


class TestSyncAPI:
    def setup_method(self):
        self.client = _setup_test_app()

    def teardown_method(self):
        reset_connection()

    @patch("shuati.web.app.is_token_valid", return_value=False)
    def test_sync_unauthorized(self, mock_valid):
        resp = self.client.post("/api/sync",
            data=json.dumps({}),
            content_type="application/json"
        )
        assert resp.status_code == 401


class TestSourcesAPI:
    def setup_method(self):
        self.client = _setup_test_app()

    def teardown_method(self):
        reset_connection()

    def test_sources_without_dates(self):
        resp = self.client.get("/api/sources")
        data = json.loads(resp.data)
        assert data == []

    def test_sources_with_dates(self):
        _save_sample_thread()
        resp = self.client.get("/api/sources?start=2026-03-01&end=2026-03-31")
        data = json.loads(resp.data)
        assert len(data) == 1
        assert data[0]["thread_id"] == "T001"
