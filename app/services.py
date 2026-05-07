"""Domain logic for resources, bookings, and users."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import text
from sqlmodel import Session, col, select

from app.models_db import Booking, BookingStatus, BookingStatusHistory, Resource, User, UserRole
from app.schemas import BookingCreate, BookingUpdate, ResourceCreate, ResourceUpdate
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


def _intervals_overlap(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> bool:
    return a_start < b_end and a_end > b_start


def _ensure_resource_exists(session: Session, resource_id: str) -> Resource:
    resource = session.get(Resource, resource_id)
    if resource is None:
        raise BadRequestError(f"Unknown resource_id: {resource_id}")
    return resource


def _ensure_booking_exists(session: Session, booking_id: str) -> Booking:
    booking = session.get(Booking, booking_id)
    if booking is None:
        raise NotFoundError(f"Booking not found: {booking_id}")
    return booking


def _validate_booking_window(start_time: datetime, end_time: datetime) -> None:
    now = datetime.now(UTC).replace(tzinfo=None)
    if start_time >= end_time:
        raise BadRequestError("start_time must be before end_time")
    if start_time < now:
        raise BadRequestError("Bookings in the past are not allowed")


def _assert_no_approved_conflict(
    session: Session,
    resource_id: str,
    start_time: datetime,
    end_time: datetime,
    exclude_booking_id: str | None = None,
) -> None:
    approved_bookings = session.exec(
        select(Booking).where(
            Booking.resource_id == resource_id,
            Booking.status == BookingStatus.approved,
        )
    ).all()
    for existing in approved_bookings:
        if exclude_booking_id and existing.id == exclude_booking_id:
            continue
        if _intervals_overlap(existing.start_time, existing.end_time, start_time, end_time):
            raise BadRequestError("Booking conflict detected")


def _assert_no_active_conflict(
    session: Session,
    resource_id: str,
    start_time: datetime,
    end_time: datetime,
    exclude_booking_id: str | None = None,
) -> None:
    active_bookings = session.exec(
        select(Booking).where(
            Booking.resource_id == resource_id,
            Booking.status != BookingStatus.cancelled,
        )
    ).all()
    for existing in active_bookings:
        if exclude_booking_id and existing.id == exclude_booking_id:
            continue
        if _intervals_overlap(existing.start_time, existing.end_time, start_time, end_time):
            raise BadRequestError("Booking conflict detected")


def _ensure_employee_owns_booking(actor: User, booking: Booking) -> None:
    if actor.role == UserRole.admin:
        return
    if booking.user_id != actor.id:
        raise BadRequestError("Employees can only act on their own bookings")


def _validate_attendees_capacity(resource: Resource, attendees_count: int | None) -> None:
    if attendees_count is None:
        return
    if attendees_count > resource.capacity:
        raise BadRequestError(
            f"attendees_count ({attendees_count}) exceeds resource capacity ({resource.capacity})"
        )


def _record_status_history(
    session: Session,
    booking: Booking,
    new_status: BookingStatus,
    changed_by_user_id: str | None,
) -> None:
    history = BookingStatusHistory(
        id=generate_id(),
        booking_id=booking.id,
        old_status=booking.status,
        new_status=new_status,
        changed_at=datetime.now(UTC).replace(tzinfo=None),
        changed_by_user_id=changed_by_user_id,
    )
    session.add(history)


# --- Resources ---


def create_resource(session: Session, payload: ResourceCreate) -> Resource:
    resource = Resource(id=generate_id(), **payload.model_dump())
    session.add(resource)
    session.commit()
    session.refresh(resource)
    return resource


def list_resources(session: Session) -> list[Resource]:
    return session.exec(select(Resource).order_by(Resource.name)).all()


def get_resource(session: Session, resource_id: str) -> Resource:
    resource = session.get(Resource, resource_id)
    if resource is None:
        raise NotFoundError(f"Resource not found: {resource_id}")
    return resource


def update_resource(session: Session, resource_id: str, payload: ResourceUpdate) -> Resource:
    resource = get_resource(session, resource_id)
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise BadRequestError("No fields to update.")
    for key, value in updates.items():
        setattr(resource, key, value)
    session.add(resource)
    session.commit()
    session.refresh(resource)
    return resource


def delete_resource(session: Session, resource_id: str) -> None:
    resource = get_resource(session, resource_id)
    session.delete(resource)
    session.commit()


# --- Bookings ---


def create_booking(session: Session, payload: BookingCreate, actor: User) -> Booking:
    if actor.role == UserRole.employee and payload.user_id != actor.id:
        raise BadRequestError("Employees can only create bookings for themselves")
    resource = _ensure_resource_exists(session, payload.resource_id)
    _validate_booking_window(payload.start_time, payload.end_time)
    _validate_attendees_capacity(resource, payload.attendees_count)
    _assert_no_active_conflict(session, payload.resource_id, payload.start_time, payload.end_time)
    booking = Booking(
        id=generate_id(),
        status=BookingStatus.pending,
        created_at=datetime.now(UTC).replace(tzinfo=None),
        **payload.model_dump(),
    )
    session.add(booking)
    session.commit()
    session.refresh(booking)
    return booking


def list_bookings(session: Session, actor: User) -> list[Booking]:
    query = select(Booking).order_by(Booking.start_time, Booking.id)
    if actor.role == UserRole.employee:
        query = query.where(Booking.user_id == actor.id)
    return session.exec(query).all()


def get_booking(session: Session, booking_id: str, actor: User) -> Booking:
    booking = _ensure_booking_exists(session, booking_id)
    _ensure_employee_owns_booking(actor, booking)
    return booking


def update_booking(session: Session, booking_id: str, payload: BookingUpdate, actor: User) -> Booking:
    booking = _ensure_booking_exists(session, booking_id)
    _ensure_employee_owns_booking(actor, booking)
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise BadRequestError("No fields to update.")
    next_resource_id = str(updates.get("resource_id", booking.resource_id))
    resource = _ensure_resource_exists(session, next_resource_id)
    new_start = updates.get("start_time", booking.start_time)
    new_end = updates.get("end_time", booking.end_time)
    _validate_booking_window(new_start, new_end)
    next_attendees = updates.get("attendees_count", booking.attendees_count)
    _validate_attendees_capacity(resource, next_attendees)
    _assert_no_active_conflict(
        session,
        updates.get("resource_id", booking.resource_id),
        new_start,
        new_end,
        exclude_booking_id=booking.id,
    )
    for key, value in updates.items():
        setattr(booking, key, value)
    booking.updated_at = datetime.now(UTC).replace(tzinfo=None)
    session.add(booking)
    session.commit()
    session.refresh(booking)
    return booking


def approve_booking(session: Session, booking_id: str, actor: User) -> Booking:
    if actor.role != UserRole.admin:
        raise BadRequestError("Only admins can approve bookings")
    session.exec(text("BEGIN IMMEDIATE"))
    booking = _ensure_booking_exists(session, booking_id)
    if booking.status != BookingStatus.pending:
        raise BadRequestError("Only pending bookings can be approved")
    _assert_no_approved_conflict(session, booking.resource_id, booking.start_time, booking.end_time, booking.id)
    _record_status_history(session, booking, BookingStatus.approved, actor.id)
    booking.status = BookingStatus.approved
    booking.updated_at = datetime.now(UTC).replace(tzinfo=None)
    booking.cancelled_at = None
    session.add(booking)
    session.commit()
    session.refresh(booking)
    return booking


def cancel_booking(session: Session, booking_id: str, actor: User) -> Booking:
    booking = _ensure_booking_exists(session, booking_id)
    _ensure_employee_owns_booking(actor, booking)
    _record_status_history(session, booking, BookingStatus.cancelled, actor.id)
    booking.status = BookingStatus.cancelled
    now = datetime.now(UTC).replace(tzinfo=None)
    booking.cancelled_at = now
    booking.updated_at = now
    session.add(booking)
    session.commit()
    session.refresh(booking)
    return booking


def delete_booking(session: Session, booking_id: str, actor: User) -> None:
    booking = _ensure_booking_exists(session, booking_id)
    _ensure_employee_owns_booking(actor, booking)
    session.delete(booking)
    session.commit()


def list_users(session: Session) -> list[User]:
    return session.exec(select(User).order_by(col(User.role), User.name)).all()


def create_user(session: Session, user_id: str, name: str, role: UserRole, password_hash: str, is_active: bool = True) -> User:
    if session.get(User, user_id):
        raise BadRequestError(f"User already exists: {user_id}")
    user = User(id=user_id, name=name, role=role, password_hash=password_hash, is_active=is_active)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def reset_user_password(session: Session, user_id: str, password_hash: str) -> User:
    user = session.get(User, user_id)
    if user is None:
        raise NotFoundError(f"User not found: {user_id}")
    user.password_hash = password_hash
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def set_user_active(session: Session, user_id: str, is_active: bool) -> User:
    user = session.get(User, user_id)
    if user is None:
        raise NotFoundError(f"User not found: {user_id}")
    user.is_active = is_active
    session.add(user)
    session.commit()
    session.refresh(user)
    return user
