import asyncio
from datetime import datetime, timedelta, timezone

from app.checks.domain_age import get_domain_info


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


class FakeClient:
    def __init__(self, response):
        self._response = response

    async def get(self, url, **kwargs):
        return self._response


def _iso(days_from_now: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days_from_now)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _run(payload, status_code=200):
    return asyncio.run(get_domain_info("example.com", FakeClient(FakeResponse(payload, status_code))))


def test_full_payload():
    payload = {
        "events": [
            {"eventAction": "registration", "eventDate": _iso(-100)},
            {"eventAction": "last changed", "eventDate": _iso(-5)},
            {"eventAction": "expiration", "eventDate": _iso(200)},
        ],
        "status": ["client transfer prohibited"],
        "entities": [
            {"roles": ["registrar"], "vcardArray": ["vcard", [["fn", {}, "text", "Example Registrar"]]]}
        ],
        "nameservers": [{"ldhName": "ns1.example.com"}],
    }
    info, error = _run(payload)
    assert error is None
    assert info["age_days"] == 100
    assert info["last_changed_days"] == 5
    assert info["expires_in_days"] in (199, 200)
    assert info["registrar"] == "Example Registrar"
    assert info["domain_status"] == ["client transfer prohibited"]
    assert info["nameservers"] == ["ns1.example.com"]


def test_missing_fields():
    info, error = _run({})
    assert error is None
    assert info == {}


def test_bad_date_keeps_other_fields():
    payload = {
        "events": [
            {"eventAction": "registration", "eventDate": "not-a-date"},
            {"eventAction": "expiration", "eventDate": _iso(50)},
        ]
    }
    info, error = _run(payload)
    assert error is None
    assert "age_days" not in info
    assert info["expires_in_days"] in (49, 50)


def test_odd_registrar_shapes_do_not_crash():
    payload = {
        "entities": [
            {"roles": "registrar", "vcardArray": ["vcard", [["fn", {}, "text", "X"]]]},
            {"roles": ["registrar"], "vcardArray": ["vcard", [["fn", {}, "text", ["not", "a", "string"]]]], "handle": "H1"},
        ]
    }
    info, error = _run(payload)
    assert error is None
    assert info["registrar"] == "H1"


def test_non_200_returns_error():
    info, error = _run({}, status_code=404)
    assert info == {}
    assert "404" in error
