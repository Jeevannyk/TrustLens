import json
import os
import time

import google.generativeai as genai
import requests
from google.api_core.exceptions import DeadlineExceeded, ResourceExhausted, ServiceUnavailable

from .prompts import EXTRACTION_SYSTEM_PROMPT, SYNTHESIS_SYSTEM_PROMPT
from .schemas import DomainCheckResult, ExtractedMessage, TrustReport

# 503/timeout: transient, worth retrying the SAME key with backoff.
_TRANSIENT = (ServiceUnavailable, DeadlineExceeded, TimeoutError, requests.exceptions.Timeout)
# 429: this key's quota (per-minute or per-day) is exhausted — retrying the same key
# won't help within a demo timeframe, so rotate to the next configured key instead.
_QUOTA_EXCEEDED = (ResourceExhausted,)

_api_keys: list[str] = []
_key_index = 0
_configured_key: str | None = None


def _load_keys() -> list[str]:
    global _api_keys
    if not _api_keys:
        # GEMINI_API_KEYS: comma-separated, for quota-rotation across multiple keys
        # (e.g. one per teammate, or multiple of your own projects). Falls back to
        # the single GEMINI_API_KEY var if that's all you've set up.
        raw = os.environ.get("GEMINI_API_KEYS") or os.environ.get("GEMINI_API_KEY", "")
        keys = [k.strip() for k in raw.split(",") if k.strip()]
        if not keys:
            raise RuntimeError("GEMINI_API_KEY (or GEMINI_API_KEYS) is not set (check backend/.env)")
        _api_keys = keys
    return _api_keys


def _configure_current_key() -> None:
    global _configured_key
    keys = _load_keys()
    key = keys[_key_index % len(keys)]
    if _configured_key != key:
        # transport="rest" avoids the default gRPC transport, which hangs
        # indefinitely (no clear error) on some networks/firewalls that allow
        # plain HTTPS but interfere with HTTP/2+gRPC.
        genai.configure(api_key=key, transport="rest")
        _configured_key = key


def _rotate_key() -> bool:
    """Advances to the next key. Returns False if we've cycled through all of them."""
    global _key_index
    keys = _load_keys()
    _key_index += 1
    return _key_index < len(keys)


def _model(system_prompt: str) -> genai.GenerativeModel:
    _configure_current_key()
    model_name = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")
    return genai.GenerativeModel(model_name=model_name, system_instruction=system_prompt)


def _generate(system_prompt: str, content, max_transient_attempts: int = 3):
    keys = _load_keys()
    last_error: Exception | None = None

    for _key_attempt in range(len(keys)):
        for attempt in range(1, max_transient_attempts + 1):
            try:
                model = _model(system_prompt)
                return model.generate_content(
                    content,
                    generation_config={"response_mime_type": "application/json"},
                    request_options={"timeout": 30},
                )
            except _TRANSIENT as exc:
                last_error = exc
                if attempt < max_transient_attempts:
                    time.sleep(2**attempt)  # 2s, 4s, ...
            except _QUOTA_EXCEEDED as exc:
                last_error = exc
                break  # stop retrying this key, rotate below
        else:
            continue  # transient retries exhausted without a quota error; give up entirely
        if not _rotate_key():
            break  # no more keys left to try

    raise last_error


def _parse_json(raw_text: str) -> dict:
    text = raw_text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    return json.loads(text.strip())


def extract_message(text: str | None, image_bytes: bytes | None, image_mime: str | None) -> ExtractedMessage:
    if not text and not image_bytes:
        raise ValueError("Provide message text, a link, or a screenshot")

    parts: list = []
    if text:
        parts.append(text)
    if image_bytes:
        parts.append({"mime_type": image_mime or "image/png", "data": image_bytes})

    response = _generate(EXTRACTION_SYSTEM_PROMPT, parts)
    data = _parse_json(response.text)
    return ExtractedMessage(**data)


def synthesize_report(
    extracted: ExtractedMessage,
    domain_checks: list[DomainCheckResult],
    language: str,
) -> TrustReport:
    payload = {
        "extracted": extracted.model_dump(),
        "domain_checks": [d.model_dump() for d in domain_checks],
        "target_language": language,
    }
    response = _generate(SYNTHESIS_SYSTEM_PROMPT, json.dumps(payload))
    data = _parse_json(response.text)
    return TrustReport(
        risk_level=data["risk_level"],
        summary=data["summary"],
        flags=data.get("flags", []),
        recommended_actions=data.get("recommended_actions", []),
        language=language,
        extracted=extracted,
        domain_checks=domain_checks,
    )
