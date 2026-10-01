import hashlib
import re
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app import documents, domain_checks, gemini_client, main, storage
from app.main import MAX_FILE_BYTES, MAX_IMAGE_BYTES, resolve_file_kind
from app.model_output import ModelReport
from app.schemas import ExtractedMessage

PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF"
EML = (
    b"From: PayPal Support <service@paypa1.com>\r\n"
    b"To: me@example.com\r\n"
    b"Subject: Verify your account\r\n"
    b"Date: Mon, 1 Jan 2024 10:00:00 +0000\r\n"
    b"Content-Type: text/plain; charset=utf-8\r\n"
    b"\r\n"
    b"Please confirm at https://paypa1.com/verify\r\n"
)


@pytest.fixture
def api(monkeypatch, tmp_path):
    """TestClient with the model stubbed, a temp DB, and a record of what reached the model."""
    seen = {}

    def extract(text, data, mime):
        seen.update(text=text, data=data, mime=mime)
        sender = re.search(r"^From: (.*)$", text or "", re.M)  # stands in for the model reading the header
        return ExtractedMessage(sender=sender.group(1) if sender else None)

    async def run_checks(urls):
        seen["urls"] = urls
        return []

    monkeypatch.setattr(storage, "DB_PATH", tmp_path / "t.db")
    storage.init_db()
    monkeypatch.setattr(gemini_client, "extract_message", extract)
    monkeypatch.setattr(
        gemini_client,
        "synthesize_report",
        lambda *a, **k: ModelReport(risk_level="Safe", summary="Fine.", recommended_actions=["None."]),
    )
    monkeypatch.setattr(domain_checks, "run_domain_checks", run_checks)
    client = TestClient(main.app)
    client.headers["X-Owner"] = "a" * 64  # history is private to this key
    client.seen = seen
    return client


def _post(client, content, ctype, name, **data):
    return client.post("/analyze", data=data or {"text": "hi"}, files={"file": (name, content, ctype)})


@pytest.mark.parametrize(
    "ctype,name,expected",
    [
        ("image/png", "a.png", ("image", "image/png")),
        ("application/pdf", "a.pdf", ("document", "application/pdf")),
        ("", "a.PDF", ("document", "application/pdf")),
        ("application/octet-stream", "mail.eml", ("document", "message/rfc822")),
        ("message/rfc822", "mail.eml", ("document", "message/rfc822")),
        ("text/plain", "notes.txt", ("document", "text/plain")),
        ("text/plain", "mail.eml", ("document", "message/rfc822")),
        ("text/plain", "README.md", ("document", "text/markdown")),
        ("text/x-markdown", "README", ("document", "text/markdown")),
        ("application/x-msdownload", "a.exe", None),
        ("", "a.exe", None),
        ("application/zip", "a.pdf", None),
        (None, None, None),
    ],
)
def test_resolve_file_kind(ctype, name, expected):
    assert resolve_file_kind(ctype, name) == expected


def test_pdf_goes_to_model_inline_and_is_stored(api):
    r = _post(api, PDF, "application/pdf", "invoice.pdf")
    assert r.status_code == 200
    assert api.seen["data"] == PDF and api.seen["mime"] == "application/pdf"
    assert api.seen["text"] == "hi"
    row = storage.get_analysis(1)
    assert row["file_bytes"] == PDF and row["file_kind"] == "document" and row["file_name"] == "invoice.pdf"


def test_pdf_alone_is_enough(api):
    r = api.post("/analyze", files={"file": ("a.pdf", PDF, "application/pdf")})
    assert r.status_code == 200


def test_txt_is_merged_into_text_not_sent_as_binary(api):
    r = _post(api, b"Your parcel is held. Pay at hxxp://x.test", "text/plain", "n.txt", text="see this")
    assert r.status_code == 200
    assert api.seen["data"] is None
    assert api.seen["text"].startswith("see this\n\nAttached text file:\n")
    assert "Pay at hxxp://x.test" in api.seen["text"]


def test_eml_is_merged_and_sender_domain_is_checked(api):
    r = _post(api, EML, "message/rfc822", "m.eml")
    assert r.status_code == 200
    text = api.seen["text"]
    assert "service@paypa1.com" in text and "Subject: Verify your account" in text
    assert "https://paypa1.com/verify" in text
    assert "paypa1.com" in api.seen["urls"]
    assert api.seen["data"] is None


