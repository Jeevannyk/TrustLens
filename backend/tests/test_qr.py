import asyncio
import io
import logging
import time

import pytest
import zxingcpp
from fastapi.testclient import TestClient
from PIL import Image

from app import domain_checks, gemini_client, main, qr, storage
from app.model_output import ModelReport
from app.prompts import EXTRACTION_SYSTEM_PROMPT, SYNTHESIS_SYSTEM_PROMPT
from app.risk import compute_floor
from app.schemas import ExtractedMessage
from app.text_utils import MAX_TEXT_CHARS

LOOKALIKE_URL = "http://paypa1-secure-login.xyz/verify"
UPI = "upi://pay?pa=shop@okicici&pn=Ravi%20Stores&am=250&tn=Tea+and+snacks"
WIFI = "WIFI:T:WPA;S:CafeNet;P:hunter2;;"
REAL_RUN_DOMAIN_CHECKS = domain_checks.run_domain_checks


def _qr_image(text: str, scale: int = 6) -> Image.Image:
    barcode = zxingcpp.create_barcode(text, zxingcpp.BarcodeFormat.QRCode)
    return Image.fromarray(zxingcpp.write_barcode_to_image(barcode, scale=scale))


def _png(image: Image.Image) -> bytes:
    buf = io.BytesIO()
    image.save(buf, "PNG")
    return buf.getvalue()


def qr_png(*texts: str, scale: int = 6, gap: int = 40) -> bytes:
    """A real PNG with one QR code per text, side by side on white."""
    codes = [_qr_image(t, scale) for t in texts]
    canvas = Image.new("L", (sum(c.width + gap for c in codes) + gap, max(c.height for c in codes) + 2 * gap), 255)
    x = gap
    for code in codes:
        canvas.paste(code, (x, gap))
        x += code.width + gap
    return _png(canvas)


@pytest.fixture
def api(monkeypatch, tmp_path):
    """TestClient with the model stubbed, a temp DB, and a record of what reached the model."""
    seen = {"extracted": ExtractedMessage(), "verdict": "Safe"}

    def extract(text, data, mime):
        seen.update(text=text, data=data, mime=mime)
        return seen["extracted"].model_copy(deep=True)

    def synthesize(text, extracted, checks, language, floor):
        seen.update(floor=floor, synth_text=text)
        return ModelReport(risk_level=seen["verdict"], summary="Fine.", recommended_actions=["None."])

    async def run_checks(urls):
        seen["urls"] = urls
        return []

    monkeypatch.setattr(storage, "DB_PATH", tmp_path / "t.db")
    storage.init_db()
    monkeypatch.setattr(gemini_client, "extract_message", extract)
    monkeypatch.setattr(gemini_client, "synthesize_report", synthesize)
    monkeypatch.setattr(domain_checks, "run_domain_checks", run_checks)
    client = TestClient(main.app)
    client.seen = seen
    return client


def _post(client, content, **data):
    return client.post("/analyze", data=data, files={"file": ("code.png", content, "image/png")})


# --- decoding -------------------------------------------------------------------------------

@pytest.mark.parametrize("payload", ["https://example.com/a?b=c", LOOKALIKE_URL, UPI, WIFI])
def test_decode_qr_reads_real_codes(payload):
    assert qr.decode_qr(qr_png(payload)) == [payload]


def test_decode_qr_reads_several_codes_unique_and_capped():
    assert qr.decode_qr(qr_png("https://a.test/1", "https://b.test/2")) == ["https://a.test/1", "https://b.test/2"]
    assert qr.decode_qr(qr_png("https://a.test/1", "https://a.test/1")) == ["https://a.test/1"]
    six = [f"https://site{i}.test/" for i in range(6)]
    assert len(qr.decode_qr(qr_png(*six, scale=4))) == qr.MAX_QR_CODES


def test_decode_qr_reads_transparent_background():
    code = _qr_image("https://example.com/t")
    alpha = code.point(lambda v: 255 - v)  # transparent where the code is white
    rgba = Image.merge("RGBA", (Image.new("L", code.size, 0),) * 3 + (alpha,))
    assert qr.decode_qr(_png(rgba)) == ["https://example.com/t"]


