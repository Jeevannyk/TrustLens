import pytest
from fastapi.testclient import TestClient

from app import domain_checks, gemini_client, guards, main, storage
from app.model_output import ModelReport
from app.schemas import ExtractedMessage


@pytest.fixture
def api(monkeypatch, tmp_path):
    """TestClient with the model stubbed; counts how often the model was asked."""
    calls = {"extract": 0, "synth": 0, "fail_synth": False}

    def extract(text, data, mime):
        calls["extract"] += 1
        return ExtractedMessage()

    def synthesize(*a, **k):
        calls["synth"] += 1
        if calls["fail_synth"]:
            raise gemini_client.OutputInvalid()
        return ModelReport(risk_level="Safe", summary="Fine.", recommended_actions=["None."])

    async def run_checks(urls):
        return []

    monkeypatch.setattr(storage, "DB_PATH", tmp_path / "t.db")
    storage.init_db()
    monkeypatch.setattr(gemini_client, "extract_message", extract)
    monkeypatch.setattr(gemini_client, "synthesize_report", synthesize)
    monkeypatch.setattr(domain_checks, "run_domain_checks", run_checks)
    client = TestClient(main.app)
    client.calls = calls
    return client


def _analyze(client, text="see you at 5", **data):
    return client.post("/analyze", data={"text": text, **data})


def test_same_input_twice_runs_the_model_once(api):
    first = _analyze(api)
    second = _analyze(api)
    assert first.status_code == second.status_code == 200
    assert "x-cache" not in first.headers and second.headers["x-cache"] == "HIT"
    assert second.json() == first.json()
    assert api.calls == {"extract": 1, "synth": 1, "fail_synth": False}


def test_a_different_language_or_input_is_a_different_entry(api):
    _analyze(api, language="en")
    assert _analyze(api, language="hi").headers.get("x-cache") is None
    assert _analyze(api, text="something else").headers.get("x-cache") is None
    assert api.calls["synth"] == 3
    assert _analyze(api, language="xx").headers["x-cache"] == "HIT"  # unknown language is English


def test_file_bytes_are_part_of_the_key(api):
    def post(content):
        return api.post("/analyze", data={"text": "hi"}, files={"file": ("a.txt", content, "text/plain")})

    post(b"one")
    assert post(b"one").headers["x-cache"] == "HIT"
    assert post(b"two").headers.get("x-cache") is None


def test_an_incomplete_fallback_report_is_not_cached(api):
    api.calls["fail_synth"] = True
    first = _analyze(api)
    assert first.json()["analysis_incomplete"] is True
    api.calls["fail_synth"] = False
    second = _analyze(api)
    assert second.headers.get("x-cache") is None and second.json()["analysis_incomplete"] is False
    assert api.calls["synth"] == 2


def test_cache_can_be_turned_off(api, monkeypatch):
    monkeypatch.setenv("CACHE_TTL_SECONDS", "0")
    _analyze(api)
    assert _analyze(api).headers.get("x-cache") is None


def test_third_distinct_request_in_a_minute_is_429_and_cache_hits_are_free(api, monkeypatch):
    monkeypatch.setenv("ANALYZE_RATE_PER_MIN", "2")
    assert _analyze(api, "one").status_code == 200
    assert _analyze(api, "two").status_code == 200
    for _ in range(5):  # hits do not consume the quota
        assert _analyze(api, "one").headers["x-cache"] == "HIT"
    r = _analyze(api, "three")
    assert r.status_code == 429
    retry_after = int(r.headers["retry-after"])
    assert 1 <= retry_after <= 60
    assert r.json() == {"detail": f"Too many analyses. Try again in {retry_after} seconds."}
    assert api.calls["synth"] == 2


def test_the_limit_is_per_ip_and_zero_disables_it(api, monkeypatch):
    monkeypatch.setenv("ANALYZE_RATE_PER_MIN", "1")
    monkeypatch.setenv("TRUST_PROXY", "1")
    assert _analyze(api, "a").status_code == 200
    assert api.post("/analyze", data={"text": "b"}, headers={"X-Forwarded-For": "9.9.9.9"}).status_code == 200
    assert _analyze(api, "c").status_code == 429
    monkeypatch.setenv("ANALYZE_RATE_PER_MIN", "0")
    assert _analyze(api, "d").status_code == 200


def test_x_forwarded_for_is_ignored_unless_trust_proxy_is_on(api, monkeypatch):
    monkeypatch.setenv("ANALYZE_RATE_PER_MIN", "1")

    def post(text, ip):
        return api.post("/analyze", data={"text": text}, headers={"X-Forwarded-For": ip})

    assert post("a", "1.1.1.1").status_code == 200
    assert post("b", "2.2.2.2").status_code == 429  # same real client, spoofed header ignored
    monkeypatch.setenv("TRUST_PROXY", "1")
    assert post("c", "3.3.3.3, 10.0.0.1").status_code == 200  # first entry of the header is used
    assert post("d", "3.3.3.3").status_code == 429


def test_cache_entries_expire():
    now = [100.0]
    cache = guards.ResultCache(clock=lambda: now[0])
    cache.put("k", "report", ttl_seconds=600)
    now[0] = 699.0
    assert cache.get("k") == "report"
    now[0] = 700.0
    assert cache.get("k") is None


def test_cache_keeps_at_most_64_entries_dropping_the_least_recently_used():
    cache = guards.ResultCache()
    for i in range(64):
        cache.put(str(i), i, 600)
    cache.get("0")  # a read keeps it alive
    cache.put("new", "x", 600)
    assert cache.get("1") is None and cache.get("0") == 0 and cache.get("new") == "x"


def test_rate_window_slides(monkeypatch):
    monkeypatch.setenv("ANALYZE_RATE_PER_MIN", "2")
    now = [0.0]
    limiter = guards.RateLimiter(clock=lambda: now[0])
    assert limiter.check("ip") == (True, 0)
    now[0] = 10.0
    assert limiter.check("ip") == (True, 0)
    assert limiter.check("ip") == (False, 50)
    assert limiter.check("other") == (True, 0)
    now[0] = 60.0  # the first hit left the window
    assert limiter.check("ip") == (True, 0)
    assert limiter.check("ip") == (False, 10)
