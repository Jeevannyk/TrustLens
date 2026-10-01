import asyncio
import json
from urllib.parse import urlparse

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from . import storage
from .checks.domain_age import get_domain_age_days
from .checks.lookalike import check_lookalike
from .checks.safe_browsing import check_safe_browsing
from .gemini_client import extract_message, synthesize_report
from .schemas import DomainCheckResult, TrustReport

load_dotenv()

app = FastAPI(title="TrustLens API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten before any real deploy; fine for hackathon demo
    allow_methods=["*"],
    allow_headers=["*"],
)

storage.init_db()


def _domain_of(url: str) -> str:
    parsed = urlparse(url if "//" in url else f"//{url}")
    return (parsed.hostname or url).lower()


async def _run_domain_checks(urls: list[str]) -> list[DomainCheckResult]:
    if not urls:
        return []
    domains = sorted({_domain_of(u) for u in urls})
    async with httpx.AsyncClient() as client:
        age_results = await asyncio.gather(*(get_domain_age_days(d, client) for d in domains))
        sb_results = await check_safe_browsing(urls, client)

    checks: list[DomainCheckResult] = []
    for domain, (age_days, error) in zip(domains, age_results):
        brand, distance = check_lookalike(domain)
        matching_url = next((u for u in urls if _domain_of(u) == domain), None)
        sb_hit, sb_type = sb_results.get(matching_url, (False, None)) if matching_url else (False, None)
        checks.append(
            DomainCheckResult(
                domain=domain,
                age_days=age_days,
                is_new_domain=age_days is not None and age_days < 30,
                lookalike_of=brand,
                lookalike_distance=distance,
                safe_browsing_hit=sb_hit,
                safe_browsing_threat_type=sb_type,
                error=error,
            )
        )
    return checks


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/analyze", response_model=TrustReport)
async def analyze(
    text: str | None = Form(None),
    link: str | None = Form(None),
    language: str = Form("en"),
    file: UploadFile | None = File(None),
) -> TrustReport:
    combined_text = "\n".join(part for part in [text, link] if part) or None
    image_bytes = await file.read() if file else None
    image_mime = file.content_type if file else None

    try:
        extracted = extract_message(combined_text, image_bytes, image_mime)

        all_links = list(dict.fromkeys(extracted.links + ([link] if link else [])))
        domain_checks = await _run_domain_checks(all_links)

        report = synthesize_report(extracted, domain_checks, language)
        storage.save_analysis(
            input_text=text,
            input_link=link,
            screenshot_bytes=image_bytes,
            screenshot_mime=image_mime,
            language=language,
            risk_level=report.risk_level,
            report_json=report.model_dump_json(),
        )
        return report
    except Exception as exc:
        # Caught here (not via @app.exception_handler(Exception)) on purpose: Starlette
        # routes that handler to ServerErrorMiddleware, which sits *outside*
        # CORSMiddleware, so its responses never get CORS headers attached. Returning a
        # normal JSONResponse from inside the route flows through CORSMiddleware like
        # any other response.
        return JSONResponse(status_code=500, content={"detail": f"{type(exc).__name__}: {exc}"})


@app.get("/history")
async def history(limit: int = 50) -> list[dict]:
    return storage.list_analyses(limit=limit)


@app.get("/history/{analysis_id}")
async def history_item(analysis_id: int):
    row = storage.get_analysis(analysis_id)
    if row is None:
        return JSONResponse(status_code=404, content={"detail": "not found"})
    return {
        "id": row["id"],
        "created_at": row["created_at"],
        "input_text": row["input_text"],
        "input_link": row["input_link"],
        "language": row["language"],
        "has_screenshot": row["screenshot"] is not None,
        "report": json.loads(row["report_json"]),
    }


@app.get("/history/{analysis_id}/screenshot")
async def history_screenshot(analysis_id: int):
    row = storage.get_analysis(analysis_id)
    if row is None or row["screenshot"] is None:
        return JSONResponse(status_code=404, content={"detail": "no screenshot"})
    return Response(content=row["screenshot"], media_type=row["screenshot_mime"] or "application/octet-stream")
