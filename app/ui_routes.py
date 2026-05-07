"""HTML UI routes."""

from __future__ import annotations

from datetime import datetime
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from pydantic import ValidationError
from sqlmodel import Session

from app.db import get_session
from app.models_db import User
from app.schemas import BookingCreate, BookingUpdate, ResourceCreate, ResourceUpdate
from app.auth import get_current_user, require_admin
from app import services
from app.template_env import templates
from app.ui_helpers import build_booking_calendar_rows, paginate_resources

router = APIRouter(tags=["ui"])

FLASH_OK = "ok"
FLASH_ERR = "error"


def _flash_context(request: Request) -> dict:
    return {
        "flash_notice": request.query_params.get("notice"),
        "flash_message": request.query_params.get("msg"),
    }


def _redirect_path(path: str, notice: str, message: str, **params: str) -> RedirectResponse:
    query = {"notice": notice, "msg": message, **params}
    return RedirectResponse(f"{path}?{urlencode(query)}", status_code=status.HTTP_303_SEE_OTHER)


def _base_context(request: Request, actor: User) -> dict:
    return {"current_user": actor, **_flash_context(request)}


def _parse_dt_local(value: str) -> datetime:
    normalized = value.strip().replace(" ", "T")
    if len(normalized) == 16:
        normalized += ":00"
    return datetime.fromisoformat(normalized)


@router.get("/ui", response_class=Response)
def ui_root() -> RedirectResponse:
    return RedirectResponse("/ui/dashboard", status_code=status.HTTP_302_FOUND)


@router.get("/ui/dashboard", response_class=Response)
def ui_dashboard(
    request: Request,
    page: int = 1,
    status_filter: str | None = Query(default=None),
    resource_type: str | None = Query(default=None),
    date: str | None = Query(default=None),
    session: Session = Depends(get_session),
    actor: User = Depends(get_current_user),
) -> Response:
    if page < 1:
        page = 1
    resources_slice, pagination = paginate_resources(session, page)
    calendar = build_booking_calendar_rows(session, actor, status_filter=status_filter, type_filter=resource_type, date_filter=date)
    ctx = {
        "resources": resources_slice,
        "pagination": pagination,
        "booking_days": calendar,
        "resource_types": sorted({r.type for r in services.list_resources(session)}),
        "filters": {"status": status_filter or "", "resource_type": resource_type or "", "date": date or ""},
        **_base_context(request, actor),
    }
    return templates.TemplateResponse(
        request=request,
        name="ui_overview.html",
        context=ctx,
    )


@router.get("/ui/resources", response_class=Response)
def ui_resources_list(
    request: Request,
    page: int = 1,
    session: Session = Depends(get_session),
    actor: User = Depends(get_current_user),
) -> Response:
    resources_slice, pagination = paginate_resources(session, max(1, page))
    return templates.TemplateResponse(
        request=request,
        name="ui_resources.html",
        context={"resources": resources_slice, "pagination": pagination, **_base_context(request, actor)},
    )


@router.post("/ui/resources")
def ui_resources_create(
    _request: Request,
    name: str = Form(),
    resource_type: str = Form(),
    location: str = Form(),
    capacity: int = Form(),
    is_active: str = Form(default="true"),
    page: int = Form(default=1),
    session: Session = Depends(get_session),
    actor: User = Depends(get_current_user),
) -> RedirectResponse:
    try:
        require_admin(actor)
    except HTTPException as exc:
        return _redirect_path(f"/ui/resources?page={max(1,page)}", FLASH_ERR, exc.detail, user_id=actor.id)
    try:
        payload = ResourceCreate(
            name=name.strip(),
            type=resource_type.strip(),
            location=location.strip(),
            capacity=capacity,
            is_active=is_active.lower() in ("true", "1", "on", "yes"),
        )
    except ValidationError as exc:
        return _redirect_path(f"/ui/resources?page={max(1,page)}", FLASH_ERR, str(exc.errors()[0]["msg"]), user_id=actor.id)
    services.create_resource(session, payload)
    return _redirect_path(f"/ui/resources?page={max(1,page)}", FLASH_OK, "Resource created.", user_id=actor.id)


@router.get("/ui/resources/{resource_id}/edit", response_class=Response)
def ui_resource_edit_form(
    request: Request,
    resource_id: str,
    session: Session = Depends(get_session),
    actor: User = Depends(get_current_user),
) -> Response:
    try:
        resource = services.get_resource(session, resource_id)
    except services.NotFoundError:
        raise HTTPException(status_code=404, detail="Resource not found")
    ctx = {"resource": resource.model_dump(), **_base_context(request, actor)}
    return templates.TemplateResponse(
        request=request,
        name="ui_resource_edit.html",
        context=ctx,
    )