def test_eml_html_body_keeps_links_and_drops_attachments():
    eml = (
        b"From: a@b.test\r\nSubject: s\r\nMIME-Version: 1.0\r\n"
        b'Content-Type: multipart/mixed; boundary="X"\r\n\r\n'
        b"--X\r\nContent-Type: text/html; charset=utf-8\r\n\r\n"
        b'<style>p{color:red}</style><p>Hello <a href="https://evil.test/x">click</a></p>\r\n'
        b"--X\r\nContent-Type: application/octet-stream\r\nContent-Disposition: attachment; filename=a.bin\r\n\r\n"
        b"SECRET-ATTACHMENT\r\n--X--\r\n"
    )
    text = documents.prepare_document("message/rfc822", eml)
    assert "Hello" in text and "https://evil.test/x" in text
    assert "<p>" not in text and "color:red" not in text and "SECRET-ATTACHMENT" not in text


def test_long_document_is_truncated_not_rejected(api):
    r = _post(api, b"a" * 50_000, "text/plain", "big.txt", text="note")
    assert r.status_code == 200
    assert len(api.seen["text"]) == documents.MAX_TEXT_CHARS
    assert api.seen["text"].startswith("note\n\n")


@pytest.mark.parametrize("ctype,name", [("application/x-msdownload", "a.exe"), ("application/zip", "a.zip"), ("", "a.docx")])
def test_wrong_type_is_415_and_lists_allowed_types(api, ctype, name):
    r = _post(api, b"x", ctype, name)
    assert r.status_code == 415
    for kind in ("PNG", "PDF", "TXT", "EML", "MD"):
        assert kind in r.json()["detail"]


def test_fake_pdf_without_magic_is_rejected(api):
    r = _post(api, b"MZ\x90\x00 not a pdf", "application/pdf", "evil.pdf")
    assert r.status_code == 415 and "valid PDF" in r.json()["detail"]


@pytest.mark.parametrize("content", [b"\xff\xfe\x00\x01binary\x80", b"text\x00with nul", "caf\xe9".encode("latin-1")])
def test_binary_or_non_utf8_text_is_rejected(api, content):
    r = _post(api, content, "text/plain", "x.txt")
    assert r.status_code == 415 and "UTF-8" in r.json()["detail"]


def test_empty_text_file_is_rejected(api):
    r = _post(api, b"  \n ", "text/plain", "x.txt")
    assert r.status_code == 422


def test_oversize_document_is_413(api):
    r = _post(api, b"%PDF" + b"0" * MAX_FILE_BYTES, "application/pdf", "big.pdf")
    assert r.status_code == 413 and "10 MB" in r.json()["detail"]


def test_images_keep_the_8mb_limit(api):
    assert _post(api, b"0" * (MAX_IMAGE_BYTES + 1), "image/png", "a.png").status_code == 413


