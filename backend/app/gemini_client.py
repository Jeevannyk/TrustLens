import json
import logging
import os
import time

import google.generativeai as genai
import requests
from google.api_core.exceptions import DeadlineExceeded, ResourceExhausted, ServiceUnavailable

from .prompts import EXTRACTION_SYSTEM_PROMPT, SYNTHESIS_SYSTEM_PROMPT
from .model_output import ModelReport, parse_model_json, validate_extracted, validate_report
from .schemas import DomainCheckResult, ExtractedMessage

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT_SECONDS = 25
MAX_ORIGINAL_TEXT_CHARS = 10_000


class ModelUnavailable(Exception):
    """The model service could not be reached or is out of quota after retries."""


class OutputInvalid(Exception):
    """The model replied, but not with usable JSON even after one repair attempt."""

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
    """Calls the model with bounded retries: transient errors back off on the same key,
    quota errors rotate to the next key. Raises ModelUnavailable if nothing works."""
    keys = _load_keys()
    last_error: Exception | None = None

    for _key_attempt in range(len(keys)):
        for attempt in range(1, max_transient_attempts + 1):
            try:
                model = _model(system_prompt)
                return model.generate_content(
                    content,
                    generation_config={"response_mime_type": "application/json", "temperature": 0.2},
                    request_options={"timeout": REQUEST_TIMEOUT_SECONDS},
                )
            except _TRANSIENT as exc:
                last_error = exc
                logger.warning("model call transient failure (attempt %d): %s", attempt, exc)
                if attempt < max_transient_attempts:
                    time.sleep(2 ** (attempt - 1))  # 1s, 2s
            except _QUOTA_EXCEEDED as exc:
                last_error = exc
                logger.warning("model quota exhausted for current key: %s", exc)
                break  # stop retrying this key, rotate below
        else:
            continue  # transient retries exhausted without a quota error; give up entirely
        if not _rotate_key():
            break  # no more keys left to try

    raise ModelUnavailable(str(last_error)) from last_error


def _generate_validated(system_prompt: str, content: list, validate):
    """Generate, parse and validate. On unusable output, retry ONCE with the error fed back.
    Raises OutputInvalid if still unusable, ModelUnavailable if the service is down."""
    error: Exception | None = None
    raw = ""
    for attempt in range(2):
        request = content
        if attempt == 1:
            request = content + [
                "Your previous reply could not be used (" + type(error).__name__ + "). "
                "Reply again with ONLY one valid JSON object in the exact required shape, "
                "no markdown fences and no commentary."
            ]
        response = _generate(system_prompt, request)
        try:
            raw = response.text  # raises ValueError when the reply was blocked/empty
            return validate(parse_model_json(raw))
        except (ValueError, KeyError, TypeError) as exc:  # pydantic ValidationError is a ValueError
            error = exc
            logger.warning("model output rejected (attempt %d): %s", attempt + 1, exc)
    raise OutputInvalid() from error


def extract_message(text: str | None, image_bytes: bytes | None, image_mime: str | None) -> ExtractedMessage:
    if not text and not image_bytes:
        raise ValueError("Provide message text, a link, or a screenshot")

    parts: list = []
    if text:
        parts.append(text)
    if image_bytes:
        parts.append({"mime_type": image_mime or "image/png", "data": image_bytes})

    extracted = _generate_validated(EXTRACTION_SYSTEM_PROMPT, parts, validate_extracted)
    extracted.extraction_failed = False
    return extracted


def synthesize_report(
    original_text: str | None,
    extracted: ExtractedMessage,
    domain_checks: list[DomainCheckResult],
    language: str,
    minimum_risk_level: str,
) -> ModelReport:
    payload = {
        "original_text": (original_text or "")[:MAX_ORIGINAL_TEXT_CHARS],
        "extracted": extracted.model_dump(),
        "domain_checks": [d.model_dump() for d in domain_checks],
        "minimum_risk_level": minimum_risk_level,
        "target_language": language,
    }
    return _generate_validated(SYNTHESIS_SYSTEM_PROMPT, [json.dumps(payload, ensure_ascii=False)], validate_report)
