import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "trustlens.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=5)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = _connect()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                input_text TEXT,
                input_link TEXT,
                screenshot BLOB,
                screenshot_mime TEXT,
                language TEXT NOT NULL,
                risk_level TEXT NOT NULL,
                report_json TEXT NOT NULL
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def save_analysis(
    input_text: str | None,
    input_link: str | None,
    screenshot_bytes: bytes | None,
    screenshot_mime: str | None,
    language: str,
    risk_level: str,
    report_json: str,
) -> int:
    conn = _connect()
    try:
        cur = conn.execute(
            """
            INSERT INTO analyses
                (input_text, input_link, screenshot, screenshot_mime, language, risk_level, report_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (input_text, input_link, screenshot_bytes, screenshot_mime, language, risk_level, report_json),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def list_analyses(limit: int = 50) -> list[dict]:
    conn = _connect()
    try:
        rows = conn.execute(
            """
            SELECT id, created_at, risk_level, input_text, input_link, language,
                   screenshot IS NOT NULL AS has_screenshot
            FROM analyses
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_analysis(analysis_id: int) -> dict | None:
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM analyses WHERE id = ?", (analysis_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()
