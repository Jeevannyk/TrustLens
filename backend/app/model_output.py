"""Parsing and validation of the model's JSON replies. Pure functions."""
import json
import re

from pydantic import BaseModel, Field, field_validator

from .schemas import ExtractedMessage, Flag

_FENCE = re.compile(r"^\s*```[a-zA-Z]*\s*|\s*```\s*$")

_LEVEL_ALIASES = {
    "safe": "Safe",
    "low": "Safe",
    "suspicious": "Suspicious",
    "needs caution": "Suspicious",
    "caution": "Suspicious",
    "medium": "Suspicious",
    "dangerous": "Dangerous",
    "high": "Dangerous",
    "high risk": "Dangerous",
    "high-risk": "Dangerous",
}


def parse_model_json(raw: str) -> dict:
    """Strip code fences / stray prose and return the JSON object. Raises ValueError."""
    text = _FENCE.sub("", raw or "").strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise ValueError("no JSON object in model output")
        data = json.loads(text[start : end + 1])
    if not isinstance(data, dict):
        raise ValueError("model output is not a JSON object")
    return data


class ModelReport(BaseModel):
    risk_level: str
    summary: str
    flags: list[Flag] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    findings: list[str] = Field(default_factory=list)

    @field_validator("risk_level", mode="before")
    @classmethod
    def _level(cls, v):
        key = str(v).strip().lower()
        if key not in _LEVEL_ALIASES:
            raise ValueError(f"unknown risk level: {v!r}")
        return _LEVEL_ALIASES[key]

    @field_validator("summary")
    @classmethod
    def _summary(cls, v):
        if not v.strip():
            raise ValueError("empty summary")
        return v.strip()

    @field_validator("flags", mode="before")
    @classmethod
    def _flags(cls, v):
        # Drop flags that cannot cite evidence instead of failing the whole report.
        cleaned = []
        for item in v or []:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            evidence = str(item.get("evidence") or "").strip()
            if not title or not evidence:
                continue
            severity = str(item.get("severity") or "").strip().lower()
            cleaned.append(
                {"title": title, "evidence": evidence, "severity": severity if severity in ("high", "medium", "low") else "medium"}
            )
        return cleaned

    @field_validator("recommended_actions", "findings", mode="before")
    @classmethod
    def _strings(cls, v):
        return [str(x).strip() for x in (v or []) if str(x).strip()]


def validate_extracted(data: dict) -> ExtractedMessage:
    return ExtractedMessage(**data)


def validate_report(data: dict) -> ModelReport:
    return ModelReport(**data)
