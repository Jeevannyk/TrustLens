import json
import logging
import os
import re
from urllib.parse import quote

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from . import storage
from .documents import PDF_MIME, merge_text, prepare_document, safe_filename
from .gemini_client import ModelUnavailable
from .pipeline import analyze_message
from .qr import merge_qr_text, scan_image
from .schemas import TrustReport
from .text_utils import InputError, validate_input

load_dotenv()

logger = logging.getLogger(__name__)

MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_VIDEO_BYTES = 25 * 1024 * 1024
_EXT_TO_MIME = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".heic": "image/heic",
    ".heif": "image/heif",
}
ALLOWED_IMAGE_MIMES = set(_EXT_TO_MIME.values())
_VIDEO_EXT_TO_MIME = {
    ".mp4": "video/mp4",
    ".m4v": "video/mp4",
    ".mov": "video/quicktime",
    ".webm": "video/webm",
    ".3gp": "video/3gpp",
}
ALLOWED_VIDEO_MIMES = set(_VIDEO_EXT_TO_MIME.values())
_DOC_EXT_TO_MIME = {
    ".pdf": PDF_MIME,
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".eml": "message/rfc822",
}
ALLOWED_DOC_MIMES = set(_DOC_EXT_TO_MIME.values())
UNSUPPORTED_TYPE_DETAIL = (
    "Unsupported file type. Use an image (PNG, JPEG, WebP, HEIC, HEIF), "
    "a video (MP4, MOV, WebM, 3GP) or a document (PDF, TXT, EML, MD)."
)
_SIZE_LIMITS = {"image": (MAX_IMAGE_BYTES, "Image"), "video": (MAX_VIDEO_BYTES, "Video")}


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


def resolve_video_mime(content_type: str | None, filename: str | None) -> str | None:
    """Like resolve_image_mime, for videos."""
    ctype = (content_type or "").split(";")[0].strip().lower()
    if ctype == "video/x-m4v":  # what some browsers send for .m4v
        ctype = "video/mp4"
    if ctype in ALLOWED_VIDEO_MIMES:
        return ctype
    if ctype in ("", "application/octet-stream"):
        return _VIDEO_EXT_TO_MIME.get(os.path.splitext(filename or "")[1].lower())
    return None


def looks_like_video(mime: str, data: bytes) -> bool:
    """MP4, MOV and 3GP files start with an ISO "ftyp" box; WebM with the EBML header."""
    if mime == "video/webm":
        return data.startswith(b"\x1a\x45\xdf\xa3")
    return data[4:8] == b"ftyp"


def resolve_file_kind(content_type: str | None, filename: str | None) -> tuple[str, str] | None:
    """Return ("image" | "video" | "document", normalized mime) for an allowed upload, or None."""
    image_mime = resolve_image_mime(content_type, filename)
    if image_mime:
        return "image", image_mime
    video_mime = resolve_video_mime(content_type, filename)
    if video_mime:
        return "video", video_mime
    ctype = (content_type or "").split(";")[0].strip().lower()
    ext_mime = _DOC_EXT_TO_MIME.get(os.path.splitext(filename or "")[1].lower())
    if ctype in ("", "application/octet-stream"):
        mime = ext_mime
    elif ctype == "text/x-markdown":
        mime = "text/markdown"
    elif ctype in ALLOWED_DOC_MIMES:
        mime = ctype
        # Browsers send text/plain for many text-like files; trust a .md/.eml extension.
        if ctype == "text/plain" and ext_mime in ("text/markdown", "message/rfc822"):
            mime = ext_mime
    else:
        mime = None
    return ("document", mime) if mime else None


def _content_disposition(disposition: str, filename: str | None) -> str:
    name = filename or "attachment"
    ascii_name = re.sub(r"[^A-Za-z0-9._ -]", "_", name)
    return f"{disposition}; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(name, safe='')}"


