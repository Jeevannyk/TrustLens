"""Deterministic risk floors applied after the model answers. Pure functions, no I/O."""
from dataclasses import dataclass

from .checks.heuristics import STRONG
from .messages import (
    FALLBACK_ACTIONS,
    FALLBACK_SUMMARY,
    FLAG_TITLES,
    FLOOR_SUMMARY,
    SAFE_FINDING,
    UNREADABLE_SUMMARY,
    pick,
)
from .schemas import DomainCheckResult, ExtractedMessage, Flag, TrustReport

LEVELS = {"Safe": 0, "Suspicious": 1, "Dangerous": 2}
NEW_DOMAIN_DAYS = 30


@dataclass(frozen=True)
class Reason:
    code: str
    evidence: str
    severity: str = "high"


def level_rank(level: str) -> int:
    # An unknown level from upstream is treated as Suspicious, never as Safe.
    return LEVELS.get(level, 1)


def max_level(a: str, b: str) -> str:
    return a if level_rank(a) >= level_rank(b) else b


def compute_floor(
    extracted: ExtractedMessage,
    domain_checks: list[DomainCheckResult],
    *,
    has_text: bool = True,
    has_image: bool = False,
) -> tuple[str, list[Reason]]:
    """Returns (minimum risk level, reasons). Rules:
    - Safe Browsing hit or a confirmed brand lookalike -> Dangerous.
    - Asking for private details, injection attempts, unreadable/failed analysis,
      strong URL oddities, or a brand-new domain combined with credential/urgency
      intent -> Suspicious.
    - Heuristics alone never reach Dangerous.
    has_image covers any attachment the model reads itself (screenshot, PDF or video)."""
    level = "Safe"
    reasons: list[Reason] = []

    def raise_to(new: str, reason: Reason) -> None:
        nonlocal level
        level = max_level(level, new)
        reasons.append(reason)

    intent = extracted.asks_for_sensitive_info or bool(extracted.urgency_signals)

    for check in domain_checks:
        if check.safe_browsing_hit:
            raise_to("Dangerous", Reason("safe_browsing", f"{check.domain} ({check.safe_browsing_threat_type or 'threat'})"))
        if check.lookalike_of:
            raise_to("Dangerous", Reason("lookalike", f"{check.domain} ~ {check.lookalike_of}"))
        if check.is_new_domain and intent:
            raise_to("Suspicious", Reason("new_domain", f"{check.domain} ({check.age_days} days)", "medium"))
        codes = set(check.heuristics)
        if codes & STRONG or (codes and intent):
            raise_to("Suspicious", Reason("suspicious_link", check.domain, "medium"))

    if extracted.asks_for_sensitive_info:
        evidence = "; ".join(extracted.requested_items[:3]) or "asks for private details"
        raise_to("Suspicious", Reason("sensitive_request", evidence))
    if extracted.injection_attempt:
        raise_to("Suspicious", Reason("injection", extracted.injection_evidence or "manipulation attempt"))
    if has_image and not has_text and extracted.image_readable is False:
        raise_to("Suspicious", Reason("unreadable", "image"))
    if extracted.extraction_failed:
        raise_to("Suspicious", Reason("incomplete", "analysis"))
    return level, reasons


def fallback_report(
    language: str, extracted: ExtractedMessage, domain_checks: list[DomainCheckResult]
) -> TrustReport:
    return TrustReport(
        risk_level="Suspicious",
        summary=pick(FALLBACK_SUMMARY, language),
        flags=[],
        recommended_actions=list(pick(FALLBACK_ACTIONS, language)),
        findings=[pick(FALLBACK_SUMMARY, language)],
        analysis_incomplete=True,
        language=language,
        extracted=extracted,
        domain_checks=domain_checks,
    )


def apply_floor(report: TrustReport, floor_level: str, reasons: list[Reason]) -> TrustReport:
    """Raise report.risk_level to floor_level if the model came in lower, replacing the
    model's (now contradicted) summary/actions and adding flags for the reasons."""
    report.risk_level = report.risk_level if report.risk_level in LEVELS else "Suspicious"
    if level_rank(report.risk_level) >= level_rank(floor_level):
        return report

    lang = report.language
    codes = {r.code for r in reasons}
    only_unreadable = codes <= {"unreadable", "incomplete"}
    if "unreadable" in codes and only_unreadable:
        report.summary = pick(UNREADABLE_SUMMARY, lang)
    elif "incomplete" in codes and only_unreadable:
        report.summary = pick(FALLBACK_SUMMARY, lang)
    else:
        report.summary = pick(FLOOR_SUMMARY[floor_level], lang)
    report.recommended_actions = list(pick(FALLBACK_ACTIONS, lang))
    existing = {f.title for f in report.flags}
    for reason in reasons:
        if reason.code in ("unreadable", "incomplete"):
            continue
        title = pick(FLAG_TITLES[reason.code], lang)
        if title not in existing:
            report.flags.append(Flag(title=title, severity=reason.severity, evidence=reason.evidence))
    report.findings = [f.title for f in report.flags] or [report.summary]
    report.risk_level = floor_level
    if "incomplete" in codes:
        report.analysis_incomplete = True
    return report


def ensure_findings(report: TrustReport) -> TrustReport:
    """"What we found" must never be empty."""
    if report.findings:
        return report
    if report.risk_level == "Safe":
        report.findings = [pick(SAFE_FINDING, report.language)]
    else:
        report.findings = [f.title for f in report.flags] or [report.summary]
    return report
