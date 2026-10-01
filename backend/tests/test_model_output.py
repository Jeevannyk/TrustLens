import pytest

from app import gemini_client
from app.gemini_client import OutputInvalid
from app.model_output import parse_model_json, validate_extracted, validate_report

GOOD = '{"risk_level": "High risk", "summary": "Bad.", "flags": [{"title": "t", "evidence": "e", "severity": "HIGH"}], "recommended_actions": ["a"], "findings": ["f"]}'


def test_parse_strips_fences_and_prose():
    assert parse_model_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_model_json('Sure! {"a": 1} hope that helps') == {"a": 1}


@pytest.mark.parametrize("raw", ["", "no json here", "[1, 2]", "{broken"])
def test_parse_rejects_garbage(raw):
    with pytest.raises(ValueError):
        parse_model_json(raw)


def test_report_normalizes_level_and_severity():
    report = validate_report(parse_model_json(GOOD))
    assert report.risk_level == "Dangerous"
    assert report.flags[0].severity == "high"


def test_report_drops_flags_without_evidence_and_rejects_bad_level():
    data = {"risk_level": "Safe", "summary": "ok", "flags": [{"title": "vague", "evidence": ""}, "junk"]}
    assert validate_report(data).flags == []
    with pytest.raises(ValueError):
        validate_report({"risk_level": "Maybe", "summary": "x"})
    with pytest.raises(ValueError):
        validate_report({"risk_level": "Safe", "summary": "  "})


def test_extracted_tolerates_nulls():
    ex = validate_extracted({"links": None, "claims": None, "injection_attempt": None, "unknown": 1})
    assert ex.links == [] and ex.injection_attempt is False


class FakeResponse:
    def __init__(self, text):
        self._text = text

    @property
    def text(self):
        if self._text is None:
            raise ValueError("blocked")
        return self._text


def _patch_generate(monkeypatch, replies):
    calls = []

    def fake(system_prompt, content, *a, **k):
        calls.append(content)
        return FakeResponse(replies[len(calls) - 1])

    monkeypatch.setattr(gemini_client, "_generate", fake)
    return calls


def test_repair_retry_succeeds(monkeypatch):
    calls = _patch_generate(monkeypatch, ["not json", GOOD])
    report = gemini_client._generate_validated("sys", ["payload"], validate_report)
    assert report.risk_level == "Dangerous"
    assert len(calls) == 2 and "valid JSON" in calls[1][-1]


def test_gives_up_after_one_repair(monkeypatch):
    calls = _patch_generate(monkeypatch, ["nope", None, GOOD])
    with pytest.raises(OutputInvalid):
        gemini_client._generate_validated("sys", ["payload"], validate_report)
    assert len(calls) == 2
