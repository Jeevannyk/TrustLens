import asyncio

import pytest
from fastapi.testclient import TestClient

from app import domain_checks, gemini_client, main, pipeline
from app.model_output import ModelReport
from app.schemas import DomainCheckResult, ExtractedMessage


def _safe_model_report():
    return ModelReport(
        risk_level="Safe",
        summary="Looks fine, you may proceed safely.",
        recommended_actions=["Proceed."],
        findings=["Nothing to worry about."],
    )


def _patch(monkeypatch, extracted=None, report=None, checks=None, extract_exc=None, synth_exc=None):
    def extract(*a, **k):
        if extract_exc:
            raise extract_exc
        return extracted or ExtractedMessage()

    def synth(*a, **k):
        if synth_exc:
            raise synth_exc
        return report or _safe_model_report()

    async def run_checks(urls):
        run_checks.urls = urls
        return checks or []

    monkeypatch.setattr(gemini_client, "extract_message", extract)
    monkeypatch.setattr(gemini_client, "synthesize_report", synth)
    monkeypatch.setattr(domain_checks, "run_domain_checks", run_checks)
    monkeypatch.setattr(main.storage, "save_analysis", lambda **k: 1)  # keep tests off the real DB
    return run_checks


def _run(**kw):
    args = dict(text="x", link=None, image_bytes=None, image_mime=None, language="en")
    args.update(kw)
    return asyncio.run(pipeline.analyze_message(**args))


def test_credential_request_cannot_be_safe(monkeypatch):
    ex = ExtractedMessage(asks_for_sensitive_info=True, requested_items=["password"])
    _patch(monkeypatch, extracted=ex)
    report = _run(text="gimme the password")
    assert report.risk_level == "Suspicious"
    assert "safely" not in report.summary
    assert report.findings and report.flags


def test_clean_message_stays_safe_with_findings(monkeypatch):
    _patch(monkeypatch, report=ModelReport(risk_level="Safe", summary="Just a chat message.", recommended_actions=["None."]))
    report = _run(text="see you at 5")
    assert report.risk_level == "Safe" and report.flags == []
    assert report.findings == ["Nothing in this message asks for money, codes, passwords or links."]


def test_urls_from_image_text_and_links_are_checked(monkeypatch):
    ex = ExtractedMessage(extracted_text="Login at hxxp://sbi-kyc[.]xyz now", links=["other.top"])
    run_checks = _patch(monkeypatch, extracted=ex)
    _run(text="see https://a.com", link="b.in")
    assert set(run_checks.urls) == {"https://a.com", "b.in", "http://sbi-kyc.xyz", "other.top"}


def test_hard_check_floor_applies_over_model(monkeypatch):
    checks = [DomainCheckResult(domain="paypa1.com", lookalike_of="PayPal", lookalike_distance=1)]
    _patch(monkeypatch, checks=checks)
    assert _run(text="paypa1.com").risk_level == "Dangerous"


def test_invalid_synthesis_falls_back_cautiously(monkeypatch):
    _patch(monkeypatch, synth_exc=gemini_client.OutputInvalid())
    report = _run()
    assert report.risk_level == "Suspicious" and report.analysis_incomplete


def test_invalid_extraction_falls_back_cautiously(monkeypatch):
    _patch(monkeypatch, extract_exc=gemini_client.OutputInvalid())
    report = _run()
    assert report.risk_level == "Suspicious" and report.analysis_incomplete


def test_unreadable_image_not_safe(monkeypatch):
    _patch(monkeypatch, extracted=ExtractedMessage(image_readable=False))
    report = _run(text=None, image_bytes=b"x", image_mime="image/png")
    assert report.risk_level == "Suspicious"
    assert "couldn't read" in report.summary


def test_unreadable_pdf_not_safe(monkeypatch):
    _patch(monkeypatch, extracted=ExtractedMessage(image_readable=False))
    report = _run(text=None, file_bytes=b"%PDF-1.4", file_mime="application/pdf")
    assert report.risk_level == "Suspicious"
    assert "couldn't read" in report.summary


