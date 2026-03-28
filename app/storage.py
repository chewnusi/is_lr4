"""JSON file persistence for resources and bookings."""

import json
from pathlib import Path
from typing import Any

# Resolve paths relative to this package so cwd does not matter.
_DATA_DIR = Path(__file__).resolve().parent / "data"
RESOURCES_FILE = _DATA_DIR / "resources.json"
BOOKINGS_FILE = _DATA_DIR / "bookings.json"


def read_json_array(path: Path) -> list[dict[str, Any]]:
    """Load a JSON file that must contain a list of objects."""
    if not path.exists():
        return []
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in {path}: {e}") from e
    if not isinstance(data, list):
        raise ValueError(f"Expected a JSON array in {path}")
    return data


def write_json_array(path: Path, items: list[dict[str, Any]]) -> None:
    """Atomically write a list of dicts as pretty-printed JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(items, f, indent=2, ensure_ascii=False)
        f.write("\n")
    tmp.replace(path)


def load_resources() -> list[dict[str, Any]]:
    return read_json_array(RESOURCES_FILE)


def save_resources(resources: list[dict[str, Any]]) -> None:
    write_json_array(RESOURCES_FILE, resources)


def load_bookings() -> list[dict[str, Any]]:
    return read_json_array(BOOKINGS_FILE)


def save_bookings(bookings: list[dict[str, Any]]) -> None:
    write_json_array(BOOKINGS_FILE, bookings)
