import pytest

from app.checks.lookalike import check_lookalike


@pytest.mark.parametrize(
    "domain",
    ["apple.com", "www.google.com", "accounts.google.com", "mail.paypal.com", "www.sbi.co.in", "jio.com", "zoo.com", "maple.com"],
)
def test_not_flagged(domain):
    assert check_lookalike(domain) == (None, None)


@pytest.mark.parametrize(
    "domain,brand",
    [("gooogle.com", "Google"), ("paypa1.com", "PayPal"), ("www.paypa1.com", "PayPal"), ("sbl.co.in", "State Bank of India")],
)
def test_flagged(domain, brand):
    matched, distance = check_lookalike(domain)
    assert matched == brand
    assert distance == 1


def test_official_brand_includes_subdomains_but_not_lookalikes():
    from app.checks.lookalike import official_brand, registrable_domain

    assert official_brand("updates.paypal.com") == "PayPal"
    assert official_brand("www.paypal.com") == "PayPal"
    assert official_brand("paypa1.com") is None
    assert official_brand("paypal.com.evil.xyz") is None
    assert registrable_domain("updates.paypal.com") == "paypal.com"


def test_brand_domain_embedded_in_other_domain_is_lookalike():
    from app.checks.lookalike import check_lookalike

    assert check_lookalike("accounts-google.com.security-verification.example") == ("Google", 0)
    assert check_lookalike("paypal.com.evil.xyz") == ("PayPal", 0)
    assert check_lookalike("www.amazon.in-offers.xyz") == ("Amazon India", 0)
    for real in ["gpay.google.com", "updates.paypal.com", "www.paypal.com", "google.com", "mygoogle.community"]:
        assert check_lookalike(real) == (None, None), real
