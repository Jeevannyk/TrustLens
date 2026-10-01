import pytest

from app.checks.heuristics import STRONG, skeleton, url_heuristics
from app.urls import extract_urls, host_of


def test_extracts_full_and_bare_urls():
    text = "Visit https://sbi-kyc.xyz/login now or go to www.paypa1.com/verify, also hdfc-secure.in."
    assert extract_urls(text) == ["https://sbi-kyc.xyz/login", "www.paypa1.com/verify", "hdfc-secure.in"]


def test_extracts_defanged():
    urls = extract_urls("hxxps://evil[.]com/a and bad(.)co(.)in and other{dot}top")
    assert urls == ["https://evil.com/a", "bad.co.in", "other.top"]


def test_ignores_emails_and_plain_words():
    assert extract_urls("mail me at john@gmail.com, e.g. tomorrow. See you at 5.") == []


def test_zero_width_and_dedupe():
    urls = extract_urls("go to ev​il.com and EVIL.com and evil.com")
    assert [u.lower() for u in urls] == ["evil.com"]


def test_empty():
    assert extract_urls(None) == []
    assert extract_urls("") == []


def test_host_of():
    assert host_of("https://user:pw@Example.COM:8080/x") == "example.com"
    assert host_of("bad.co.in/path") == "bad.co.in"


@pytest.mark.parametrize(
    "url,code",
    [
        ("http://xn--pypal-4ve.com/a", "punycode"),
        ("http://pаypal.com", "punycode"),
        ("http://192.168.4.4/login", "ip_literal"),
        ("https://bit.ly/abc", "shortener"),
        ("https://prize.xyz", "suspicious_tld"),
        ("https://www.sbi.co.in@evil.com/x", "userinfo"),
        ("http://bank-secure.com/login", "http_login"),
    ],
)
def test_heuristic_flags(url, code):
    assert code in url_heuristics(url)


def test_clean_urls_have_no_heuristics():
    assert url_heuristics("https://www.google.com/search?q=a") == []
    assert url_heuristics("http://example.com/about") == []
    assert url_heuristics("example.com/login") == []  # bare domain: no scheme claim


def test_only_some_heuristics_are_strong():
    assert "shortener" not in STRONG and "suspicious_tld" not in STRONG and "http_login" not in STRONG


def test_skeleton_maps_cyrillic():
    assert skeleton("gооgle.com") == "google.com"


def test_email_domains_for_sender_checks():
    from app.urls import email_domains

    assert email_domains("Notification via PayPal <service@updates.paypal.com>") == ["updates.paypal.com"]
    assert email_domains("a@b.com, c@D.in") == ["b.com", "d.in"]
    assert email_domains(None) == [] and email_domains("no address here") == []