@router.post("/ui/resources/{resource_id}/edit")
def ui_resource_edit_submit(
    _request: Request,
    resource_id: str,
    name: str = Form(),
    resource_type: str = Form(),
    location: str = Form(),
    capacity: int = Form(),
    is_active: str = Form(default="true"),
    session: Session = Depends(get_session),
    actor: User = Depends(get_current_user),
) -> RedirectResponse:
    try:
        require_admin(actor)
    except HTTPException as exc:
        return _redirect_path("/ui/resources", FLASH_ERR, exc.detail, user_id=actor.id)
    try:
        payload = ResourceUpdate(
            name=name.strip(),
            type=resource_type.strip(),
            location=location.strip(),
            capacity=capacity,
            is_active=is_active.lower() in ("true", "1", "on", "yes"),
        )
    except ValidationError:
        return _redirect_path(
            f"/ui/resources/{resource_id}/edit",
            FLASH_ERR,
            "Could not update: invalid field values.",
        )
    try:
        services.update_resource(session, resource_id, payload)
    except services.NotFoundError:
        return _redirect_path("/ui/resources", FLASH_ERR, "Resource not found.")
    except services.BadRequestError as e:
        return _redirect_path(
            f"/ui/resources/{resource_id}/edit",
            FLASH_ERR,
            e.message,
        )
    return _redirect_path("/ui/resources", FLASH_OK, "Resource updated.", user_id=actor.id)


@router.post("/ui/resources/{resource_id}/delete")
def ui_resource_delete(
    _request: Request,
    resource_id: str,
    page: int = Form(default=1),
    session: Session = Depends(get_session),
    actor: User = Depends(get_current_user),
) -> RedirectResponse:
    try:
        require_admin(actor)
    except HTTPException as exc:
        return _redirect_path(f"/ui/resources?page={max(1,page)}", FLASH_ERR, exc.detail, user_id=actor.id)
    try:
        services.delete_resource(session, resource_id)
    except services.NotFoundError:
        return _redirect_path(
            f"/ui/resources?page={max(1, page)}",
            FLASH_ERR,
            "Resource not found.",
        )
    return _redirect_path(
        f"/ui/resources?page={max(1, page)}",
        FLASH_OK,
        "Resource deleted.",
        user_id=actor.id,
    )


@router.get("/ui/bookings", response_class=Response)
def ui_bookings_list(
    request: Request,
    status_filter: str | None = Query(default=None),
    resource_type: str | None = Query(default=None),
    date: str | None = Query(default=None),
    session: Session = Depends(get_session),
    actor: User = Depends(get_current_user),
) -> Response:
    bookings = services.list_bookings(session, actor)
    # Stable display order
    bookings_sorted = sorted(bookings, key=lambda b: (b.start_time, b.id))
    resource_options = services.list_resources(session)
    resource_name_by_id = {r.id: r.name for r in resource_options}
    if status_filter:
        bookings_sorted = [b for b in bookings_sorted if b.status.value == status_filter]
    if resource_type:
        resource_type_by_id = {r.id: r.type for r in resource_options}
        bookings_sorted = [b for b in bookings_sorted if resource_type_by_id.get(b.resource_id) == resource_type]
    if date:
        bookings_sorted = [b for b in bookings_sorted if b.start_time.date().isoformat() == date]
    ctx = {
        "bookings": bookings_sorted,
        "resource_options": resource_options,
        "resource_name_by_id": resource_name_by_id,
        "resource_types": sorted({r.type for r in resource_options}),
        "filters": {"status": status_filter or "", "resource_type": resource_type or "", "date": date or ""},
        **_base_context(request, actor),
    }
    return templates.TemplateResponse(
        request=request,
        name="ui_bookings.html",
        context=ctx,
    )


@router.post("/ui/bookings")
def ui_bookings_create(
    _request: Request,
    resource_id: str = Form(),
    start_time: str = Form(...),
    end_time: str = Form(...),
    purpose: str = Form(),
    user_id: str = Form(...),
    session: Session = Depends(get_session),
    actor: User = Depends(get_current_user),
) -> RedirectResponse:
    try:
        payload = BookingCreate(
            resource_id=resource_id.strip(),
            user_id=user_id.strip(),
            start_time=_parse_dt_local(start_time),
            end_time=_parse_dt_local(end_time),
            purpose=purpose.strip(),
        )
    except ValidationError:
        return _redirect_path("/ui/bookings", FLASH_ERR, "Could not create booking: fill all fields correctly.", user_id=actor.id)
    except ValueError:
        return _redirect_path("/ui/bookings", FLASH_ERR, "Invalid datetime format.", user_id=actor.id)
    try:
        services.create_booking(session, payload, actor)
    except services.BadRequestError as e:
        return _redirect_path("/ui/bookings", FLASH_ERR, e.message, user_id=actor.id)
    return _redirect_path("/ui/bookings", FLASH_OK, "Booking created.", user_id=actor.id)


@router.get("/ui/bookings/{booking_id}/edit", response_class=Response)
def ui_booking_edit_form(
    request: Request,
    booking_id: str,
    session: Session = Depends(get_session),
    actor: User = Depends(get_current_user),
) -> Response:
    try:
        booking = services.get_booking(session, booking_id, actor)
    except services.NotFoundError:
        raise HTTPException(status_code=404, detail="Booking not found")
    except services.BadRequestError as exc:
        raise HTTPException(status_code=403, detail=exc.message)
    resource_options = services.list_resources(session)
    ctx = {
        "booking": booking.model_dump(),
        "resource_options": resource_options,
        **_base_context(request, actor),
    }
    return templates.TemplateResponse(
        request=request,
        name="ui_booking_edit.html",
        context=ctx,
    )


