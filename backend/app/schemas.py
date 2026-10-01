from typing import Optional
from pydantic import BaseModel, Field


class ExtractedMessage(BaseModel):
    sender: Optional[str] = None
    claimed_brand: Optional[str] = None
    urgency_signals: list[str] = Field(default_factory=list)
    links: list[str] = Field(default_factory=list)
    claims: list[str] = Field(default_factory=list)
    language_detected: Optional[str] = None
    injection_attempt: bool = False
    injection_evidence: Optional[str] = None


class DomainCheckResult(BaseModel):
    domain: str
    age_days: Optional[int] = None
    is_new_domain: bool = False
    lookalike_of: Optional[str] = None
    lookalike_distance: Optional[int] = None
    safe_browsing_hit: bool = False
    safe_browsing_threat_type: Optional[str] = None
    error: Optional[str] = None


class Flag(BaseModel):
    title: str
    severity: str  # "high" | "medium" | "low"
    evidence: str


class TrustReport(BaseModel):
    risk_level: str  # "Safe" | "Suspicious" | "Dangerous"
    summary: str
    flags: list[Flag] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    language: str
    extracted: ExtractedMessage
    domain_checks: list[DomainCheckResult] = Field(default_factory=list)
