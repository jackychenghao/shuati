"""
Tests for shuati CLI.

Uses in-memory database and mocks to avoid dependency on real data.
"""
import os
import sys
import json
import sqlite3

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import yaml
from click.testing import CliRunner

import shuati.core.database as database
from shuati.core.database import init_db_from_conn, reset_connection, save_thread
from shuati.cli.cli import cli


def _setup_memory_db():
    """Create in-memory DB for CLI tests."""
    reset_connection()
    conn = sqlite3.connect(":memory:")
    init_db_from_conn(conn)
    return conn


def _save_sample_thread(thread_id="TTEST01", subject="20260312小六打卡", date_str="2026-03-12 18:00:00"):
    blocks = [
        {"content_type": 11, "text": "1、计算面积", "image_url": None, "image_local": None},
    ]
    questions = [
        {"seq": 1, "content": "计算面积", "images_json": json.dumps([]), "answers_json": "[]"},
    ]
    save_thread(thread_id, subject, date_str, "老师", blocks, questions)


# ── Basic CLI tests ──

def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "shuati-agent" in result.output
    assert "login" in result.output
    assert "sync" in result.output
    assert "list" in result.output
    assert "generate" in result.output
    assert "server" in result.output


def test_cli_version():
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "version" in result.output.lower() or "1.0.0" in result.output


def test_all_commands_listed():
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    commands = ["login", "status", "sync", "sync-status", "list", "list-questions", "generate", "server", "show"]
    for cmd in commands:
        assert cmd in result.output, f"Command '{cmd}' not found in help output"


def test_server_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["server", "--help"])
    assert result.exit_code == 0
    assert "port" in result.output


# ── Status command ──

def test_status_yaml():
    _setup_memory_db()
    try:
        runner = CliRunner()
        result = runner.invoke(cli, ["status", "--yaml"])
        assert result.exit_code == 0
        data = yaml.safe_load(result.output)
        assert data["ok"] is True
        assert "logged_in" in data["data"]
    finally:
        reset_connection()


def test_status_json():
    _setup_memory_db()
    try:
        runner = CliRunner()
        result = runner.invoke(cli, ["status", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True
        assert data["schema_version"] == "1"
    finally:
        reset_connection()


# ── Sync-status command ──

def test_sync_status():
    _setup_memory_db()
    try:
        runner = CliRunner()
        result = runner.invoke(cli, ["sync-status", "--yaml"])
        assert result.exit_code == 0
        data = yaml.safe_load(result.output)
        assert data["ok"] is True
    finally:
        reset_connection()


# ── List command ──

def test_list_empty():
    _setup_memory_db()
    try:
        runner = CliRunner()
        result = runner.invoke(cli, ["list", "--yaml"])
        assert result.exit_code == 0
        data = yaml.safe_load(result.output)
        assert data["ok"] is True
        assert data["data"]["items"] == []
    finally:
        reset_connection()


def test_list_with_data():
    _setup_memory_db()
    _save_sample_thread()
    try:
        runner = CliRunner()
        result = runner.invoke(cli, ["list", "--yaml"])
        assert result.exit_code == 0
        data = yaml.safe_load(result.output)
        assert len(data["data"]["items"]) == 1
    finally:
        reset_connection()


def test_list_with_date_filter():
    _setup_memory_db()
    _save_sample_thread()
    try:
        runner = CliRunner()
        result = runner.invoke(cli, ["list", "--date", "2026-03-01", "--end", "2026-03-15", "--yaml"])
        assert result.exit_code == 0
        data = yaml.safe_load(result.output)
        assert data["ok"] is True
    finally:
        reset_connection()


# ── Show command ──

def test_show_existing():
    _setup_memory_db()
    _save_sample_thread()
    try:
        runner = CliRunner()
        result = runner.invoke(cli, ["show", "TTEST01", "--yaml"])
        assert result.exit_code == 0
        data = yaml.safe_load(result.output)
        assert data["ok"] is True
        assert "thread" in data["data"]
        assert "questions" in data["data"]
    finally:
        reset_connection()


def test_show_nonexistent():
    _setup_memory_db()
    try:
        runner = CliRunner()
        result = runner.invoke(cli, ["show", "NONEXISTENT_ID", "--yaml"])
        data = yaml.safe_load(result.output)
        assert data["ok"] is False
        assert "error" in data
    finally:
        reset_connection()


# ── List-questions command ──

def test_list_questions():
    _setup_memory_db()
    _save_sample_thread()
    try:
        runner = CliRunner()
        result = runner.invoke(cli, ["list-questions", "TTEST01", "--yaml"])
        assert result.exit_code == 0
        data = yaml.safe_load(result.output)
        assert data["ok"] is True
        assert "questions" in data["data"]
    finally:
        reset_connection()


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