@router.post("/ui/bookings/{booking_id}/edit")
def ui_booking_edit_submit(
    _request: Request,
    booking_id: str,
    resource_id: str = Form(),
    start_time: str = Form(),
    end_time: str = Form(),
    purpose: str = Form(),
    session: Session = Depends(get_session),
    actor: User = Depends(get_current_user),
) -> RedirectResponse:
    try:
        payload = BookingUpdate(
            resource_id=resource_id.strip(),
            start_time=_parse_dt_local(start_time),
            end_time=_parse_dt_local(end_time),
            purpose=purpose.strip(),
        )
    except ValidationError:
        return _redirect_path(
            f"/ui/bookings/{booking_id}/edit",
            FLASH_ERR,
            "Could not update: invalid field values.",
            user_id=actor.id,
        )
    except ValueError:
        return _redirect_path(
            f"/ui/bookings/{booking_id}/edit",
            FLASH_ERR,
            "Invalid datetime format.",
            user_id=actor.id,
        )
    try:
        services.update_booking(session, booking_id, payload, actor)
    except services.NotFoundError:
        return _redirect_path("/ui/bookings", FLASH_ERR, "Booking not found.", user_id=actor.id)
    except services.BadRequestError as e:
        return _redirect_path(
            f"/ui/bookings/{booking_id}/edit",
            FLASH_ERR,
            e.message,
            user_id=actor.id,
        )
    return _redirect_path("/ui/bookings", FLASH_OK, "Booking updated.", user_id=actor.id)


@router.post("/ui/bookings/{booking_id}/delete")
def ui_booking_delete(
    _request: Request,
    booking_id: str,
    session: Session = Depends(get_session),
    actor: User = Depends(get_current_user),
) -> RedirectResponse:
    try:
        services.delete_booking(session, booking_id, actor)
    except services.NotFoundError:
        return _redirect_path("/ui/bookings", FLASH_ERR, "Booking not found.", user_id=actor.id)
    except services.BadRequestError as exc:
        return _redirect_path("/ui/bookings", FLASH_ERR, exc.message, user_id=actor.id)
    return _redirect_path("/ui/bookings", FLASH_OK, "Booking deleted.", user_id=actor.id)


@router.post("/ui/bookings/{booking_id}/approve")
def ui_booking_approve(
    _request: Request,
    booking_id: str,
    session: Session = Depends(get_session),
    actor: User = Depends(get_current_user),
) -> RedirectResponse:
    try:
        services.approve_booking(session, booking_id, actor)
    except services.NotFoundError:
        return _redirect_path("/ui/bookings", FLASH_ERR, "Booking not found.", user_id=actor.id)
    except services.BadRequestError as e:
        return _redirect_path("/ui/bookings", FLASH_ERR, e.message, user_id=actor.id)
    return _redirect_path("/ui/bookings", FLASH_OK, "Booking approved.", user_id=actor.id)


@router.post("/ui/bookings/{booking_id}/cancel")
def ui_booking_cancel(
    _request: Request,
    booking_id: str,
    session: Session = Depends(get_session),
    actor: User = Depends(get_current_user),
) -> RedirectResponse:
    try:
        services.cancel_booking(session, booking_id, actor)
    except services.NotFoundError:
        return _redirect_path("/ui/bookings", FLASH_ERR, "Booking not found.", user_id=actor.id)
    except services.BadRequestError as exc:
        return _redirect_path("/ui/bookings", FLASH_ERR, exc.message, user_id=actor.id)
    return _redirect_path("/ui/bookings", FLASH_OK, "Booking cancelled.", user_id=actor.id)


@router.get("/ui/calendar", response_class=Response)
def ui_calendar(
    request: Request,
    status_filter: str | None = Query(default=None),
    resource_type: str | None = Query(default=None),
    date: str | None = Query(default=None),
    session: Session = Depends(get_session),
    actor: User = Depends(get_current_user),
) -> Response:
    days = build_booking_calendar_rows(session, actor, status_filter, resource_type, date)
    resources = services.list_resources(session)
    return templates.TemplateResponse(
        request=request,
        name="ui_calendar.html",
        context={
            "booking_days": days,
            "resource_types": sorted({r.type for r in resources}),
            "filters": {"status": status_filter or "", "resource_type": resource_type or "", "date": date or ""},
            **_base_context(request, actor),
        },
    )


@router.get("/ui/admin", response_class=Response)
def ui_admin(
    request: Request,
    session: Session = Depends(get_session),
    actor: User = Depends(get_current_user),
) -> Response:
    if actor.role.value != "admin":
        return templates.TemplateResponse(
            request=request,
            name="ui_admin.html",
            context={"users": [], "forbidden": True, **_base_context(request, actor)},
            status_code=403,
        )
    return templates.TemplateResponse(
        request=request,
        name="ui_admin.html",
        context={"users": services.list_users(session), "forbidden": False, **_base_context(request, actor)},
    )
