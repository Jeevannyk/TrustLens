import re
from urllib.parse import urlsplit

from .text_utils import normalize_text

_TLDS = sorted(
    {
        "com", "org", "net", "edu", "gov", "in", "co", "io", "me", "info", "biz", "xyz", "top",
        "online", "site", "shop", "store", "app", "dev", "ai", "tech", "club", "live", "link",
        "click", "support", "help", "bank", "pay", "uk", "us", "ca", "au", "de", "fr", "nl", "ru",
        "cn", "jp", "kr", "br", "za", "ng", "pk", "bd", "lk", "np", "ae", "sg", "my", "id", "ph",
        "tv", "cc", "ws", "to", "ly", "gl", "gd", "is", "it", "es", "se", "no", "fi", "ch", "at",
        "be", "pl", "tk", "ml", "ga", "cf", "gq", "icu", "buzz", "monster", "rest", "cam", "sbs",
        "cfd", "work", "loan", "zip", "mov", "vip", "fun", "cyou", "ink", "page", "website",
        "space", "cloud", "life", "world", "today", "mobi", "pro", "asia", "sbi", "country", "kim",
    },
    key=len,
    reverse=True,
)

_URL_RE = re.compile(r"(?i)\b(?:https?://|www\.)[^\s<>\"'`]+")
_BARE_RE = re.compile(
    r"(?i)(?<![\w@./:\-])(?:[^\W_][\w\-]*\.)+(?:" + "|".join(_TLDS) + r")(?![\w\-])(?::\d+)?(?:/[^\s<>\"'`]*)?"
)
_TRAILING = ".,;:!?)]}>'\""
_MAX_URLS = 25


def refang(text: str) -> str:
    """Undo common defanging so hxxp://evil[.]com becomes http://evil.com."""
    out = re.sub(r"(?i)\bhxxp(s?)", r"http\1", text)
    out = re.sub(r"(?i)\bh\*\*p(s?)", r"http\1", out)
    out = re.sub(r"\[:\]|\(:\)|\[://\]", ":", out)
    out = re.sub(r"(?i)[\[({]\s*(?:\.|dot)\s*[\])}]", ".", out)
    return out


def extract_urls(text: str | None) -> list[str]:
    """All URLs and bare domains in text (defanged forms included), de-duplicated,
    in order of appearance. Bare domains are returned without a scheme."""
    if not text:
        return []
    cleaned = refang(normalize_text(text, for_matching=True))
    found: list[tuple[int, str]] = []
    covered: list[tuple[int, int]] = []
    for m in _URL_RE.finditer(cleaned):
        found.append((m.start(), m.group().rstrip(_TRAILING)))
        covered.append((m.start(), m.end()))
    for m in _BARE_RE.finditer(cleaned):
        if any(s <= m.start() < e for s, e in covered):
            continue
        found.append((m.start(), m.group().rstrip(_TRAILING)))
    seen: set[str] = set()
    result: list[str] = []
    for _, url in sorted(found):
        key = url.lower()
        if url and key not in seen:
            seen.add(key)
            result.append(url)
    return result[:_MAX_URLS]


def split_url(url: str):
    return urlsplit(url if "://" in url else f"//{url}")


def host_of(url: str) -> str:
    """Lowercased hostname without userinfo/port; falls back to the raw string."""
    try:
        host = (split_url(url).hostname or "").rstrip(".").lower()
    except ValueError:
        host = ""
    return host or url.lower()


def ascii_host(host: str) -> str:
    """IDNA/punycode form of host, or host unchanged if it can't be encoded."""
    try:
        return host.encode("idna").decode("ascii")
    except UnicodeError:
        return host