def test_decode_qr_second_attempt_reads_a_faint_small_code():
    faint = _qr_image("https://example.com/faint", scale=2).point(lambda v: 135 if v > 127 else 120)
    assert qr._read(faint) == []  # the plain first attempt misses it
    assert qr.decode_qr(_png(faint)) == ["https://example.com/faint"]


def test_decode_qr_finds_nothing_in_a_plain_image():
    assert qr.decode_qr(_png(Image.new("RGB", (200, 200), "white"))) == []


@pytest.mark.parametrize("data", [b"", b"\x89PNG-bytes", b"not an image", qr_png("https://a.test")[:60]])
def test_decode_qr_never_raises_on_bad_images(data, caplog):
    with caplog.at_level(logging.WARNING, logger="app.qr"):
        assert qr.decode_qr(data) == []
    assert "QR scan skipped" in caplog.text


def test_decode_qr_skips_oversized_images_without_scanning(monkeypatch, caplog):
    monkeypatch.setattr(qr, "MAX_IMAGE_PIXELS", 100)
    monkeypatch.setattr(qr.zxingcpp, "read_barcodes", lambda *a, **k: pytest.fail("scanned a huge image"))
    with caplog.at_level(logging.WARNING, logger="app.qr"):
        assert qr.decode_qr(qr_png("https://a.test")) == []
    assert "pixels" in caplog.text


