import re
import unicodedata

MAX_TEXT_CHARS = 10_000
MAX_LINK_CHARS = 2_048

# Invisible characters used to break up words/URLs so naive matching misses them.
_ALWAYS_STRIP = re.compile("[​⁠﻿­‪-‮⁦-⁩]")
# ZWNJ/ZWJ are meaningful in Indic scripts, so only strip them for matching.
_JOINERS = re.compile("[‌‍]")
_CONTROL = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class InputError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def normalize_text(value: str | None, *, for_matching: bool = False) -> str:
    """NFKC-normalize and strip invisible/control characters. for_matching also strips
    ZWJ/ZWNJ (safe for URL/keyword matching, not for display or model input)."""
    if not value:
        return ""
    out = unicodedata.normalize("NFKC", value)
    out = _ALWAYS_STRIP.sub("", out)
    out = _CONTROL.sub("", out)
    if for_matching:
        out = _JOINERS.sub("", out)
    return out.strip()


def validate_input(text: str | None, link: str | None, has_image: bool) -> tuple[str | None, str | None]:
    """Returns cleaned (text, link) or raises InputError."""
    clean_text = normalize_text(text) or None
    clean_link = normalize_text(link) or None
    if clean_text and len(clean_text) > MAX_TEXT_CHARS:
        raise InputError(413, f"Message is too long. Maximum is {MAX_TEXT_CHARS:,} characters.")
    if clean_link and len(clean_link) > MAX_LINK_CHARS:
        raise InputError(413, f"Link is too long. Maximum is {MAX_LINK_CHARS:,} characters.")
    if not (clean_text or clean_link or has_image):
        raise InputError(422, "Provide a message, a link, or a screenshot.")
    return clean_text, clean_link
