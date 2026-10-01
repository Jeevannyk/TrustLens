import hashlib
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app import domain_checks, gemini_client, main, storage
from app.model_output import ModelReport
from app.schemas import ExtractedMessage

KEY_A = "a" * 64
KEY_B = "b" * 64
PNG = b"\x89PNG-bytes"


def _hash(key):
    return hashlib.sha256(key.encode()).hexdigest()


@pytest.fixture
def db(monkeypatch, tmp_path):
    monkeypatch.setattr(storage, "DB_PATH", tmp_path / "t.db")
    storage.init_db()
    return tmp_path / "t.db"


@pytest.fixture
def client(db, monkeypatch):
    async def run_checks(urls):
        return []

    monkeypatch.setattr(gemini_client, "extract_message", lambda *a: ExtractedMessage())
    monkeypatch.setattr(
        gemini_client, "synthesize_report", lambda *a, **k: ModelReport(risk_level="Safe", summary="Fine.")
    )
    monkeypatch.setattr(domain_checks, "run_domain_checks", run_checks)
    return TestClient(main.app)


def _as(key):
    return {"X-Owner": key}


def _analyze(client, key=KEY_A, **form):
    form.setdefault("text", "hello there")
    headers = _as(key) if key else {}
    return client.post("/analyze", data=form, files={"file": ("shot.png", PNG, "image/png")}, headers=headers)


def _rows(db):
    conn = sqlite3.connect(db)
    rows = conn.execute("SELECT id, owner FROM analyses ORDER BY id").fetchall()
    conn.close()
    return rows


ROUTES = [
    ("get", "/history"),
    ("get", "/history/1"),
    ("get", "/history/1/file"),
    ("get", "/history/1/screenshot"),
    ("delete", "/history/1"),
    ("delete", "/history"),
]
BAD_KEYS = [{}, {"X-Owner": ""}, {"X-Owner": "a" * 63}, {"X-Owner": "A" * 64}, {"X-Owner": "g" * 64}, {"X-Owner": "a" * 65}]


@pytest.mark.parametrize("method,path", ROUTES)
@pytest.mark.parametrize("headers", BAD_KEYS)
def test_missing_or_malformed_owner_key_is_401(client, db, method, path, headers):
    _analyze(client)
    r = getattr(client, method)(path, headers=headers)
    assert r.status_code == 401 and r.json() == {"detail": "owner key required"}
    assert len(_rows(db)) == 1  # nothing was deleted


@pytest.mark.parametrize("path", ["/history/1", "/history/1/file", "/history/1/screenshot"])
def test_another_owners_row_looks_exactly_like_a_missing_one(client, path):
    _analyze(client, KEY_A)
    assert client.get(path, headers=_as(KEY_A)).status_code == 200
    other = client.get(path, headers=_as(KEY_B))
    missing = client.get(path.replace("/1", "/999"), headers=_as(KEY_A))
    assert other.status_code == 404
    assert (other.status_code, other.content, other.headers["content-type"]) == (
        missing.status_code,
        missing.content,
        missing.headers["content-type"],
    )


def test_another_owner_cannot_delete_a_row_and_gets_the_missing_row_response(client, db):
    _analyze(client, KEY_A)
    other = client.delete("/history/1", headers=_as(KEY_B))
    missing = client.delete("/history/999", headers=_as(KEY_B))
    assert other.status_code == missing.status_code == 404 and other.content == missing.content
    assert len(_rows(db)) == 1


def test_list_shows_only_the_callers_rows(client):
    _analyze(client, KEY_A, text="mine 1")
    _analyze(client, KEY_B, text="theirs")
    _analyze(client, KEY_A, text="mine 2")
    mine = client.get("/history", headers=_as(KEY_A)).json()
    assert [r["input_text"] for r in mine] == ["mine 2", "mine 1"]
    assert [r["input_text"] for r in client.get("/history", headers=_as(KEY_B)).json()] == ["theirs"]
    assert client.get("/history", headers=_as("c" * 64)).json() == []


def test_the_database_stores_the_hash_not_the_secret(client, db):
    _analyze(client, KEY_A)
    assert _rows(db) == [(1, _hash(KEY_A))]
    assert KEY_A.encode() not in db.read_bytes()


@pytest.mark.parametrize("save", ["false", "False", " FALSE "])
def test_save_false_stores_nothing(client, db, save):
    r = _analyze(client, save=save)
    assert r.status_code == 200 and r.json()["risk_level"] == "Safe"
    assert _rows(db) == []


def test_save_true_and_the_default_store_the_row(client, db):
    _analyze(client, save="true")
    _analyze(client, text="another")
    assert len(_rows(db)) == 2


def test_no_owner_key_stores_nothing_but_still_answers(client, db):
    r = _analyze(client, key=None)
    assert r.status_code == 200 and r.json()["risk_level"] == "Safe"
    r = _analyze(client, key="not-a-key", text="again")
    assert r.status_code == 200
    assert _rows(db) == []


def test_a_cached_report_is_still_saved_for_each_requester(client, db):
    _analyze(client, KEY_A)
    second = _analyze(client, KEY_B)
    assert second.headers["x-cache"] == "HIT"
    assert _rows(db) == [(1, _hash(KEY_A)), (2, _hash(KEY_B))]


