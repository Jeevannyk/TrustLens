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
# Reading a video takes far longer than an image. pipeline.VIDEO_MODEL_STAGE_TIMEOUT_SECONDS
# caps the whole video extraction (upload, processing and model call).
VIDEO_REQUEST_TIMEOUT_SECONDS = 90
VIDEO_UPLOAD_TIMEOUT_SECONDS = 60  # per upload request (connect / wait for a reply)
VIDEO_PROCESSING_TIMEOUT_SECONDS = 60  # from upload until the File API says the video is ready
VIDEO_POLL_SECONDS = 2
_UPLOAD_URL = "https://generativelanguage.googleapis.com/upload/v1beta/files"
MAX_ORIGINAL_TEXT_CHARS = 10_000
# The Gemini docs list QuickTime as "video/mov"; browsers and our storage use video/quicktime.
_MODEL_VIDEO_MIMES = {"video/quicktime": "video/mov"}


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


def is_video_mime(mime: str | None) -> bool:
    return (mime or "").startswith("video/")


def _delete_quietly(name: str) -> None:
    try:
        genai.delete_file(name)
    except Exception as exc:  # cleanup must not hide the real outcome; the service expires files after 48 h
        logger.warning("could not delete uploaded video %s: %s: %s", name, type(exc).__name__, exc)


def _check_upload(response: requests.Response) -> None:
    """Maps a failed upload request onto the errors _generate handles."""
    if response.ok:
        return
    status = response.status_code
    if status == 429:
        raise ResourceExhausted("video upload: quota exceeded")
    if status >= 500:
        raise ServiceUnavailable(f"video upload failed (HTTP {status})")
    raise ModelUnavailable(f"video upload failed (HTTP {status}): {response.text[:300]}")


def _upload_video(data: bytes, mime: str):
    """Uploads a video to the File API under the configured key and waits until it is ready.
    Raises OutputInvalid if the service could not process it (a broken or unsupported video,
    so asking again will not help) and ModelUnavailable if processing takes too long. The
    upload is deleted again if it never becomes usable."""
    # Not genai.upload_file: its older upload client sends the key as a URL parameter, which
    # the service rejects for newer key formats ("API key not valid"). This is the documented
    # resumable upload, with the key in a header (it never appears in a URL or error text).
    _configure_current_key()
    start = requests.post(
        _UPLOAD_URL,
        headers={
            "x-goog-api-key": _configured_key,
            "X-Goog-Upload-Protocol": "resumable",
            "X-Goog-Upload-Command": "start",
            "X-Goog-Upload-Header-Content-Length": str(len(data)),
            "X-Goog-Upload-Header-Content-Type": _MODEL_VIDEO_MIMES.get(mime, mime),
        },
        json={"file": {}},
        timeout=VIDEO_UPLOAD_TIMEOUT_SECONDS,
    )
    _check_upload(start)
    done = requests.post(
        start.headers["X-Goog-Upload-URL"],
        headers={"X-Goog-Upload-Offset": "0", "X-Goog-Upload-Command": "upload, finalize"},
        data=data,
        timeout=VIDEO_UPLOAD_TIMEOUT_SECONDS,
    )
    _check_upload(done)
    name = done.json()["file"]["name"]
    try:
        deadline = time.monotonic() + VIDEO_PROCESSING_TIMEOUT_SECONDS
        uploaded = genai.get_file(name)
        while uploaded.state.name == "PROCESSING":
            if time.monotonic() >= deadline:
                raise ModelUnavailable("video processing timed out")
            time.sleep(VIDEO_POLL_SECONDS)
            uploaded = genai.get_file(name)
        if uploaded.state.name != "ACTIVE":
            logger.warning("uploaded video could not be processed: %s", uploaded.state.name)
            raise OutputInvalid()
    except BaseException:
        _delete_quietly(name)
        raise
    return uploaded


class _Video:
    """A video for the extraction call, sent through the File API (too big to send inline).
    An uploaded file belongs to the project of the API key that uploaded it, so _generate
    deletes it before moving to another key and part() then uploads a copy under that key.
    Transient retries and the repair attempt on the same key reuse the upload."""

    def __init__(self, data: bytes, mime: str):
        self.data = data
        self.mime = mime
        self._file = None

    def part(self):
        if self._file is None:
            self._file = _upload_video(self.data, self.mime)
        return self._file

    def delete(self) -> None:
        if self._file is not None:
            _delete_quietly(self._file.name)
            self._file = None


def _generate(system_prompt: str, content, max_transient_attempts: int = 3, video: _Video | None = None):
    """Calls the model with bounded retries: transient errors back off on the same key,
    quota errors rotate to the next key. Raises ModelUnavailable if nothing works.
    A video goes first in the request, uploaded under the key being tried."""
    keys = _load_keys()
    last_error: Exception | None = None
    timeout = VIDEO_REQUEST_TIMEOUT_SECONDS if video else REQUEST_TIMEOUT_SECONDS

    for _key_attempt in range(len(keys)):
        for attempt in range(1, max_transient_attempts + 1):
            try:
                model = _model(system_prompt)
                request = [video.part(), *content] if video else content
                return model.generate_content(
                    request,
                    generation_config={"response_mime_type": "application/json", "temperature": 0.2},
                    request_options={"timeout": timeout},
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
        if video:
            video.delete()  # the next key cannot use this key's upload
        if not _rotate_key():
            break  # no more keys left to try

    raise ModelUnavailable(str(last_error)) from last_error


def _generate_validated(system_prompt: str, content: list, validate, video: _Video | None = None):
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
        response = _generate(system_prompt, request, video=video)
        try:
            raw = response.text  # raises ValueError when the reply was blocked/empty
            return validate(parse_model_json(raw))
        except (ValueError, KeyError, TypeError) as exc:  # pydantic ValidationError is a ValueError
            error = exc
            logger.warning("model output rejected (attempt %d): %s", attempt + 1, exc)
    raise OutputInvalid() from error


def extract_message(text: str | None, image_bytes: bytes | None, image_mime: str | None) -> ExtractedMessage:
    """image_bytes is the attachment the model reads itself: a screenshot or PDF (sent
    inline) or a video (sent through the File API and always deleted afterwards)."""
    if not text and not image_bytes:
        raise ValueError("Provide message text, a link, or a screenshot")

    parts: list = []
    if text:
        parts.append(text)
    video = None
    if image_bytes and is_video_mime(image_mime):
        video = _Video(image_bytes, image_mime)
    elif image_bytes:
        parts.append({"mime_type": image_mime or "image/png", "data": image_bytes})

    try:
        extracted = _generate_validated(EXTRACTION_SYSTEM_PROMPT, parts, validate_extracted, video=video)
    finally:
        if video:
            video.delete()
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
