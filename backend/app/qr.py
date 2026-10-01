"""Reads QR codes from an uploaded image and turns what they contain into text for the
analysis. decode_qr and describe_payload are pure (no network); scan_image is the async
wrapper the API uses."""
import asyncio
import io
import logging
import math
import re
from urllib.parse import parse_qsl, urlsplit

import zxingcpp
from PIL import Image, ImageOps

from .text_utils import MAX_TEXT_CHARS, normalize_text

logger = logging.getLogger(__name__)

MAX_QR_CODES = 5
MAX_PAYLOAD_CHARS = 1_000
MAX_QR_TEXT_CHARS = 2_000
MAX_FIELD_CHARS = 100
# Pixels, not bytes: a tiny PNG can still expand to a huge bitmap. Checked from the file
# header, before anything is decoded.
MAX_IMAGE_PIXELS = 50_000_000
SCAN_TIMEOUT_SECONDS = 10.0
_SMALL_IMAGE_SIDE = 1_000  # images smaller than this are upscaled for the second attempt

QR_HEADER = "QR code content (decoded by scanner, exact):"

_WIFI_FIELD = re.compile(r"(?:^|;)([A-Za-z]):((?:\\.|[^;\\])*)")  # KEY:value, backslash escapes a ;
_WIFI_ESCAPE = re.compile(r"\\(.)")

_LABELS = (
    ("tel:", "Phone number QR code (starts a call)"),
    ("smsto:", "SMS QR code (prepares a text message)"),
    ("sms:", "SMS QR code (prepares a text message)"),
    ("mailto:", "Email QR code (prepares an email)"),
    ("geo:", "Map location QR code"),
    ("begin:vcard", "Contact card QR code"),
)


def _read(image: Image.Image) -> list[str]:
    barcodes = zxingcpp.read_barcodes(
        image, formats=zxingcpp.BarcodeFormat.QRCode, text_mode=zxingcpp.TextMode.Plain
    )
    return [b.text for b in barcodes]


def _flatten(image: Image.Image) -> Image.Image:
    """Transparency onto white: a transparent background would otherwise read as black."""
    if image.mode in ("RGBA", "LA", "PA") or "transparency" in image.info:
        rgba = image.convert("RGBA")
        return Image.alpha_composite(Image.new("RGBA", rgba.size, "white"), rgba)
    return image


def decode_qr(image_bytes: bytes) -> list[str]:
    """Up to 5 unique QR code texts found in the image, [] when there is none. Never raises:
    an image we cannot open or scan (HEIC without a decoder, corrupt, too large) just has
    no QR text."""
    try:
        with Image.open(io.BytesIO(image_bytes)) as image:
            if image.width * image.height > MAX_IMAGE_PIXELS:
                logger.warning("QR scan skipped: image is %dx%d pixels", image.width, image.height)
                return []
            image.load()  # a truncated or corrupt file fails here, cleanly
            image = _flatten(image)
            found = _read(image)
            if not found:
                # Second attempt for faint or small codes: grayscale, stretched contrast, upscaled.
                gray = ImageOps.autocontrast(image.convert("L"))
                scale = math.ceil(_SMALL_IMAGE_SIDE / max(gray.size))
                if scale > 1:
                    gray = gray.resize((gray.width * scale, gray.height * scale), Image.Resampling.LANCZOS)
                found = _read(gray)
    except Exception as exc:  # untrusted bytes: any decoder failure means "no QR text"
        logger.warning("QR scan skipped: %s: %s", type(exc).__name__, exc)
        return []
    texts = (normalize_text(text)[:MAX_PAYLOAD_CHARS] for text in found)
    return list(dict.fromkeys(t for t in texts if t))[:MAX_QR_CODES]


async def scan_image(image_bytes: bytes) -> list[str]:
    """decode_qr off the event loop, with a time limit (a timeout also means no QR text)."""
    try:
        return await asyncio.wait_for(asyncio.to_thread(decode_qr, image_bytes), SCAN_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        logger.warning("QR scan skipped: timed out after %.0fs", SCAN_TIMEOUT_SECONDS)
        return []


def _field(value: str) -> str:
    return " ".join(value.split())[:MAX_FIELD_CHARS]


def _upi(payload: str) -> str:
    parts = urlsplit(payload)
    fields: dict[str, str] = {}
    for key, value in parse_qsl(parts.query):
        fields.setdefault(key.lower(), value)
    action = parts.netloc.lower()
    label = "UPI payment request" if action == "pay" else f"UPI {_field(action)} request"
    names = (("pa", "payee ID"), ("pn", "payee name"), ("am", "amount"), ("tn", "note"))
    details = [f"{name} {_field(fields[key])}" for key, name in names if fields.get(key)]
    return f"{label}: {', '.join(details)}" if details else label


def _wifi(payload: str) -> str:
    # WIFI:T:WPA;S:name;P:password;; The password is left out of the description (it is
    # still in the raw text).
    fields = {key: _WIFI_ESCAPE.sub(r"\1", value) for key, value in _WIFI_FIELD.findall(payload[5:])}
    names = (("S", "network name"), ("T", "security"))
    details = [f"{name} {_field(fields[key])}" for key, name in names if fields.get(key)]
    label = "Wi-Fi QR code (joins a network)"
    return f"{label}: {', '.join(details)}" if details else label


def describe_payload(payload: str) -> str:
    """Plain-language label for a QR text that is not a web link, followed by the raw text
    (exact characters matter for IDs and addresses). Web links, bare domains and plain text
    come back unchanged so the URL extraction sees them as written."""
    lowered = payload.lower()
    if lowered.startswith("upi:"):
        description = _upi(payload)
    elif lowered.startswith("wifi:"):
        description = _wifi(payload)
    else:
        description = next((label for prefix, label in _LABELS if lowered.startswith(prefix)), None)
    return f"{description} (raw: {payload})" if description else payload


def qr_block(payloads: list[str]) -> str:
    """The text handed to the model for decoded QR codes ("" when there are none): one line
    per code, at most MAX_QR_TEXT_CHARS. Codes that do not fit are left out."""
    if not payloads:
        return ""
    block = QR_HEADER
    for payload in payloads:
        line = " ".join(describe_payload(payload).split())
        if block != QR_HEADER and len(block) + 1 + len(line) > MAX_QR_TEXT_CHARS:
            break
        block += "\n" + line
    return block[:MAX_QR_TEXT_CHARS]


def merge_qr_text(user_text: str | None, payloads: list[str]) -> str | None:
    """User text first, then the QR block. The block always fits: the user's text is what
    gets cut to make room."""
    block = qr_block(payloads)
    if not block:
        return user_text
    if not user_text:
        return block
    return f"{user_text[: MAX_TEXT_CHARS - len(block) - 2]}\n\n{block}"
