import pytest

from app.prompts import EXTRACTION_SYSTEM_PROMPT, SYNTHESIS_SYSTEM_PROMPT
from app.text_utils import MAX_TEXT_CHARS, InputError, normalize_text, validate_input


def test_requires_something():
    with pytest.raises(InputError) as e:
        validate_input("  ", None, has_image=False)
    assert e.value.status_code == 422
    assert validate_input(None, None, has_image=True) == (None, None)


def test_too_long():
    with pytest.raises(InputError) as e:
        validate_input("a" * (MAX_TEXT_CHARS + 1), None, False)
    assert e.value.status_code == 413
    assert validate_input("a" * MAX_TEXT_CHARS, None, False)[0]


def test_normalization():
    assert normalize_text("pa​ss﻿word") == "password"
    assert normalize_text("ｈｔｔｐ") == "http"  # fullwidth -> ascii
    # Joiners kept for display (Indic scripts), stripped for matching.
    assert normalize_text("a‍b") == "a‍b"
    assert normalize_text("a‍b", for_matching=True) == "ab"


PROMPTS = (EXTRACTION_SYSTEM_PROMPT, SYNTHESIS_SYSTEM_PROMPT)


def test_prompts_treat_input_as_untrusted():
    for p in PROMPTS:
        assert "UNTRUSTED" in p


def test_prompts_cover_intent_rules():
    text = EXTRACTION_SYSTEM_PROMPT + SYNTHESIS_SYSTEM_PROMPT
    for needle in ["INTENT", "password", "OTP", "UPI", "lottery", "remote access", "sextortion", "gimme the password"]:
        assert needle.lower() in text.lower(), needle
    assert "thin" in SYNTHESIS_SYSTEM_PROMPT


def test_synthesis_prompt_forbids_revealing_internals():
    p = SYNTHESIS_SYSTEM_PROMPT
    assert "Never mention being an AI" in p
    for forbidden in ["as an ai", "language model, i", "i am gemini", "you may mention"]:
        assert forbidden not in p.lower()
