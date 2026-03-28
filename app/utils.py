"""Small helpers shared across the application."""

import uuid


def generate_id() -> str:
    """Return a new unique string id suitable for JSON-stored entities."""
    return str(uuid.uuid4())
