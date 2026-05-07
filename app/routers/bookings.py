from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.auth import get_current_user
from app.db import get_session
from app.models_db import User
from app.schemas import BookingCreate, BookingRead, BookingUpdate
from app import services

router = APIRouter(prefix="/bookings", tags=["bookings"])


@router.post("", response_model=BookingRead, status_code=status.HTTP_201_CREATED)
def create_booking(
    payload: BookingCreate,
    session: Session = Depends(get_session),
    actor: User = Depends(get_current_user),
) -> BookingRead:
    try:
        return services.create_booking(session, payload, actor)
    except services.BadRequestError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=exc.message) from exc


@router.get("", response_model=list[BookingRead])
def list_bookings(
    session: Session = Depends(get_session),
    actor: User = Depends(get_current_user),
) -> list[BookingRead]:
    return services.list_bookings(session, actor)


@router.get("/{booking_id}", response_model=BookingRead)
def get_booking(
    booking_id: str,
    session: Session = Depends(get_session),
    actor: User = Depends(get_current_user),
) -> BookingRead:
    try:
        return services.get_booking(session, booking_id, actor)
    except services.NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    except services.BadRequestError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=exc.message) from exc


@router.put("/{booking_id}", response_model=BookingRead)
def update_booking(
    booking_id: str,
    payload: BookingUpdate,
    session: Session = Depends(get_session),
    actor: User = Depends(get_current_user),
) -> BookingRead:
    try:
        return services.update_booking(session, booking_id, payload, actor)
    except services.NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    except services.BadRequestError as exc:
        status_code = status.HTTP_403_FORBIDDEN if "Employees can only" in exc.message else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code, detail=exc.message) from exc


@router.patch("/{booking_id}/approve", response_model=BookingRead)
def approve_booking(
    booking_id: str,
    session: Session = Depends(get_session),
    actor: User = Depends(get_current_user),
) -> BookingRead:
    try:
        return services.approve_booking(session, booking_id, actor)
    except services.NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    except services.BadRequestError as exc:
        status_code = status.HTTP_403_FORBIDDEN if "Only admins" in exc.message else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code, detail=exc.message) from exc


@router.patch("/{booking_id}/cancel", response_model=BookingRead)
def cancel_booking(
    booking_id: str,
    session: Session = Depends(get_session),
    actor: User = Depends(get_current_user),
) -> BookingRead:
    try:
        return services.cancel_booking(session, booking_id, actor)
    except services.NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    except services.BadRequestError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=exc.message) from exc


@router.delete("/{booking_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_booking(
    booking_id: str,
    session: Session = Depends(get_session),
    actor: User = Depends(get_current_user),
) -> None:
    try:
        services.delete_booking(session, booking_id, actor)
    except services.NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    except services.BadRequestError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=exc.message) from exc
