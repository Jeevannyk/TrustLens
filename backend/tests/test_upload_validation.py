import pytest
from fastapi.testclient import TestClient

from app import gemini_client, main
from app.main import MAX_IMAGE_BYTES, resolve_image_mime


@pytest.mark.parametrize(
    "ctype,name,expected",
    [
        ("image/png", "a.png", "image/png"),
        ("image/jpg", "a.jpg", "image/jpeg"),
        ("image/webp; charset=x", "a", "image/webp"),
        ("", "photo.HEIC", "image/heic"),
        ("application/octet-stream", "photo.heif", "image/heif"),
        ("image/gif", "a.gif", None),
        ("application/pdf", "a.png", None),
        ("", "a.txt", None),
        (None, None, None),
    ],
)
def test_resolve_image_mime(ctype, name, expected):
    assert resolve_image_mime(ctype, name) == expected


@pytest.fixture
def client(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("secret internal detail")

    monkeypatch.setattr(gemini_client, "extract_message", boom)
    return TestClient(main.app)


def _post(client, content, ctype, name="x.png"):
    return client.post("/analyze", data={"text": "hi"}, files={"file": (name, content, ctype)})


def test_rejects_unsupported_type(client):
    r = _post(client, b"x", "image/gif", "x.gif")
    assert r.status_code == 415
    assert "Unsupported" in r.json()["detail"]


def test_rejects_oversize(client):
    r = _post(client, b"0" * (MAX_IMAGE_BYTES + 1), "image/png")
    assert r.status_code == 413
    assert "8 MB" in r.json()["detail"]


def test_valid_image_passes_validation_and_errors_are_generic(client):
    r = _post(client, b"0" * 10, "image/png")
    assert r.status_code == 500
    assert "secret" not in r.text
