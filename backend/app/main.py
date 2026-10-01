import json
import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from . import storage
from .gemini_client import ModelUnavailable
from .pipeline import analyze_message
from .schemas import TrustReport
from .text_utils import InputError, validate_input

load_dotenv()

logger = logging.getLogger(__name__)

MAX_IMAGE_BYTES = 8 * 1024 * 1024
_EXT_TO_MIME = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".heic": "image/heic",
    ".heif": "image/heif",
}
ALLOWED_IMAGE_MIMES = set(_EXT_TO_MIME.values())


def resolve_image_mime(content_type: str | None, filename: str | None) -> str | None:
    """Return a normalized allowed mime type, or None. Falls back to the file
    extension when the client sent no useful content type."""
    ctype = (content_type or "").split(";")[0].strip().lower()
    if ctype == "image/jpg":
        ctype = "image/jpeg"
    if ctype in ALLOWED_IMAGE_MIMES:
        return ctype
    if ctype in ("", "application/octet-stream"):
        return _EXT_TO_MIME.get(os.path.splitext(filename or "")[1].lower())
    return None

app = FastAPI(title="TrustLens API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten before any real deploy; fine for hackathon demo
    allow_methods=["*"],
    allow_headers=["*"],
)

storage.init_db()


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
    try:
        clean_text, clean_link = validate_input(text, link, has_image=file is not None)
    except InputError as exc:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    image_bytes = None
    image_mime = None
    if file:
        image_mime = resolve_image_mime(file.content_type, file.filename)
        if image_mime is None:
            return JSONResponse(
                status_code=415,
                content={"detail": "Unsupported image type. Use PNG, JPEG, WebP, HEIC or HEIF."},
            )
        image_bytes = await file.read(MAX_IMAGE_BYTES + 1)
        if len(image_bytes) > MAX_IMAGE_BYTES:
            return JSONResponse(
                status_code=413,
                content={"detail": f"Image is too large. Maximum size is {MAX_IMAGE_BYTES // 1024 // 1024} MB."},
            )

    try:
        report = await analyze_message(
            text=clean_text,
            link=clean_link,
            image_bytes=image_bytes,
            image_mime=image_mime,
            language=language,
        )
    except ModelUnavailable:
        logger.exception("analysis service unavailable")
        return JSONResponse(
            status_code=503,
            content={"detail": "The analysis service is busy right now. Please try again in a moment."},
        )
    except Exception:
        # Caught here (not via @app.exception_handler(Exception)) on purpose: Starlette
        # routes that handler to ServerErrorMiddleware, which sits *outside*
        # CORSMiddleware, so its responses never get CORS headers attached. Returning a
        # normal JSONResponse from inside the route flows through CORSMiddleware like
        # any other response.
        logger.exception("analyze failed")
        return JSONResponse(
            status_code=500,
            content={"detail": "Analysis failed on the server. Please try again."},
        )

    try:
        storage.save_analysis(
            input_text=clean_text,
            input_link=clean_link,
            screenshot_bytes=image_bytes,
            screenshot_mime=image_mime,
            language=report.language,
            risk_level=report.risk_level,
            report_json=report.model_dump_json(),
        )
    except Exception:
        logger.exception("could not save analysis; returning it anyway")
    return report


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