def _stored_file(row: dict) -> tuple[bytes, str, str, str | None] | None:
    """(data, kind, mime, name) of the file saved with an analysis; screenshots from
    before file uploads existed count as images."""
    if row["file_bytes"] is not None:
        return row["file_bytes"], row["file_kind"] or "document", row["file_mime"] or "application/octet-stream", row["file_name"]
    if row["screenshot"] is not None:
        return row["screenshot"], "image", row["screenshot_mime"] or "application/octet-stream", row["file_name"]
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

    image_bytes = image_mime = None
    # model_file_bytes: a PDF or video the model reads itself. stored_file_bytes: saved in file_bytes.
    model_file_bytes = stored_file_bytes = None
    qr_payloads: list[str] = []
    file_kind = file_mime = file_name = None
    analysis_text = clean_text
    if file:
        resolved = resolve_file_kind(file.content_type, file.filename)
        if resolved is None:
            return JSONResponse(status_code=415, content={"detail": UNSUPPORTED_TYPE_DETAIL})
        file_kind, file_mime = resolved
        limit, label = _SIZE_LIMITS.get(file_kind, (MAX_FILE_BYTES, "File"))
        data = await file.read(limit + 1)
        if len(data) > limit:
            return JSONResponse(
                status_code=413,
                content={"detail": f"{label} is too large. Maximum size is {limit // 1024 // 1024} MB."},
            )
        file_name = safe_filename(file.filename)
        if file_kind == "image":
            image_bytes, image_mime = data, file_mime
            # The image still goes to the model as well, for logos and "scan to pay" cues.
            qr_payloads = await scan_image(data)
            analysis_text = merge_qr_text(clean_text, qr_payloads)
        elif file_kind == "video":
            if not looks_like_video(file_mime, data):
                return JSONResponse(status_code=415, content={"detail": "This file doesn't look like a valid video."})
            # No QR scan or frame extraction: the model watches and listens to the video itself.
            model_file_bytes = stored_file_bytes = data
        else:
            try:
                document_text = prepare_document(file_mime, data)
            except InputError as exc:
                return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
            analysis_text = merge_text(clean_text, document_text)
            stored_file_bytes = data
            if file_mime == PDF_MIME:
                model_file_bytes = data  # the model reads PDFs itself, as an inline part

    try:
        report = await analyze_message(
            text=analysis_text,
            link=clean_link,
            image_bytes=image_bytes,
            image_mime=image_mime,
            file_bytes=model_file_bytes,
            file_mime=file_mime if model_file_bytes else None,
            qr_payloads=qr_payloads,
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
            file_name=file_name,
            file_mime=file_mime,
            file_kind=file_kind,
            file_bytes=stored_file_bytes,
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
    stored = _stored_file(row)
    return {
        "id": row["id"],
        "created_at": row["created_at"],
        "input_text": row["input_text"],
        "input_link": row["input_link"],
        "language": row["language"],
        "has_screenshot": row["screenshot"] is not None,
        "has_file": stored is not None,
        "file_name": stored[3] if stored else None,
        "file_kind": stored[1] if stored else None,
        "file_mime": stored[2] if stored else None,
        "report": json.loads(row["report_json"]),
    }


@app.get("/history/{analysis_id}/screenshot")
async def history_screenshot(analysis_id: int):
    row = storage.get_analysis(analysis_id)
    if row is None or row["screenshot"] is None:
        return JSONResponse(status_code=404, content={"detail": "no screenshot"})
    return Response(content=row["screenshot"], media_type=row["screenshot_mime"] or "application/octet-stream")


@app.get("/history/{analysis_id}/file")
async def history_file(analysis_id: int):
    row = storage.get_analysis(analysis_id)
    stored = _stored_file(row) if row else None
    if stored is None:
        return JSONResponse(status_code=404, content={"detail": "no file"})
    data, kind, mime, name = stored
    # Plain full response (no Range support): Safari may not play a video served this way.
    disposition = "inline" if kind in ("image", "video") or mime == PDF_MIME else "attachment"
    return Response(
        content=data,
        media_type=mime,
        headers={
            "Content-Disposition": _content_disposition(disposition, name),
            "X-Content-Type-Options": "nosniff",
        },
    )
