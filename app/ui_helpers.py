"""
Server-side helpers for the /ui dashboard (pagination, booking calendar grouping).

Uses the same storage layer as the JSON API; does not alter API behavior.
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any

from app import storage

RESOURCES_PER_PAGE = 5


def _parse_booking_date(start_time: str) -> tuple[str, str]:
    """
    Derive a sortable date key (YYYY-MM-DD) and a human label from start_time.

    Accepts common ISO-like strings; unknown shapes fall back to a late sort key.
    """
    s = (start_time or "").strip()
    if not s:
        return "9999-12-31", "Unknown date"

    candidates = [s, s.replace(" ", "T", 1)]
    for candidate in candidates:
        try:
            normalized = candidate.replace("Z", "+00:00")
            dt = datetime.fromisoformat(normalized)
            if dt.tzinfo is not None:
                dt = dt.replace(tzinfo=None)
            return dt.date().isoformat(), dt.strftime("%B %d, %Y")
        except ValueError:
            continue

    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        key = s[:10]
        return key, key

    return "9999-12-31", "Unknown date"


def _resource_id_to_name() -> dict[str, str]:
    out: dict[str, str] = {}
    for r in storage.load_resources():
        rid = r.get("id")
        if not rid:
            continue
        name = r.get("name")
        out[str(rid)] = name if name else str(rid)
    return out


def paginate_resources(page: int, per_page: int = RESOURCES_PER_PAGE) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Return a page of raw resource dicts plus pagination metadata."""
    resources = list(storage.load_resources())
    total = len(resources)
    total_pages = max(1, math.ceil(total / per_page)) if total else 1
    safe_page = max(1, min(int(page), total_pages))
    start = (safe_page - 1) * per_page
    slice_ = resources[start : start + per_page]
    meta = {
        "page": safe_page,
        "total_pages": total_pages,
        "has_prev": safe_page > 1,
        "has_next": safe_page < total_pages,
        "total": total,
        "per_page": per_page,
    }
    return slice_, meta


def build_booking_calendar_rows() -> list[dict[str, Any]]:
    """
    Group bookings by calendar date (from start_time), sorted by date then start time.

    Each row: { "date_label", "bookings": [ { resource_label, start_time, end_time, user_name, purpose } ] }
    """
    id_to_name = _resource_id_to_name()
    by_key: dict[str, tuple[str, list[dict[str, Any]]]] = {}

    for b in storage.load_bookings():
        start_time = str(b.get("start_time", ""))
        sort_key, date_label = _parse_booking_date(start_time)
        rid = str(b.get("resource_id", ""))
        resource_label = id_to_name.get(rid, rid or "—")

        if sort_key not in by_key:
            by_key[sort_key] = (date_label, [])
        by_key[sort_key][1].append(
            {
                "resource_label": resource_label,
                "resource_id": rid,
                "start_time": start_time,
                "end_time": str(b.get("end_time", "")),
                "user_name": str(b.get("user_name", "")),
                "purpose": str(b.get("purpose", "")),
            }
        )

    rows: list[dict[str, Any]] = []
    for sort_key in sorted(by_key.keys()):
        date_label, items = by_key[sort_key]
        items.sort(key=lambda x: x["start_time"])
        rows.append({"date_label": date_label, "sort_key": sort_key, "bookings": items})

    return rows


def build_ui_context(page: int) -> dict[str, Any]:
    """Context dict for the dashboard template."""
    resources, pagination = paginate_resources(page)
    return {
        "resources": resources,
        "pagination": pagination,
        "booking_days": build_booking_calendar_rows(),
    }
