from app.risk import Reason, apply_floor, compute_floor, ensure_findings, fallback_report, max_level
from app.schemas import DomainCheckResult, ExtractedMessage, Flag, TrustReport


def _report(level="Safe", flags=None, findings=None, language="en"):
    return TrustReport(
        risk_level=level,
        summary="You may proceed.",
        flags=flags or [],
        recommended_actions=["Proceed."],
        findings=findings or [],
        language=language,
        extracted=ExtractedMessage(),
    )


def _domain(**kw):
    return DomainCheckResult(domain="x.com", **kw)


def test_clean_is_safe():
    assert compute_floor(ExtractedMessage(), [_domain()]) == ("Safe", [])


def test_safe_browsing_hit_is_dangerous():
    level, reasons = compute_floor(ExtractedMessage(), [_domain(safe_browsing_hit=True, safe_browsing_threat_type="MALWARE")])
    assert level == "Dangerous" and reasons[0].code == "safe_browsing"


def test_lookalike_is_dangerous():
    level, _ = compute_floor(ExtractedMessage(), [_domain(lookalike_of="PayPal", lookalike_distance=1)])
    assert level == "Dangerous"


def test_new_domain_needs_intent():
    assert compute_floor(ExtractedMessage(), [_domain(is_new_domain=True, age_days=3)])[0] == "Safe"
    urgent = ExtractedMessage(urgency_signals=["act now"])
    assert compute_floor(urgent, [_domain(is_new_domain=True, age_days=3)])[0] == "Suspicious"


def test_sensitive_request_alone_is_suspicious():
    ex = ExtractedMessage(asks_for_sensitive_info=True, requested_items=["password"])
    level, reasons = compute_floor(ex, [])
    assert level == "Suspicious" and reasons[0].evidence == "password"


def test_weak_heuristic_alone_stays_safe_strong_goes_suspicious_never_dangerous():
    assert compute_floor(ExtractedMessage(), [_domain(heuristics=["shortener"])])[0] == "Safe"
    assert compute_floor(ExtractedMessage(), [_domain(heuristics=["punycode"])])[0] == "Suspicious"
    every = ["punycode", "ip_literal", "userinfo", "shortener", "suspicious_tld", "http_login"]
    ex = ExtractedMessage(asks_for_sensitive_info=True, urgency_signals=["now"])
    assert compute_floor(ex, [_domain(heuristics=every)])[0] == "Suspicious"


def test_weak_heuristic_with_intent_is_suspicious():
    ex = ExtractedMessage(urgency_signals=["now"])
    assert compute_floor(ex, [_domain(heuristics=["shortener"])])[0] == "Suspicious"


def test_unreadable_image_only_without_text():
    ex = ExtractedMessage(image_readable=False)
    assert compute_floor(ex, [], has_text=False, has_image=True)[0] == "Suspicious"
    assert compute_floor(ex, [], has_text=True, has_image=True)[0] == "Safe"


def test_injection_and_failed_extraction():
    assert compute_floor(ExtractedMessage(injection_attempt=True), [])[0] == "Suspicious"
    assert compute_floor(ExtractedMessage(extraction_failed=True), [])[0] == "Suspicious"


def test_max_level_treats_unknown_as_suspicious():
    assert max_level("Weird", "Safe") == "Weird"
    assert max_level("Safe", "Dangerous") == "Dangerous"


def test_apply_floor_overrides_contradicting_model_answer():
    report = _report("Safe")
    out = apply_floor(report, "Suspicious", [Reason("sensitive_request", "gimme the password")])
    assert out.risk_level == "Suspicious"
    assert "proceed" not in out.summary.lower()
    assert out.flags and out.flags[0].evidence == "gimme the password"
    assert out.findings and out.recommended_actions != ["Proceed."]


def test_apply_floor_keeps_higher_model_answer():
    report = _report("Dangerous", flags=[Flag(title="t", severity="high", evidence="e")])
    out = apply_floor(report, "Suspicious", [Reason("sensitive_request", "x")])
    assert out.risk_level == "Dangerous" and out.summary == "You may proceed."


def test_apply_floor_unreadable_message_and_language():
    out = apply_floor(_report("Safe", language="hi"), "Suspicious", [Reason("unreadable", "image")])
    assert out.flags == [] and out.risk_level == "Suspicious"
    assert "तस्वीर" in out.summary


def test_unknown_model_level_never_safe():
    out = apply_floor(_report("Weird"), "Safe", [])
    assert out.risk_level == "Suspicious"


def test_ensure_findings_never_empty():
    assert ensure_findings(_report("Safe")).findings
    flagged = _report("Suspicious", flags=[Flag(title="Odd link", severity="low", evidence="e")])
    assert ensure_findings(flagged).findings == ["Odd link"]
    assert ensure_findings(_report("Suspicious")).findings == ["You may proceed."]


def test_fallback_is_cautious():
    out = fallback_report("en", ExtractedMessage(), [])
    assert out.risk_level == "Suspicious" and out.analysis_incomplete and "careful" in out.summary