def test_delete_removes_the_row_and_a_repeat_is_404(client, db):
    _analyze(client)
    _analyze(client, text="keep me")
    assert client.delete("/history/1", headers=_as(KEY_A)).status_code == 204
    assert [r[0] for r in _rows(db)] == [2]
    assert client.delete("/history/1", headers=_as(KEY_A)).status_code == 404
    assert client.get("/history/1", headers=_as(KEY_A)).status_code == 404


def test_delete_all_removes_only_the_callers_rows(client, db):
    _analyze(client, KEY_A, text="1")
    _analyze(client, KEY_A, text="2")
    _analyze(client, KEY_B, text="3")
    r = client.delete("/history", headers=_as(KEY_A))
    assert r.status_code == 200 and r.json() == {"deleted": 2}
    assert _rows(db) == [(3, _hash(KEY_B))]
    assert client.delete("/history", headers=_as(KEY_A)).json() == {"deleted": 0}


def _insert(db, owner, created):
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO analyses (created_at, language, risk_level, report_json, owner) VALUES (?, 'en', 'Safe', '{}', ?)",
        (created, owner),
    )
    conn.commit()
    conn.close()


def test_purge_removes_old_owned_rows_and_keeps_legacy_and_fresh_ones(db):
    _insert(db, _hash(KEY_A), "2000-01-01 00:00:00")
    _insert(db, None, "2000-01-01 00:00:00")
    storage.save_analysis("fresh", None, None, None, "en", "Safe", "{}", owner=_hash(KEY_A))
    assert storage.purge_expired(7) == 1
    assert _rows(db) == [(2, None), (3, _hash(KEY_A))]


def test_purge_respects_the_retention_window(db):
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO analyses (created_at, language, risk_level, report_json, owner) "
        "VALUES (datetime('now', '-6 days'), 'en', 'Safe', '{}', 'x'), (datetime('now', '-8 days'), 'en', 'Safe', '{}', 'x')"
    )
    conn.commit()
    conn.close()
    assert storage.purge_expired(7) == 1
    assert [r[0] for r in _rows(db)] == [1]


def test_saving_purges_expired_rows_using_retention_days(client, db, monkeypatch):
    monkeypatch.setenv("RETENTION_DAYS", "3")
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO analyses (created_at, language, risk_level, report_json, owner) "
        "VALUES (datetime('now', '-4 days'), 'en', 'Safe', '{}', ?)",
        (_hash(KEY_B),),
    )
    conn.commit()
    conn.close()
    _analyze(client, KEY_A)
    assert _rows(db) == [(2, _hash(KEY_A))]


@pytest.mark.parametrize("value,expected", [(None, 7), ("30", 30), ("abc", 7), ("0", 1), ("-5", 1)])
def test_retention_days(monkeypatch, value, expected):
    monkeypatch.delenv("RETENTION_DAYS", raising=False)
    if value is not None:
        monkeypatch.setenv("RETENTION_DAYS", value)
    assert main.retention_days() == expected


def test_legacy_rows_are_kept_but_unreachable(client, db):
    _insert(db, None, "2000-01-01 00:00:00")
    assert client.get("/history", headers=_as(KEY_A)).json() == []
    assert client.get("/history/1", headers=_as(KEY_A)).status_code == 404
    assert client.delete("/history/1", headers=_as(KEY_A)).status_code == 404
    assert client.delete("/history", headers=_as(KEY_A)).json() == {"deleted": 0}
    assert len(_rows(db)) == 1


def test_migration_adds_owner_and_index_and_is_idempotent(monkeypatch, tmp_path):
    db = tmp_path / "old.db"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE analyses (id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL DEFAULT (datetime('now')), "
        "input_text TEXT, input_link TEXT, screenshot BLOB, screenshot_mime TEXT, language TEXT NOT NULL, "
        "risk_level TEXT NOT NULL, report_json TEXT NOT NULL)"
    )
    conn.execute("INSERT INTO analyses (input_text, language, risk_level, report_json) VALUES ('old', 'en', 'Safe', '{}')")
    conn.commit()
    conn.close()
    monkeypatch.setattr(storage, "DB_PATH", db)
    storage.init_db()
    storage.init_db()

    conn = sqlite3.connect(db)
    assert "owner" in {r[1] for r in conn.execute("PRAGMA table_info(analyses)")}
    assert "idx_analyses_owner" in {r[1] for r in conn.execute("PRAGMA index_list(analyses)")}
    assert conn.execute("SELECT owner FROM analyses").fetchall() == [(None,)]
    conn.close()
    new_id = storage.save_analysis("t", None, None, None, "en", "Safe", "{}", owner=_hash(KEY_A))
    assert storage.get_analysis(new_id, _hash(KEY_A))["owner"] == _hash(KEY_A)
    assert storage.get_analysis(new_id, _hash(KEY_B)) is None
    assert [r["id"] for r in storage.list_analyses(owner=_hash(KEY_A))] == [new_id]


def test_cors_preflight_allows_the_owner_header_and_delete(client):
    origin = "http://localhost:5173"
    for method, path in [("GET", "/history"), ("DELETE", "/history/1")]:
        r = client.options(
            path,
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": method,
                "Access-Control-Request-Headers": "x-owner",
            },
        )
        assert r.status_code == 200
        assert "x-owner" in r.headers["access-control-allow-headers"].lower()
        assert method in r.headers["access-control-allow-methods"]


def test_retry_after_is_exposed_to_browsers(client):
    r = client.get("/health", headers={"Origin": "http://localhost:5173"})
    assert "Retry-After" in r.headers["access-control-expose-headers"]
