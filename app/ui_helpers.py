"""Server-side helpers for dashboard/calendar pages."""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any

from sqlmodel import Session

from app import services
from app.models_db import BookingStatus, User

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


def _resource_id_to_name(session: Session) -> dict[str, str]:
    out: dict[str, str] = {}
    for r in services.list_resources(session):
        out[r.id] = r.name
    return out


def paginate_resources(session: Session, page: int, per_page: int = RESOURCES_PER_PAGE) -> tuple[list[Any], dict[str, Any]]:
    resources = list(services.list_resources(session))
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


def build_booking_calendar_rows(
    session: Session,
    actor: User,
    status_filter: str | None = None,
    type_filter: str | None = None,
    date_filter: str | None = None,
) -> list[dict[str, Any]]:
    id_to_name = _resource_id_to_name(session)
    resources = {r.id: r for r in services.list_resources(session)}
    by_key: dict[str, tuple[str, list[dict[str, Any]]]] = {}

    for b in services.list_bookings(session, actor):
        start_time = b.start_time.isoformat(timespec="minutes")
        sort_key, date_label = _parse_booking_date(start_time)
        if date_filter and sort_key != date_filter:
            continue
        rid = b.resource_id
        resource_label = id_to_name.get(rid, rid or "—")
        resource = resources.get(rid)
        if type_filter and resource and resource.type != type_filter:
            continue

        if sort_key not in by_key:
            by_key[sort_key] = (date_label, [])
        status = b.status.value
        if status_filter and status_filter != status:
            continue
        by_key[sort_key][1].append(
            {
                "resource_label": resource_label,
                "resource_id": rid,
                "start_time": start_time,
                "end_time": b.end_time.isoformat(timespec="minutes"),
                "user_name": b.user_id,
                "purpose": b.purpose,
                "status": status,
            }
        )

    rows: list[dict[str, Any]] = []
    for sort_key in sorted(by_key.keys()):
        date_label, items = by_key[sort_key]
        items.sort(key=lambda x: x["start_time"])
        rows.append({"date_label": date_label, "sort_key": sort_key, "bookings": items})

    return rows


def build_ui_context(page: int) -> dict[str, Any]:
    raise NotImplementedError("Use explicit helpers in routes.")
    return {
        "resources": resources,
        "pagination": pagination,
        "booking_days": build_booking_calendar_rows(),
    }