def test_pdf_is_passed_to_the_model_inline(monkeypatch):
    seen = []
    _patch(monkeypatch)
    monkeypatch.setattr(gemini_client, "extract_message", lambda *a: seen.append(a) or ExtractedMessage())
    _run(text="x", file_bytes=b"%PDF-1.4", file_mime="application/pdf")
    assert seen == [("x", b"%PDF-1.4", "application/pdf")]


def test_unknown_language_defaults_to_english(monkeypatch):
    _patch(monkeypatch)
    assert _run(language="xx").language == "en"


def test_model_down_gives_503_without_details(monkeypatch):
    _patch(monkeypatch, extract_exc=gemini_client.ModelUnavailable("quota exceeded for gemini key abc"))
    r = TestClient(main.app).post("/analyze", data={"text": "hi"})
    assert r.status_code == 503
    assert "gemini" not in r.text.lower() and "quota" not in r.text.lower()


def test_endpoint_validates_input(monkeypatch):
    _patch(monkeypatch)
    client = TestClient(main.app)
    assert client.post("/analyze", data={"text": "   "}).status_code == 422
    assert client.post("/analyze", data={"text": "a" * 10_001}).status_code == 413


def test_save_failure_does_not_fail_analysis(monkeypatch):
    _patch(monkeypatch)

    def boom(**kw):
        raise RuntimeError("disk full")

    monkeypatch.setattr(main.storage, "save_analysis", boom)
    r = TestClient(main.app).post("/analyze", data={"text": "see you at 5"})
    assert r.status_code == 200 and r.json()["risk_level"] == "Safe"


# --- domain checks degrade instead of failing ---------------------------------------------

def test_slow_checks_time_out_and_degrade(monkeypatch):
    async def slow_rdap(domain, client):
        await asyncio.sleep(5)

    async def slow_sb(urls, client):
        await asyncio.sleep(5)

    monkeypatch.setattr(domain_checks, "get_domain_info", slow_rdap)
    monkeypatch.setattr(domain_checks, "check_safe_browsing", slow_sb)
    monkeypatch.setattr(domain_checks, "CHECK_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setattr(domain_checks, "RETRY_BACKOFF_SECONDS", 0.01)
    results = asyncio.run(domain_checks.run_domain_checks(["paypa1.com", "http://192.168.1.1/login"]))
    by_domain = {r.domain: r for r in results}
    assert by_domain["paypa1.com"].error == "Domain age lookup unavailable"
    assert by_domain["paypa1.com"].lookalike_of == "PayPal"  # local checks still ran
    assert "ip_literal" in by_domain["192.168.1.1"].heuristics
    assert by_domain["192.168.1.1"].error is None  # RDAP skipped for IPs


def test_failing_checks_do_not_leak_exception_text(monkeypatch):
    async def bad_rdap(domain, client):
        raise RuntimeError("secret-host.internal exploded")

    async def bad_sb(urls, client):
        raise RuntimeError("boom")

    monkeypatch.setattr(domain_checks, "get_domain_info", bad_rdap)
    monkeypatch.setattr(domain_checks, "check_safe_browsing", bad_sb)
    monkeypatch.setattr(domain_checks, "RETRY_BACKOFF_SECONDS", 0.01)
    (result,) = asyncio.run(domain_checks.run_domain_checks(["example.com"]))
    assert "secret" not in (result.error or "")
    assert result.safe_browsing_hit is False


def test_sender_email_domain_is_checked(monkeypatch):
    ex = ExtractedMessage(sender="PayPal <service@paypa1.com>")
    run_checks = _patch(monkeypatch, extracted=ex)
    _run(text="hello")
    assert run_checks.urls == ["paypa1.com"]


def test_rdap_uses_registrable_domain_for_subdomains(monkeypatch):
    seen = []

    async def fake_info(domain, client):
        seen.append(domain)
        return {"age_days": 9940}, None

    async def fake_sb(urls, client):
        return {}

    monkeypatch.setattr(domain_checks, "get_domain_info", fake_info)
    monkeypatch.setattr(domain_checks, "check_safe_browsing", fake_sb)
    [check] = asyncio.run(domain_checks.run_domain_checks(["updates.paypal.com"]))
    assert seen == ["paypal.com"]
    assert check.domain == "updates.paypal.com" and check.official_domain_of == "PayPal" and check.error is None
