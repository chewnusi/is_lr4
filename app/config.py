"""Application settings."""

from __future__ import annotations

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "app" / "data"
DEFAULT_SQLITE_PATH = DATA_DIR / "app.db"


class Settings:
    def __init__(self) -> None:
        self.database_url = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_SQLITE_PATH}")
        self.seed_on_start = os.getenv("SEED_ON_START", "true").lower() in {"1", "true", "yes", "on"}
        self.session_secret = os.getenv("SESSION_SECRET", "dev-insecure-session-secret-change-me")
        self.seed_temp_password = os.getenv("SEED_TEMP_PASSWORD", "ChangeMe123!")


settings = Settings()
