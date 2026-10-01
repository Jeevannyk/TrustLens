"""Orchestrates one analysis: read -> deterministic checks -> verdict -> risk floors."""
import asyncio
import logging

from . import domain_checks as domain_checks_module
from . import gemini_client
from .messages import SUPPORTED_LANGUAGES
from .risk import apply_floor, compute_floor, ensure_findings, fallback_report
from .schemas import ExtractedMessage, Flag, TrustReport
from .urls import extract_urls

logger = logging.getLogger(__name__)

MODEL_STAGE_TIMEOUT_SECONDS = 75.0


def collect_urls(text: str | None, link: str | None, extracted: ExtractedMessage) -> list[str]:
    """Every URL/domain from the user's text, link, the model's link list and any text
    read from a screenshot, de-duplicated."""
    sources = [text, link, extracted.extracted_text, *extracted.links]
    seen: set[str] = set()
    urls: list[str] = []
    for source in sources:
        for url in extract_urls(source):
            if url.lower() not in seen:
                seen.add(url.lower())
                urls.append(url)
    return urls


async def _in_thread(fn, *args):
    return await asyncio.wait_for(asyncio.to_thread(fn, *args), MODEL_STAGE_TIMEOUT_SECONDS)


async def analyze_message(
    *,
    text: str | None,
    link: str | None,
    image_bytes: bytes | None,
    image_mime: str | None,
    language: str,
) -> TrustReport:
    """Raises gemini_client.ModelUnavailable if the model service is down. Everything
    else (bad model output, slow/failed lookups) degrades to a cautious result."""
    language = language if language in SUPPORTED_LANGUAGES else "en"
    combined = "\n".join(part for part in [text, link] if part) or None

    try:
        extracted = await _in_thread(gemini_client.extract_message, combined, image_bytes, image_mime)
    except gemini_client.OutputInvalid:
        extracted = ExtractedMessage(extraction_failed=True)
    except asyncio.TimeoutError as exc:
        raise gemini_client.ModelUnavailable("extraction timed out") from exc

    urls = collect_urls(text, link, extracted)
    checks = await domain_checks_module.run_domain_checks(urls)
    floor_level, reasons = compute_floor(
        extracted, checks, has_text=bool(combined), has_image=bool(image_bytes)
    )

    try:
        model_report = await _in_thread(
            gemini_client.synthesize_report, combined, extracted, checks, language, floor_level
        )
        report = TrustReport(
            risk_level=model_report.risk_level,
            summary=model_report.summary,
            flags=[Flag(**f.model_dump()) for f in model_report.flags],
            recommended_actions=model_report.recommended_actions,
            findings=model_report.findings,
            language=language,
            extracted=extracted,
            domain_checks=checks,
        )
    except gemini_client.OutputInvalid:
        report = fallback_report(language, extracted, checks)
    except asyncio.TimeoutError as exc:
        raise gemini_client.ModelUnavailable("synthesis timed out") from exc

    report = apply_floor(report, floor_level, reasons)
    return ensure_findings(report)