def test_failures_do_not_leak_exception_text(api, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("secret internal detail")

    monkeypatch.setattr(gemini_client, "extract_message", boom)
    r = _post(api, PDF, "application/pdf", "a.pdf")
    assert r.status_code == 500 and "secret" not in r.text


# --- file names -----------------------------------------------------------------------------

def test_safe_filename():
    assert documents.safe_filename("C:\\Users\\me\\..\\report.pdf") == "report.pdf"
    assert documents.safe_filename("../../etc/passwd") == "passwd"
    assert documents.safe_filename("a\x00b\r\nc\u202e.pdf") == "abc.pdf"
    assert len(documents.safe_filename("x" * 400 + ".pdf")) == 255
    assert documents.safe_filename("") is None and documents.safe_filename(None) is None


# --- history + storage ----------------------------------------------------------------------

def test_history_file_round_trip_for_pdf(api):
    _post(api, PDF, "application/pdf", "../inv oice.pdf")
    item = api.get("/history/1").json()
    assert item["has_file"] and item["file_kind"] == "document"
    assert item["file_name"] == "inv oice.pdf" and item["file_mime"] == "application/pdf"
    assert item["has_screenshot"] is False
    r = api.get("/history/1/file")
    assert r.status_code == 200 and r.content == PDF
    assert r.headers["content-type"] == "application/pdf"
    assert r.headers["content-disposition"].startswith('inline; filename="inv oice.pdf"')
    assert r.headers["x-content-type-options"] == "nosniff"
    assert api.get("/history/1/screenshot").status_code == 404
    [listed] = api.get("/history").json()
    assert listed["has_file"] and "file_bytes" not in listed


def test_history_file_is_attachment_for_text_and_header_is_safe(api):
    _post(api, b"hello", "text/plain", 'we"ird\u00e9\nname.txt')
    r = api.get("/history/1/file")
    assert r.content == b"hello"
    disposition = r.headers["content-disposition"]
    assert disposition.startswith("attachment;")
    assert "\n" not in disposition and 'we"ird' not in disposition


def test_screenshot_is_also_served_as_file_and_still_as_screenshot(api):
    _post(api, b"\x89PNG-bytes", "image/png", "shot.png")
    item = api.get("/history/1").json()
    assert item["has_screenshot"] and item["has_file"] and item["file_kind"] == "image"
    assert api.get("/history/1/screenshot").content == b"\x89PNG-bytes"
    r = api.get("/history/1/file")
    assert r.content == b"\x89PNG-bytes" and r.headers["content-disposition"].startswith("inline;")


def test_history_file_404_when_nothing_stored(api):
    api.post("/analyze", data={"text": "hello"})
    assert api.get("/history/1").json()["has_file"] is False
    assert api.get("/history/1/file").status_code == 404
    assert api.get("/history/999/file").status_code == 404


OLD_SCHEMA = """
CREATE TABLE analyses (
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


def _old_db(path):
    conn = sqlite3.connect(path)
    conn.execute(OLD_SCHEMA)
    conn.execute(
        "INSERT INTO analyses (input_text, screenshot, screenshot_mime, language, risk_level, report_json) "
        "VALUES ('old text', ?, 'image/png', 'en', 'Safe', '{\"x\": 1}')",
        (b"oldshot",),
    )
    conn.commit()
    conn.close()


def test_init_db_migrates_old_database_in_place(monkeypatch, tmp_path):
    db = tmp_path / "old.db"
    _old_db(db)
    monkeypatch.setattr(storage, "DB_PATH", db)
    storage.init_db()
    storage.init_db()  # idempotent

    conn = sqlite3.connect(db)
    columns = {r[1] for r in conn.execute("PRAGMA table_info(analyses)")}
    conn.close()
    assert {"file_name", "file_mime", "file_kind", "file_bytes"} <= columns

    row = storage.get_analysis(1)
    assert row["input_text"] == "old text" and row["screenshot"] == b"oldshot"
    assert row["file_name"] is None and row["file_bytes"] is None
    [listed] = storage.list_analyses()
    assert listed["has_screenshot"] and listed["has_file"] and listed["file_kind"] == "image"
    assert "screenshot" not in listed and "file_bytes" not in listed

    new_id = storage.save_analysis("t", None, None, None, "en", "Safe", "{}", "a.txt", "text/plain", "document", b"hi")
    assert storage.get_analysis(new_id)["file_bytes"] == b"hi"


def test_old_screenshot_row_is_served_through_old_and_new_endpoints(monkeypatch, tmp_path):
    db = tmp_path / "old.db"
    _old_db(db)
    monkeypatch.setattr(storage, "DB_PATH", db)
    storage.init_db()
    # Old rows have no owner and cannot be reached; give this one to the test's key, as if it had been saved by it.
    conn = sqlite3.connect(db)
    conn.execute("UPDATE analyses SET owner = ?", (hashlib.sha256(("a" * 64).encode()).hexdigest(),))
    conn.commit()
    conn.close()
    client = TestClient(main.app)
    client.headers["X-Owner"] = "a" * 64
    item = client.get("/history/1").json()
    assert item["has_screenshot"] and item["has_file"] and item["file_kind"] == "image"
    assert client.get("/history/1/screenshot").content == b"oldshot"
    assert client.get("/history/1/file").content == b"oldshot"
