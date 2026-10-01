"""Protects the model quota: a small in-memory cache of finished reports and a per-IP rate
limit. Both live in one process and are lost on restart, which is fine for a demo backend."""
import hashlib
import json
import math
import os
import threading
import time
from collections import OrderedDict, deque

from .messages import SUPPORTED_LANGUAGES

MAX_CACHE_ENTRIES = 64
RATE_WINDOW_SECONDS = 60.0
_MAX_TRACKED_IPS = 1024


def _env_number(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return default


def cache_ttl_seconds() -> float:
    """CACHE_TTL_SECONDS (default 600); 0 turns the cache off."""
    return _env_number("CACHE_TTL_SECONDS", 600)


def rate_per_minute() -> int:
    """ANALYZE_RATE_PER_MIN (default 6); 0 turns the limit off."""
    return int(_env_number("ANALYZE_RATE_PER_MIN", 6))


def trust_proxy() -> bool:
    return os.environ.get("TRUST_PROXY", "") == "1"


def cache_key(text, link, file_bytes, file_mime, language, model) -> str:
    """Everything that can change the report. The language is normalized the way the
    pipeline does it, so "xx" and "en" share an entry."""
    language = language if language in SUPPORTED_LANGUAGES else "en"
    digest = hashlib.sha256(file_bytes).hexdigest() if file_bytes else ""
    payload = json.dumps([text, link, digest, file_mime or "", language, model], ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class ResultCache:
    """Finished reports by key, at most max_entries (oldest evicted), each for a limited time."""

    def __init__(self, max_entries: int = MAX_CACHE_ENTRIES, clock=time.monotonic):
        self._max = max_entries
        self._clock = clock
        self._items: OrderedDict[str, tuple[float, object]] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str):
        with self._lock:
            entry = self._items.get(key)
            if entry is None:
                return None
            expires, value = entry
            if self._clock() >= expires:
                del self._items[key]
                return None
            self._items.move_to_end(key)
            return value

    def put(self, key: str, value, ttl_seconds: float) -> None:
        with self._lock:
            self._items[key] = (self._clock() + ttl_seconds, value)
            self._items.move_to_end(key)
            while len(self._items) > self._max:
                self._items.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._items.clear()


class RateLimiter:
    """Sliding-window limit per client IP: at most rate_per_minute() requests in any 60 s."""

    def __init__(self, window: float = RATE_WINDOW_SECONDS, clock=time.monotonic):
        self._window = window
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def check(self, ip: str) -> tuple[bool, int]:
        """(allowed, retry_after_seconds). An allowed call is counted."""
        limit = rate_per_minute()
        if limit <= 0:
            return True, 0
        with self._lock:
            now = self._clock()
            if len(self._hits) > _MAX_TRACKED_IPS:
                self._sweep(now)
            hits = self._hits.setdefault(ip, deque())
            while hits and now - hits[0] >= self._window:
                hits.popleft()
            if len(hits) >= limit:
                return False, max(1, math.ceil(self._window - (now - hits[0])))
            hits.append(now)
            return True, 0

    def _sweep(self, now: float) -> None:
        for ip in [ip for ip, hits in self._hits.items() if not hits or now - hits[-1] >= self._window]:
            del self._hits[ip]

    def clear(self) -> None:
        with self._lock:
            self._hits.clear()


cache = ResultCache()
limiter = RateLimiter()
