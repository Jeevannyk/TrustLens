"""Orchestrates one analysis: read -> deterministic checks -> verdict -> risk floors."""
import asyncio
import logging

from . import domain_checks as domain_checks_module
from . import gemini_client
from .messages import SUPPORTED_LANGUAGES
from .risk import apply_floor, compute_floor, ensure_findings, fallback_report
from .schemas import ExtractedMessage, Flag, TrustReport
from .urls import email_domains, extract_urls

logger = logging.getLogger(__name__)

MODEL_STAGE_TIMEOUT_SECONDS = 75.0
# Reading a video (upload, processing, then the model call) takes much longer than an image.
VIDEO_MODEL_STAGE_TIMEOUT_SECONDS = 150.0


def collect_urls(text: str | None, link: str | None, extracted: ExtractedMessage) -> list[str]:
    """Every URL/domain from the user's text, link, the model's link list, any text read
    from a screenshot or PDF and any decoded QR code, plus the sender's email domain,
    de-duplicated."""
    sources = [text, link, extracted.extracted_text, *extracted.links, *extracted.qr_decoded]
    seen: set[str] = set()
    urls: list[str] = []
    for source in sources:
        for url in extract_urls(source):
            if url.lower() not in seen:
                seen.add(url.lower())
                urls.append(url)
    # Sender addresses are skipped by extract_urls, so a spoofed or look-alike sender
    # domain (paypa1.com) would otherwise go unchecked.
    for url in email_domains(extracted.sender):
        if url not in seen:
            seen.add(url)
            urls.append(url)
    return urls


async def _in_thread(fn, *args, timeout: float | None = None):
    return await asyncio.wait_for(asyncio.to_thread(fn, *args), timeout or MODEL_STAGE_TIMEOUT_SECONDS)


async def analyze_message(
    *,
    text: str | None,
    link: str | None,
    image_bytes: bytes | None,
    image_mime: str | None,
    language: str,
    file_bytes: bytes | None = None,
    file_mime: str | None = None,
    qr_payloads: list[str] | None = None,
) -> TrustReport:
    """Raises gemini_client.ModelUnavailable if the model service is down. Everything
    else (bad model output, slow/failed lookups) degrades to a cautious result.
    qr_payloads are QR codes our scanner decoded from the image; their text is already
    part of `text`."""
    language = language if language in SUPPORTED_LANGUAGES else "en"
    combined = "\n".join(part for part in [text, link] if part) or None
    # A PDF goes to the model inline, exactly like a screenshot. A video (also file_bytes)
    # goes through the File API, and only to this reading step: synthesis gets text only.
    attachment_bytes = image_bytes or file_bytes
    attachment_mime = image_mime or file_mime
    is_video = bool(attachment_bytes) and gemini_client.is_video_mime(attachment_mime)

    try:
        extracted = await _in_thread(
            gemini_client.extract_message,
            combined,
            attachment_bytes,
            attachment_mime,
            timeout=VIDEO_MODEL_STAGE_TIMEOUT_SECONDS if is_video else None,
        )
    except gemini_client.OutputInvalid:
        extracted = ExtractedMessage(extraction_failed=True)
    except asyncio.TimeoutError as exc:
        raise gemini_client.ModelUnavailable("extraction timed out") from exc

    # Set by our code, never taken from the model. A decoded QR code is readable content
    # even if the picture itself has nothing else on it.
    extracted.qr_decoded = list(qr_payloads or [])
    if extracted.qr_decoded and extracted.image_readable is False:
        extracted.image_readable = True

    urls = collect_urls(text, link, extracted)
    checks = await domain_checks_module.run_domain_checks(urls)
    floor_level, reasons = compute_floor(
        extracted, checks, has_text=bool(combined), has_image=bool(attachment_bytes)
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
