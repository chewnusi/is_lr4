"""Shared Jinja2 templates and app directory path for web UI and static files."""

from pathlib import Path

from fastapi.templating import Jinja2Templates

APP_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(APP_DIR / "templates"))
