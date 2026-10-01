import tempfile
from pathlib import Path

from app import storage

# app.main creates/migrates the database when it is imported, so point it at a throwaway
# file before any test module imports it. The real backend/trustlens.db is never touched.
storage.DB_PATH = Path(tempfile.mkdtemp()) / "test.db"
