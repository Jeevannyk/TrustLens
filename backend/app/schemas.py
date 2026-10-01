from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class ExtractedMessage(BaseModel):
    sender: Optional[str] = None
    claimed_brand: Optional[str] = None
    urgency_signals: list[str] = Field(default_factory=list)
    links: list[str] = Field(default_factory=list)
    claims: list[str] = Field(default_factory=list)
    language_detected: Optional[str] = None
    injection_attempt: bool = False
    injection_evidence: Optional[str] = None
    # What the message asks the reader to share, pay, install or do.
    requested_items: list[str] = Field(default_factory=list)
    asks_for_sensitive_info: bool = False
    payment_ids: list[str] = Field(default_factory=list)
    # Screenshots/PDFs: all readable text, and whether anything useful could be read.
    extracted_text: Optional[str] = None
    image_readable: Optional[bool] = None
    # Set by our code (not the model) when the extraction step could not be completed.
    extraction_failed: bool = False
    # Set by our code (not the model): texts of the QR codes our scanner decoded from the image.
    qr_decoded: list[str] = Field(default_factory=list)

    @field_validator("urgency_signals", "links", "claims", "requested_items", "payment_ids", mode="before")
    @classmethod
    def _none_to_list(cls, v):
        return [] if v is None else v

    @field_validator("injection_attempt", "asks_for_sensitive_info", mode="before")
    @classmethod
    def _none_to_false(cls, v):
        return False if v is None else v


class DomainCheckResult(BaseModel):
    domain: str
    age_days: Optional[int] = None
    is_new_domain: bool = False
    last_changed_days: Optional[int] = None
    expires_in_days: Optional[int] = None
    registrar: Optional[str] = None
    domain_status: list[str] = Field(default_factory=list)
    nameservers: list[str] = Field(default_factory=list)
    # Codes from checks/heuristics.py (punycode, ip_literal, shortener, ...).
    heuristics: list[str] = Field(default_factory=list)
    lookalike_of: Optional[str] = None
    lookalike_distance: Optional[int] = None
    # Set when the domain is the real, official domain (or a subdomain) of a known brand.
    official_domain_of: Optional[str] = None
    safe_browsing_hit: bool = False
    safe_browsing_threat_type: Optional[str] = None
    # None: stored before this field existed. True: the Safe Browsing API answered.
    # False: it did not run (no key) or failed, so "no hit" says nothing.
    safe_browsing_checked: Optional[bool] = None
    error: Optional[str] = None


class Flag(BaseModel):
    title: str
    severity: str  # "high" | "medium" | "low"
    evidence: str


class FloorReason(BaseModel):
    """One automatic check that set a minimum risk level (see risk.Reason). code is a machine
    code such as "lookalike" or "payment_check", evidence is the fact it is based on."""
    code: str
    evidence: str
    severity: str  # "high" | "medium" | "low"


class TrustReport(BaseModel):
    model_config = ConfigDict(protected_namespaces=())  # model_risk_level is not a pydantic internal

    risk_level: str  # "Safe" | "Suspicious" | "Dangerous"
    summary: str
    flags: list[Flag] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    # Short plain statements of what the message does or asks. Never empty.
    findings: list[str] = Field(default_factory=list)
    analysis_incomplete: bool = False
    language: str
    extracted: ExtractedMessage
    domain_checks: list[DomainCheckResult] = Field(default_factory=list)
    # How the verdict was reached. Reports stored before these existed have the defaults.
    floor_reasons: list[FloorReason] = Field(default_factory=list)
    floor_level: Optional[str] = None
    model_risk_level: Optional[str] = None  # what the AI said, before our checks raised it
