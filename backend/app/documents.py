"""Turns an uploaded document into text for the analysis, and cleans file names. No I/O."""
import re
import unicodedata
from email import policy
from email.parser import BytesParser
from html.parser import HTMLParser

from .text_utils import MAX_TEXT_CHARS, InputError, normalize_text

PDF_MIME = "application/pdf"
EML_MIME = "message/rfc822"
MAX_FILENAME_CHARS = 255

_LABELS = {
    "text/plain": "Attached text file",
    "text/markdown": "Attached Markdown file",
    EML_MIME: "Attached email",
}
_EML_HEADERS = ("Subject", "From", "To", "Date")
_BLANK_LINES = re.compile(r"\n{3,}")


class _HtmlText(HTMLParser):
    """Visible text of an HTML email body. Keeps link targets: a phishing link usually
    hides behind harmless anchor text."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1
        elif tag in ("br", "p", "div", "tr", "li"):
            self.parts.append("\n")
        elif tag == "a":
            href = dict(attrs).get("href") or ""
            if href.lower().startswith(("http://", "https://")):
                self.parts.append(f" ({href}) ")

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def _html_to_text(html: str) -> str:
    parser = _HtmlText()
    parser.feed(html)
    parser.close()
    return "".join(parser.parts)


def _eml_text(data: bytes) -> str:
    """Subject/From/To/Date plus the plain-text body (or the HTML body as plain text).
    Attachments are never read or kept."""
    msg = BytesParser(policy=policy.default).parsebytes(data)
    lines = []
    for name in _EML_HEADERS:
        value = msg[name]
        if value:
            lines.append(f"{name}: {value}")

    body = ""
    for kind in ("plain", "html"):
        part = msg.get_body(preferencelist=(kind,))
        if part is None:
            continue
        try:
            content = part.get_content()
        except (LookupError, ValueError):  # unknown charset / undecodable part
            continue
        body = content if kind == "plain" else _html_to_text(content)
        if body.strip():
            break
    return "\n".join(lines) + "\n\n" + body


def prepare_document(mime: str, data: bytes) -> str | None:
    """Validates the content really is what its type claims. Returns the normalized
    text for text-like documents, or None for a PDF (the model reads that itself).
    Raises InputError."""
    if mime == PDF_MIME:
        if not data.startswith(b"%PDF"):
            raise InputError(415, "This file doesn't look like a valid PDF.")
        return None
    try:
        raw = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raw = None
    if raw is None or "\x00" in raw:
        raise InputError(415, "This file isn't a readable UTF-8 text file.")
    if mime == EML_MIME:
        try:
            raw = _eml_text(data)
        except Exception:  # the email parser is lenient, but this is untrusted input
            raise InputError(415, "We couldn't read this email file.") from None
    text = _BLANK_LINES.sub("\n\n", normalize_text(raw.replace("\r\n", "\n")))
    if not text:
        raise InputError(422, "This file has no readable text.")
    return f"{_LABELS[mime]}:\n{text}"


def merge_text(user_text: str | None, document_text: str | None) -> str | None:
    """User text first, then the document, cut to MAX_TEXT_CHARS (never an error)."""
    if not document_text:
        return user_text
    merged = f"{user_text}\n\n{document_text}" if user_text else document_text
    return merged[:MAX_TEXT_CHARS]


def safe_filename(name: str | None) -> str | None:
    """Last path component only, no control/format characters, at most 255 chars."""
    base = re.split(r"[\\/]", name or "")[-1]
    base = "".join(c for c in base if unicodedata.category(c) not in ("Cc", "Cf")).strip()
    return base[:MAX_FILENAME_CHARS] or None
