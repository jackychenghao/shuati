import sqlite3
import os
from datetime import datetime
from shuati.core.config import DB_PATH, DATA_DIR

# 单线程共享连接，整个进程只有一个连接
_db_conn = None

def _get_conn():
    """Get or create the shared connection (single-threaded)."""
    global _db_conn
    if _db_conn is None:
        os.makedirs(DATA_DIR, exist_ok=True)
        _db_conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _db_conn.row_factory = sqlite3.Row
    return _db_conn


def get_conn():
    """Public alias for _get_conn() (used by app.py)."""
    return _get_conn()


def reset_connection():
    """Close and reset the shared connection (for test isolation)."""
    global _db_conn
    if _db_conn is not None:
        try:
            _db_conn.close()
        except Exception:
            pass
    _db_conn = None


def init_db_from_conn(conn):
    """Initialize tables on an externally-provided connection (e.g. :memory: for tests)."""
    global _db_conn
    _db_conn = conn
    _db_conn.row_factory = sqlite3.Row
    _init_tables(_db_conn)


def init_db():
    conn = _get_conn()
    _init_tables(conn)
    print("[DB] 初始化完成")


def _init_tables(conn):
    """Create all tables (shared by init_db and init_db_from_conn)."""
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS threads (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            thread_id   TEXT UNIQUE NOT NULL,
            subject     TEXT NOT NULL,
            date_str    TEXT NOT NULL,
            author      TEXT,
            synced_at   TEXT NOT NULL
        )
    """)

    try:
        c.execute("ALTER TABLE threads ADD COLUMN type TEXT DEFAULT '接龙管家打卡接龙'")
    except sqlite3.OperationalError:
        pass

    c.execute("""
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            thread_id TEXT NOT NULL,
            seq INTEGER NOT NULL,
            content TEXT,
            images TEXT,
            answers TEXT,
            FOREIGN KEY (thread_id) REFERENCES threads(thread_id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS blocks (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            thread_id   TEXT NOT NULL,
            block_order INTEGER NOT NULL,
            content_type INTEGER NOT NULL,
            text        TEXT,
            image_url   TEXT,
            image_local TEXT,
            FOREIGN KEY (thread_id) REFERENCES threads(thread_id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS sync_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            synced_at   TEXT NOT NULL,
            new_count   INTEGER DEFAULT 0,
            status      TEXT,
            message     TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    conn.commit()


def thread_exists(thread_id: str) -> bool:
    conn = _get_conn()
    row = conn.execute(
        "SELECT 1 FROM threads WHERE thread_id = ?", (thread_id,)
    ).fetchone()
    return row is not None


def thread_date_exists(date_str: str) -> bool:
    return False


def thread_subject_date_exists(subject: str, date_str: str) -> bool:
    conn = _get_conn()
    row = conn.execute(
        "SELECT 1 FROM threads WHERE subject = ? AND substr(date_str, 1, 10) = substr(?, 1, 10)",
        (subject, date_str)
    ).fetchone()
    return row is not None


def save_thread(thread_id: str, subject: str, date_str: str, author: str, blocks: list, questions: list = None):
    conn = _get_conn()
    conn.execute("""
        INSERT OR IGNORE INTO threads (thread_id, subject, date_str, author, type, synced_at)
        VALUES (?, ?, ?, ?, '接龙管家打卡接龙', ?)
    """, (thread_id, subject, date_str, author, datetime.now().isoformat()))

    for i, block in enumerate(blocks):
        conn.execute("""
            INSERT INTO blocks (thread_id, block_order, content_type, text, image_url, image_local)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            thread_id,
            i,
            block.get("content_type"),
            block.get("text"),
            block.get("image_url"),
            block.get("image_local"),
        ))

    if questions:
        for q in questions:
            conn.execute("""
                INSERT INTO questions (thread_id, seq, content, images, answers)
                VALUES (?, ?, ?, ?, ?)
            """, (thread_id, q.get("seq", 1), q.get("content", ""), q.get("images_json", "[]"), q.get("answers_json", "[]")))

    conn.commit()


def update_image_local(thread_id: str, image_url: str, local_path: str):
    conn = _get_conn()
    conn.execute("""
        UPDATE blocks SET image_local = ?
        WHERE thread_id = ? AND image_url = ?
    """, (local_path, thread_id, image_url))
    conn.commit()


def log_sync(new_count: int, status: str, message: str = ""):
    conn = _get_conn()
    conn.execute("""
        INSERT INTO sync_log (synced_at, new_count, status, message)
        VALUES (?, ?, ?, ?)
    """, (datetime.now().isoformat(), new_count, status, message))
    conn.commit()


def get_all_threads(limit: int = 100):
    conn = _get_conn()
    rows = conn.execute("""
        SELECT * FROM threads ORDER BY date_str DESC LIMIT ?
    """, (limit,)).fetchall()
    return [dict(r) for r in rows]


def get_threads_by_date_range(start: str, end: str):
    conn = _get_conn()
    rows = conn.execute("""
        SELECT * FROM threads
        WHERE substr(date_str, 1, 10) BETWEEN ? AND ?
        ORDER BY date_str ASC
    """, (start, end)).fetchall()
    return [dict(r) for r in rows]


def get_threads_page(start: str = "", end: str = "", page: int = 1, page_size: int = 15):
    page = max(1, int(page))
    page_size = max(1, int(page_size))
    offset = (page - 1) * page_size
    conn = _get_conn()
    if start and end:
        total_row = conn.execute("""
            SELECT COUNT(*) AS cnt FROM threads
            WHERE substr(date_str, 1, 10) BETWEEN ? AND ?
        """, (start, end)).fetchone()
        rows = conn.execute("""
            SELECT * FROM threads
            WHERE substr(date_str, 1, 10) BETWEEN ? AND ?
            ORDER BY date_str DESC, id DESC
            LIMIT ? OFFSET ?
        """, (start, end, page_size, offset)).fetchall()
    else:
        total_row = conn.execute("SELECT COUNT(*) AS cnt FROM threads").fetchone()
        rows = conn.execute("""
            SELECT * FROM threads
            ORDER BY date_str DESC, id DESC
            LIMIT ? OFFSET ?
        """, (page_size, offset)).fetchall()
    total = total_row["cnt"] if total_row else 0
    return {
        "items": [dict(r) for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size
    }


def get_threads_by_ids(thread_ids: list[str]):
    if not thread_ids:
        return []
    conn = _get_conn()
    placeholders = ",".join(["?"] * len(thread_ids))
    rows = conn.execute(
        f"SELECT * FROM threads WHERE thread_id IN ({placeholders}) ORDER BY date_str ASC",
        tuple(thread_ids)
    ).fetchall()
    return [dict(r) for r in rows]


def get_blocks_by_thread(thread_id: str):
    conn = _get_conn()
    rows = conn.execute("""
        SELECT * FROM blocks WHERE thread_id = ? ORDER BY block_order ASC
    """, (thread_id,)).fetchall()
    return [dict(r) for r in rows]


def get_questions_by_thread(thread_id: str):
    conn = _get_conn()
    rows = conn.execute("""
        SELECT * FROM questions WHERE thread_id = ? ORDER BY seq ASC
    """, (thread_id,)).fetchall()
    return [dict(r) for r in rows]


def get_last_sync():
    conn = _get_conn()
    row = conn.execute("""
        SELECT * FROM sync_log ORDER BY id DESC LIMIT 1
    """).fetchone()
    return dict(row) if row else None


def delete_thread(thread_id: str):
    conn = _get_conn()
    conn.execute("DELETE FROM questions WHERE thread_id = ?", (thread_id,))
    conn.execute("DELETE FROM blocks WHERE thread_id = ?", (thread_id,))
    conn.execute("DELETE FROM threads WHERE thread_id = ?", (thread_id,))
    conn.commit()


def clear_all_threads():
    conn = _get_conn()
    conn.execute("DELETE FROM questions")
    conn.execute("DELETE FROM blocks")
    conn.execute("DELETE FROM threads")
    conn.execute("DELETE FROM sync_log")
    conn.execute("UPDATE sqlite_sequence SET seq = 0 WHERE name = 'threads'")
    conn.execute("UPDATE sqlite_sequence SET seq = 0 WHERE name = 'blocks'")
    conn.execute("UPDATE sqlite_sequence SET seq = 0 WHERE name = 'questions'")
    conn.execute("UPDATE sqlite_sequence SET seq = 0 WHERE name = 'sync_log'")
    conn.commit()
    print("[DB] 已清空所有数据")


def get_thread_count():
    conn = _get_conn()
    row = conn.execute("SELECT COUNT(*) as cnt FROM threads").fetchone()
    return row["cnt"]


def get_setting(key: str, default: str | None = None) -> str | None:
    conn = _get_conn()
    row = conn.execute("SELECT value FROM app_settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(key: str, value: str):
    conn = _get_conn()
    conn.execute("""
        INSERT INTO app_settings (key, value) VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
    """, (key, value))
    conn.commit()


def get_bool_setting(key: str, default: bool = False) -> bool:
    v = get_setting(key)
    if v is None:
        return default
    return str(v).strip().lower() in {"1", "true", "yes", "on"}


def set_bool_setting(key: str, value: bool):
    set_setting(key, "1" if value else "0")
