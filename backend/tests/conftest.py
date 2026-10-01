import os
import tempfile
from pathlib import Path

import pytest

from app import guards, storage

# app.main creates/migrates the database when it is imported, so point it at a throwaway
# file before any test module imports it. The real backend/trustlens.db is never touched.
storage.DB_PATH = Path(tempfile.mkdtemp()) / "test.db"

# No per-IP limit unless a test turns it on.
os.environ["ANALYZE_RATE_PER_MIN"] = "0"


@pytest.fixture(autouse=True)
def _fresh_guards():
    """Stubbed tests send the same text again and again; they must not hit the cache."""
    guards.cache.clear()
    guards.limiter.clear()
