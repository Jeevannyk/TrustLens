import ipaddress
import re

from ..urls import ascii_host, host_of, split_url

SHORTENERS = {
    "bit.ly", "tinyurl.com", "t.co", "goo.gl", "is.gd", "cutt.ly", "rb.gy", "shorturl.at",
    "ow.ly", "buff.ly", "tiny.cc", "rebrand.ly", "lnkd.in", "t.ly", "bl.ink", "s.id",
}
SUSPICIOUS_TLDS = {
    "zip", "mov", "xyz", "top", "click", "support", "loan", "work", "gq", "tk", "ml", "cf",
    "ga", "icu", "buzz", "monster", "rest", "country", "kim", "cam", "sbs", "cfd", "cyou",
}
_LOGINISH = re.compile(r"(?i)login|signin|sign-in|verify|account|secure|update|kyc|password|otp|bank|pay|wallet")

# Strong heuristics are individually odd enough to warrant caution; weak ones only
# matter alongside other evidence. Neither kind can by itself make a result "Dangerous".
STRONG = {"punycode", "ip_literal", "userinfo"}

# A few look-alike letters (Cyrillic/Greek) mapped to Latin, for homograph detection.
_CONFUSABLES = str.maketrans("аеорсхуіјѕԁɡοντ", "aeopcxyijsdgovt")


def skeleton(host: str) -> str:
    """Latin-lookalike form of an IDN host, for comparing against brand domains."""
    return host.translate(_CONFUSABLES)


def url_heuristics(url: str) -> list[str]:
    """Cheap, deterministic URL red flags. Returns codes (see STRONG)."""
    codes: list[str] = []
    try:
        parts = split_url(url)
        scheme = parts.scheme.lower() if "://" in url else ""
        userinfo = "@" in parts.netloc
        path = (parts.path or "") + ("?" + parts.query if parts.query else "")
    except ValueError:
        return codes

    host = host_of(url)
    if userinfo:
        codes.append("userinfo")
    if any(ord(c) > 127 for c in host) or any(label.startswith("xn--") for label in host.split(".")):
        codes.append("punycode")
    try:
        ipaddress.ip_address(host.strip("[]"))
        codes.append("ip_literal")
    except ValueError:
        pass
    labels = ascii_host(host).split(".")
    if len(labels) >= 2:
        if ".".join(labels[-2:]) in SHORTENERS:
            codes.append("shortener")
        if labels[-1] in SUSPICIOUS_TLDS:
            codes.append("suspicious_tld")
    if scheme == "http" and _LOGINISH.search(path):
        codes.append("http_login")
    return codes
