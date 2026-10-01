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
