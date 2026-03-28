"""
Domain logic for resources and bookings.

Used by JSON API routes and HTML UI routes so behavior stays in one place.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from app import storage

# Returned on PATCH approve when another approved booking overlaps this one (same resource).
BOOKING_CONFLICT_MESSAGE = "Booking conflict detected"
from app.models import (
    BOOKING_STATUS_VALUES,
    Booking,
    BookingCreate,
    BookingUpdate,
    Resource,
    ResourceCreate,
    ResourceUpdate,
)
from app.utils import generate_id


class NotFoundError(Exception):
    """Entity id not found."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class BadRequestError(Exception):
    """Invalid operation (e.g. unknown resource on booking)."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


def _find_index_by_id(items: list[dict], item_id: str) -> int | None:
    for i, item in enumerate(items):
        if item.get("id") == item_id:
            return i
    return None


def resource_exists(resource_id: str) -> bool:
    resources = storage.load_resources()
    return any(r.get("id") == resource_id for r in resources)


def _normalize_booking_dict(row: dict) -> dict:
    """Ensure status is present and valid (legacy JSON may omit it)."""
    d = dict(row)
    s = d.get("status")
    if not s or s not in BOOKING_STATUS_VALUES:
        d["status"] = "pending"
    return d


def _booking_model(row: dict) -> Booking:
    return Booking.model_validate(_normalize_booking_dict(row))


def _parse_booking_datetime(value: str) -> datetime | None:
    """Parse ISO-like start/end strings; None if unparseable."""
    s = (value or "").strip()
    if not s:
        return None
    for candidate in (s, s.replace(" ", "T", 1)):
        try:
            dt = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
            if dt.tzinfo is not None:
                dt = dt.replace(tzinfo=None)
            return dt
        except ValueError:
            continue
    return None


def _intervals_overlap(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> bool:
    """True iff [a_start, a_end) overlaps [b_start, b_end) per strict inequality rule."""
    return a_start < b_end and a_end > b_start


def _approved_booking_conflicts_with(
    other: dict,
    exclude_booking_id: str,
    resource_id: str,
    new_start: datetime,
    new_end: datetime,
) -> bool:
    """other is a raw row; True if other is approved, same resource, not excluded, and overlaps new interval."""
    if str(other.get("id", "")) == exclude_booking_id:
        return False
    norm = _normalize_booking_dict(other)
    if norm.get("status") != "approved":
        return False
    if str(norm.get("resource_id", "")) != resource_id:
        return False
    o_start = _parse_booking_datetime(str(norm.get("start_time", "")))
    o_end = _parse_booking_datetime(str(norm.get("end_time", "")))
    if o_start is None or o_end is None:
        return False
    return _intervals_overlap(o_start, o_end, new_start, new_end)


# --- Resources ---


def create_resource(payload: ResourceCreate) -> Resource:
    resources = storage.load_resources()
    new_id = generate_id()
    record = {"id": new_id, **payload.model_dump()}
    resources.append(record)
    storage.save_resources(resources)
    return Resource.model_validate(record)


def list_resources() -> list[Resource]:
    resources = storage.load_resources()
    return [Resource.model_validate(r) for r in resources]


def get_resource(resource_id: str) -> Resource:
    resources = storage.load_resources()
    idx = _find_index_by_id(resources, resource_id)
    if idx is None:
        raise NotFoundError(f"Resource not found: {resource_id}")
    return Resource.model_validate(resources[idx])


def update_resource(resource_id: str, payload: ResourceUpdate) -> Resource:
    resources = storage.load_resources()
    idx = _find_index_by_id(resources, resource_id)
    if idx is None:
        raise NotFoundError(f"Resource not found: {resource_id}")
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise BadRequestError("No fields to update.")
    current = dict(resources[idx])
    current.update(updates)
    resources[idx] = current
    storage.save_resources(resources)
    return Resource.model_validate(current)


def delete_resource(resource_id: str) -> None:
    resources = storage.load_resources()
    idx = _find_index_by_id(resources, resource_id)
    if idx is None:
        raise NotFoundError(f"Resource not found: {resource_id}")
    resources.pop(idx)
    storage.save_resources(resources)


# --- Bookings ---


def create_booking(payload: BookingCreate) -> Booking:
    if not resource_exists(payload.resource_id):
        raise BadRequestError(f"Unknown resource_id: {payload.resource_id}")
    bookings = storage.load_bookings()
    new_id = generate_id()
    record = {"id": new_id, **payload.model_dump(), "status": "pending"}
    bookings.append(record)
    storage.save_bookings(bookings)
    return _booking_model(record)


def list_bookings() -> list[Booking]:
    bookings = storage.load_bookings()
    return [_booking_model(b) for b in bookings]


def get_booking(booking_id: str) -> Booking:
    bookings = storage.load_bookings()
    idx = _find_index_by_id(bookings, booking_id)
    if idx is None:
        raise NotFoundError(f"Booking not found: {booking_id}")
    return _booking_model(bookings[idx])


def update_booking(booking_id: str, payload: BookingUpdate) -> Booking:
    bookings = storage.load_bookings()
    idx = _find_index_by_id(bookings, booking_id)
    if idx is None:
        raise NotFoundError(f"Booking not found: {booking_id}")
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise BadRequestError("No fields to update.")
    new_rid = updates.get("resource_id")
    if new_rid is not None and not resource_exists(new_rid):
        raise BadRequestError(f"Unknown resource_id: {new_rid}")
    current = _normalize_booking_dict(dict(bookings[idx]))
    current.update(updates)
    bookings[idx] = current
    storage.save_bookings(bookings)
    return _booking_model(current)


def approve_booking(booking_id: str) -> Booking:
    bookings = storage.load_bookings()
    idx = _find_index_by_id(bookings, booking_id)
    if idx is None:
        raise NotFoundError(f"Booking not found: {booking_id}")
    current = _normalize_booking_dict(dict(bookings[idx]))
    rid = str(current.get("resource_id", ""))
    ns = _parse_booking_datetime(str(current.get("start_time", "")))
    ne = _parse_booking_datetime(str(current.get("end_time", "")))
    if ns is not None and ne is not None:
        for row in bookings:
            if _approved_booking_conflicts_with(row, booking_id, rid, ns, ne):
                raise BadRequestError(BOOKING_CONFLICT_MESSAGE)
    current["status"] = "approved"
    bookings[idx] = current
    storage.save_bookings(bookings)
    return _booking_model(current)


def cancel_booking(booking_id: str) -> Booking:
    return _set_booking_status(booking_id, "cancelled")


def _set_booking_status(booking_id: str, status: Literal["approved", "cancelled"]) -> Booking:
    bookings = storage.load_bookings()
    idx = _find_index_by_id(bookings, booking_id)
    if idx is None:
        raise NotFoundError(f"Booking not found: {booking_id}")
    current = _normalize_booking_dict(dict(bookings[idx]))
    current["status"] = status
    bookings[idx] = current
    storage.save_bookings(bookings)
    return _booking_model(current)


def delete_booking(booking_id: str) -> None:
    bookings = storage.load_bookings()
    idx = _find_index_by_id(bookings, booking_id)
    if idx is None:
        raise NotFoundError(f"Booking not found: {booking_id}")
    bookings.pop(idx)
    storage.save_bookings(bookings)
