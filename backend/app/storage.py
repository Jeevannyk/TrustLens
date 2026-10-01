import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "trustlens.db"

# Added after the first release, so they are added to existing databases in init_db.
# Screenshots stay in screenshot/screenshot_mime (old rows and /screenshot keep working);
# file_bytes holds uploaded documents and videos. file_name/file_kind/file_mime describe any of them.
_FILE_COLUMNS = {"file_name": "TEXT", "file_mime": "TEXT", "file_kind": "TEXT", "file_bytes": "BLOB"}


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
        existing = {row["name"] for row in conn.execute("PRAGMA table_info(analyses)")}
        for column, declaration in _FILE_COLUMNS.items():
            if column not in existing:
                conn.execute(f"ALTER TABLE analyses ADD COLUMN {column} {declaration}")
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
    file_name: str | None = None,
    file_mime: str | None = None,
    file_kind: str | None = None,
    file_bytes: bytes | None = None,
) -> int:
    conn = _connect()
    try:
        cur = conn.execute(
            """
            INSERT INTO analyses
                (input_text, input_link, screenshot, screenshot_mime, language, risk_level, report_json,
                 file_name, file_mime, file_kind, file_bytes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                input_text, input_link, screenshot_bytes, screenshot_mime, language, risk_level, report_json,
                file_name, file_mime, file_kind, file_bytes,
            ),
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
                   screenshot IS NOT NULL AS has_screenshot,
                   (screenshot IS NOT NULL OR file_bytes IS NOT NULL) AS has_file,
                   file_name,
                   COALESCE(file_kind, CASE WHEN screenshot IS NOT NULL THEN 'image' END) AS file_kind
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