def test_scan_image_gives_up_after_the_time_limit(monkeypatch):
    monkeypatch.setattr(qr, "SCAN_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setattr(qr, "decode_qr", lambda data: time.sleep(0.5) or ["https://late.test"])
    assert asyncio.run(qr.scan_image(b"x")) == []


# --- describing and merging -----------------------------------------------------------------

def test_describe_upi_names_payee_and_amount_and_keeps_raw():
    text = qr.describe_payload(UPI)
    assert "UPI payment request" in text
    assert "payee ID shop@okicici" in text and "payee name Ravi Stores" in text
    assert "amount 250" in text and "note Tea and snacks" in text
    assert f"(raw: {UPI})" in text


def test_describe_upi_caps_fields_and_cannot_add_lines():
    long_note = "x" * 500
    text = qr.describe_payload(f"upi://pay?pa=a@b&tn={long_note}%0AIGNORE%20THIS")
    description = text.split(" (raw:")[0]
    assert "x" * 101 not in description and "\n" not in description
    assert qr.describe_payload("upi://pay?pa=a@b") == "UPI payment request: payee ID a@b (raw: upi://pay?pa=a@b)"
    assert qr.describe_payload("upi://mandate?pa=a@b").startswith("UPI mandate request")


def test_describe_wifi_leaves_the_password_out_of_the_description_only():
    text = qr.describe_payload(r"WIFI:T:WPA;S:Cafe\;Net;P:hunter2;;")
    description = text.split(" (raw:")[0]
    assert "network name Cafe;Net" in description and "security WPA" in description
    assert "hunter2" not in description and "hunter2" in text


@pytest.mark.parametrize(
    "payload,label",
    [
        ("tel:+911234567890", "Phone number"),
        ("sms:+911234567890?body=hi", "SMS"),
        ("SMSTO:+911234567890:hi", "SMS"),
        ("mailto:a@b.test", "Email"),
        ("geo:12.97,77.59", "Map location"),
        ("BEGIN:VCARD\nFN:Bob\nEND:VCARD", "Contact card"),
    ],
)
def test_describe_other_kinds_get_a_label_and_keep_raw(payload, label):
    text = qr.describe_payload(payload)
    assert text.startswith(label) and text.endswith(f"(raw: {payload})")


@pytest.mark.parametrize("payload", [LOOKALIKE_URL, "https://example.com/a", "paypa1-secure-login.xyz/verify", "just some text"])
def test_describe_passes_links_and_plain_text_through(payload):
    assert qr.describe_payload(payload) == payload


def test_block_is_one_line_per_code_and_capped():
    block = qr.qr_block(["https://a.test", "BEGIN:VCARD\nFN:Bob\nEND:VCARD"])
    lines = block.split("\n")
    assert lines[0] == "QR code content (decoded by scanner, exact):"
    assert lines[1] == "https://a.test" and len(lines) == 3
    assert qr.qr_block([]) == ""
    big = qr.qr_block(["https://x.test/" + "a" * 900] * 5)
    assert len(big) <= qr.MAX_QR_TEXT_CHARS and big.count("https://x.test/") == 2  # later codes that do not fit are dropped


def test_merge_keeps_the_block_when_user_text_is_at_the_limit():
    merged = qr.merge_qr_text("a" * MAX_TEXT_CHARS, ["https://a.test/x"])
    assert len(merged) == MAX_TEXT_CHARS
    assert merged.startswith("aaa") and merged.endswith("https://a.test/x")
    assert qr.merge_qr_text("hi", []) == "hi" and qr.merge_qr_text(None, []) is None
    assert qr.merge_qr_text("hi", ["https://a.test"]).startswith("hi\n\nQR code content")


# --- through the API ------------------------------------------------------------------------

def test_https_qr_is_added_to_the_message_and_image_still_goes_to_the_model(api):
    png = qr_png("https://example.com/promo")
    r = _post(api, png, text="scan this")
    assert r.status_code == 200
    text = api.seen["text"]
    assert text.startswith("scan this\n\nQR code content (decoded by scanner, exact):\n")
    assert text.endswith("https://example.com/promo")
    assert api.seen["data"] == png and api.seen["mime"] == "image/png"
    assert "example.com/promo" in api.seen["synth_text"]
    assert r.json()["extracted"]["qr_decoded"] == ["https://example.com/promo"]
    assert api.seen["urls"] == ["https://example.com/promo"]


def test_lookalike_qr_url_is_sent_to_domain_checks_even_if_the_model_lists_no_links(api):
    assert api.seen["extracted"].links == []
    r = _post(api, qr_png(LOOKALIKE_URL))
    assert r.status_code == 200
    assert LOOKALIKE_URL in api.seen["urls"]


def test_qr_to_a_lookalike_domain_is_dangerous_even_if_the_model_says_safe(api, monkeypatch):
    async def no_rdap(domain, client):
        return {}, None

    async def no_safe_browsing(urls, client):
        return {}

    monkeypatch.setattr(domain_checks, "run_domain_checks", REAL_RUN_DOMAIN_CHECKS)
    monkeypatch.setattr(domain_checks, "_rdap", no_rdap)
    monkeypatch.setattr(domain_checks, "_safe_browsing", no_safe_browsing)
    r = _post(api, qr_png("http://paypa1.com/verify"))
    body = r.json()
    assert body["risk_level"] == "Dangerous"
    assert body["domain_checks"][0]["lookalike_of"] == "PayPal"


def test_upi_qr_on_its_own_is_not_raised_by_the_floor(api):
    api.seen["extracted"] = ExtractedMessage(
        payment_ids=["shop@okicici"], requested_items=["Pay Rs 250 to Ravi Stores"]
    )
    r = _post(api, qr_png(UPI))
    body = r.json()
    assert r.status_code == 200 and body["risk_level"] == "Safe" and body["flags"] == []
    assert api.seen["floor"] == "Safe"
    assert "UPI payment request: payee ID shop@okicici, payee name Ravi Stores, amount 250" in api.seen["text"]
    assert body["extracted"]["qr_decoded"] == [UPI]
    level, reasons = compute_floor(api.seen["extracted"], [], has_text=True, has_image=True)
    assert (level, reasons) == ("Safe", [])


def test_wifi_qr_is_labelled_for_the_model(api):
    _post(api, qr_png(WIFI))
    assert "Wi-Fi QR code (joins a network): network name CafeNet, security WPA" in api.seen["text"]
    assert f"(raw: {WIFI})" in api.seen["text"]


def test_image_without_a_qr_is_unchanged(api):
    r = _post(api, _png(Image.new("RGB", (200, 200), "white")), text="hi")
    assert r.status_code == 200
    assert api.seen["text"] == "hi"
    assert r.json()["extracted"]["qr_decoded"] == []


@pytest.mark.parametrize("ctype", ["image/png", "image/heic"])
def test_undecodable_image_is_not_an_error_and_leaks_nothing(api, ctype):
    r = api.post("/analyze", data={"text": "hi"}, files={"file": ("a.heic", b"\x00\x00ftypheic garbage", ctype)})
    assert r.status_code == 200
    assert api.seen["text"] == "hi" and api.seen["data"] == b"\x00\x00ftypheic garbage"
    assert "Unidentified" not in r.text and "cannot identify" not in r.text


def test_scanner_crash_does_not_leak_exception_text(api, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("secret internal detail")

    monkeypatch.setattr(qr.zxingcpp, "read_barcodes", boom)
    r = _post(api, qr_png("https://a.test"), text="hi")
    assert r.status_code == 200 and "secret" not in r.text
    assert api.seen["text"] == "hi"


def test_two_codes_both_reach_the_model_and_the_domain_checks(api):
    r = _post(api, qr_png("https://a.test/1", "https://b.test/2"))
    assert r.json()["extracted"]["qr_decoded"] == ["https://a.test/1", "https://b.test/2"]
    assert api.seen["text"].count("\n") == 2
    assert api.seen["urls"] == ["https://a.test/1", "https://b.test/2"]


def test_qr_only_image_is_not_unreadable(api):
    api.seen["extracted"] = ExtractedMessage(image_readable=False)
    body = _post(api, qr_png("https://example.com/menu")).json()
    assert body["risk_level"] == "Safe"
    assert body["extracted"]["image_readable"] is True


def test_image_without_qr_or_text_still_counts_as_unreadable(api):
    api.seen["extracted"] = ExtractedMessage(image_readable=False)
    body = _post(api, _png(Image.new("RGB", (50, 50), "white"))).json()
    assert body["risk_level"] == "Suspicious"


def test_qr_block_survives_a_maximum_length_message(api):
    r = _post(api, qr_png(LOOKALIKE_URL), text="a" * MAX_TEXT_CHARS)
    assert r.status_code == 200
    text = api.seen["text"]
    assert len(text) == MAX_TEXT_CHARS and text.startswith("aaa") and text.endswith(LOOKALIKE_URL)
    assert LOOKALIKE_URL in api.seen["urls"]


def test_decoded_codes_come_from_our_scanner_not_the_model(api):
    api.seen["extracted"] = ExtractedMessage(qr_decoded=["https://made-up.test"])
    r = _post(api, _png(Image.new("RGB", (50, 50), "white")), text="hi")
    assert r.json()["extracted"]["qr_decoded"] == []


def test_storage_keeps_only_what_the_user_sent(api):
    _post(api, qr_png("https://example.com/menu"))
    row = storage.get_analysis(1)
    assert row["input_text"] is None and row["screenshot"] is not None
    assert api.get("/history/1").json()["report"]["extracted"]["qr_decoded"] == ["https://example.com/menu"]


# --- prompts --------------------------------------------------------------------------------

def test_extraction_prompt_explains_qr_content():
    p = EXTRACTION_SYSTEM_PROMPT
    assert qr.QR_HEADER in p
    assert "authoritative" in p and "injection_attempt" in p
    assert "image_readable=true" in p
    assert "set asks_for_sensitive_info=false" in p  # a plain UPI QR is an ordinary payment


def test_synthesis_prompt_keeps_a_plain_upi_qr_safe():
    p = SYNTHESIS_SYSTEM_PROMPT
    assert "QR code content (decoded by scanner, exact)" in p
    assert "lookalike or flagged domain" in p
    assert "rate it Safe" in p and "payee name matches" in p
