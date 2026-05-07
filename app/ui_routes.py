"""HTML UI routes."""

from __future__ import annotations

import math
import math
from datetime import datetime
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from pydantic import ValidationError
from sqlmodel import Session

from app.auth import authenticate_user, get_current_user, require_admin
from app.db import get_session
from app.models_db import BookingPurposeCategory, User, UserRole
from app.security import hash_password
from app.schemas import BookingCreate, BookingUpdate, ResourceCreate, ResourceUpdate
from app import services
from app.demand_forecast_service import get_demand_forecast
from app.template_env import templates
from app.ui_helpers import paginate_resources

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


def _role_options() -> list[str]:
    return [role.value for role in UserRole]


def _parse_dt_local(value: str) -> datetime:
    normalized = value.strip().replace(" ", "T")
    if len(normalized) == 16:
        normalized += ":00"
    return datetime.fromisoformat(normalized)


def _purpose_categories() -> list[str]:
    return [category.value for category in BookingPurposeCategory]


@router.get("/ui", response_class=Response)
def ui_root() -> RedirectResponse:
    return RedirectResponse("/ui/dashboard", status_code=status.HTTP_302_FOUND)


@router.get("/ui/login", response_class=Response)
def ui_login_form(request: Request) -> Response:
    if request.session.get("user_id"):
        return RedirectResponse("/ui/dashboard", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse(request=request, name="ui_login.html", context=_flash_context(request))


@router.post("/ui/login")
def ui_login_submit(
    request: Request,
    user_id: str = Form(...),
    password: str = Form(...),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    user = authenticate_user(session, user_id=user_id.strip(), password=password)
    if user is None:
        return _redirect_path("/ui/login", FLASH_ERR, "Invalid credentials.")
    request.session["user_id"] = user.id
    return _redirect_path("/ui/dashboard", FLASH_OK, f"Welcome, {user.name}.")


@router.post("/ui/logout")
def ui_logout(request: Request) -> RedirectResponse:
    request.session.clear()
    return _redirect_path("/ui/login", FLASH_OK, "Logged out.")


@router.get("/ui/dashboard", response_class=Response)
def ui_dashboard(
    request: Request,
    page: int = 1,
    booking_page: int = 1,
    status_filter: str | None = Query(default=None),
    resource_type: str | None = Query(default=None),
    date: str | None = Query(default=None),
    user_filter: str | None = Query(default=None),
    session: Session = Depends(get_session),
    actor: User = Depends(get_current_user),
) -> Response:
    if page < 1:
        page = 1
    resources_slice, pagination = paginate_resources(session, page)
    booking_date = date or datetime.now().date().isoformat()
    bookings = services.list_bookings(session, actor)
    resources = {resource.id: resource for resource in services.list_resources(session)}
    if status_filter:
        bookings = [booking for booking in bookings if booking.status.value == status_filter]
    if resource_type:
        bookings = [booking for booking in bookings if resources.get(booking.resource_id) and resources[booking.resource_id].type == resource_type]
    bookings = [booking for booking in bookings if booking.start_time.date().isoformat() == booking_date]
    if actor.role.value == "admin":
        if user_filter == "me":
            bookings = [booking for booking in bookings if booking.user_id == actor.id]
        elif user_filter:
            bookings = [booking for booking in bookings if booking.user_id == user_filter]
    else:
        user_filter = "me"
    bookings = sorted(bookings, key=lambda booking: (booking.start_time, booking.id), reverse=True)
    booking_per_page = 5
    booking_total = len(bookings)
    booking_total_pages = max(1, math.ceil(booking_total / booking_per_page)) if booking_total else 1
    safe_booking_page = max(1, min(booking_page, booking_total_pages))
    booking_start = (safe_booking_page - 1) * booking_per_page
    bookings_page = bookings[booking_start : booking_start + booking_per_page]
    ctx = {
        "resources": resources_slice,
        "pagination": pagination,
        "bookings_page": bookings_page,
        "resource_name_by_id": {resource.id: resource.name for resource in resources.values()},
        "booking_pagination": {
            "page": safe_booking_page,
            "total_pages": booking_total_pages,
            "has_prev": safe_booking_page > 1,
            "has_next": safe_booking_page < booking_total_pages,
            "total": booking_total,
        },
        "resource_types": sorted({r.type for r in resources.values()}),
        "user_options": services.list_users(session),
        "filters": {"status": status_filter or "", "resource_type": resource_type or "", "date": booking_date, "user": user_filter or ""},
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
        return _redirect_path(f"/ui/resources?page={max(1,page)}", FLASH_ERR, exc.detail)
    try:
        payload = ResourceCreate(
            name=name.strip(),
            type=resource_type.strip(),
            location=location.strip(),
            capacity=capacity,
            is_active=is_active.lower() in ("true", "1", "on", "yes"),
        )
    except ValidationError as exc:
        return _redirect_path(f"/ui/resources?page={max(1,page)}", FLASH_ERR, str(exc.errors()[0]["msg"]))
    services.create_resource(session, payload)
    return _redirect_path(f"/ui/resources?page={max(1,page)}", FLASH_OK, "Resource created.")


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
        return _redirect_path("/ui/resources", FLASH_ERR, exc.detail)
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
    return _redirect_path("/ui/resources", FLASH_OK, "Resource updated.")


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
        return _redirect_path(f"/ui/resources?page={max(1,page)}", FLASH_ERR, exc.detail)
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
    )


@router.get("/ui/bookings", response_class=Response)
def ui_bookings_list(
    request: Request,
    page: int = 1,
    status_filter: str | None = Query(default=None),
    resource_type: str | None = Query(default=None),
    date: str | None = Query(default=None),
    user_filter: str | None = Query(default=None),
    session: Session = Depends(get_session),
    actor: User = Depends(get_current_user),
) -> Response:
    if page < 1:
        page = 1
    bookings = services.list_bookings(session, actor)
    # Newest first
    bookings_sorted = sorted(bookings, key=lambda b: (b.start_time, b.id), reverse=True)
    resource_options = services.list_resources(session)
    resource_name_by_id = {r.id: r.name for r in resource_options}
    if status_filter:
        bookings_sorted = [b for b in bookings_sorted if b.status.value == status_filter]
    if resource_type:
        resource_type_by_id = {r.id: r.type for r in resource_options}
        bookings_sorted = [b for b in bookings_sorted if resource_type_by_id.get(b.resource_id) == resource_type]
    if date:
        bookings_sorted = [b for b in bookings_sorted if b.start_time.date().isoformat() == date]
    if actor.role.value == "admin":
        if user_filter == "me":
            bookings_sorted = [b for b in bookings_sorted if b.user_id == actor.id]
        elif user_filter:
            bookings_sorted = [b for b in bookings_sorted if b.user_id == user_filter]
    else:
        user_filter = "me"
    per_page = 5
    total = len(bookings_sorted)
    total_pages = max(1, math.ceil(total / per_page)) if total else 1
    safe_page = max(1, min(page, total_pages))
    start = (safe_page - 1) * per_page
    bookings_page = bookings_sorted[start : start + per_page]
    ctx = {
        "bookings": bookings_page,
        "pagination": {
            "page": safe_page,
            "total_pages": total_pages,
            "has_prev": safe_page > 1,
            "has_next": safe_page < total_pages,
            "total": total,
            "per_page": per_page,
        },
        "resource_options": resource_options,
        "user_options": services.list_users(session),
        "resource_name_by_id": resource_name_by_id,
        "purpose_categories": _purpose_categories(),
        "resource_types": sorted({r.type for r in resource_options}),
        "filters": {"status": status_filter or "", "resource_type": resource_type or "", "date": date or "", "user": user_filter or ""},
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
    purpose_category: str = Form(default=""),
    attendees_count: int | None = Form(default=None),
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
            purpose_category=purpose_category.strip() or None,
            attendees_count=attendees_count,
        )
    except ValidationError:
        return _redirect_path("/ui/bookings", FLASH_ERR, "Could not create booking: fill all fields correctly.")
    except ValueError:
        return _redirect_path("/ui/bookings", FLASH_ERR, "Invalid datetime format.")
    try:
        services.create_booking(session, payload, actor)
    except services.BadRequestError as e:
        return _redirect_path("/ui/bookings", FLASH_ERR, e.message)
    return _redirect_path("/ui/bookings", FLASH_OK, "Booking created.")


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
        "purpose_categories": _purpose_categories(),
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
    purpose_category: str = Form(default=""),
    attendees_count: int | None = Form(default=None),
    session: Session = Depends(get_session),
    actor: User = Depends(get_current_user),
) -> RedirectResponse:
    try:
        payload = BookingUpdate(
            resource_id=resource_id.strip(),
            start_time=_parse_dt_local(start_time),
            end_time=_parse_dt_local(end_time),
            purpose=purpose.strip(),
            purpose_category=purpose_category.strip() or None,
            attendees_count=attendees_count,
        )
    except ValidationError:
        return _redirect_path(
            f"/ui/bookings/{booking_id}/edit",
            FLASH_ERR,
            "Could not update: invalid field values.",
        )
    except ValueError:
        return _redirect_path(
            f"/ui/bookings/{booking_id}/edit",
            FLASH_ERR,
            "Invalid datetime format.",
        )
    try:
        services.update_booking(session, booking_id, payload, actor)
    except services.NotFoundError:
        return _redirect_path("/ui/bookings", FLASH_ERR, "Booking not found.")
    except services.BadRequestError as e:
        return _redirect_path(
            f"/ui/bookings/{booking_id}/edit",
            FLASH_ERR,
            e.message,
        )
    return _redirect_path("/ui/bookings", FLASH_OK, "Booking updated.")


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
        return _redirect_path("/ui/bookings", FLASH_ERR, "Booking not found.")
    except services.BadRequestError as exc:
        return _redirect_path("/ui/bookings", FLASH_ERR, exc.message)
    return _redirect_path("/ui/bookings", FLASH_OK, "Booking deleted.")


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
        return _redirect_path("/ui/bookings", FLASH_ERR, "Booking not found.")
    except services.BadRequestError as e:
        return _redirect_path("/ui/bookings", FLASH_ERR, e.message)
    return _redirect_path("/ui/bookings", FLASH_OK, "Booking approved.")


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
        return _redirect_path("/ui/bookings", FLASH_ERR, "Booking not found.")
    except services.BadRequestError as exc:
        return _redirect_path("/ui/bookings", FLASH_ERR, exc.message)
    return _redirect_path("/ui/bookings", FLASH_OK, "Booking cancelled.")


@router.get("/ui/calendar", response_class=Response)
def ui_calendar(
    request: Request,
    page: int = 1,
    status_filter: str | None = Query(default=None),
    resource_type: str | None = Query(default=None),
    date: str | None = Query(default=None),
    user_filter: str | None = Query(default=None),
    session: Session = Depends(get_session),
    actor: User = Depends(get_current_user),
) -> Response:
    if page < 1:
        page = 1
    booking_date = date or datetime.now().date().isoformat()
    bookings = services.list_bookings(session, actor)
    resources = services.list_resources(session)
    resources_by_id = {resource.id: resource for resource in resources}
    if status_filter:
        bookings = [booking for booking in bookings if booking.status.value == status_filter]
    if resource_type:
        bookings = [booking for booking in bookings if resources_by_id.get(booking.resource_id) and resources_by_id[booking.resource_id].type == resource_type]
    bookings = [booking for booking in bookings if booking.start_time.date().isoformat() == booking_date]
    if actor.role.value == "admin":
        if user_filter == "me":
            bookings = [booking for booking in bookings if booking.user_id == actor.id]
        elif user_filter:
            bookings = [booking for booking in bookings if booking.user_id == user_filter]
    else:
        user_filter = "me"
    bookings = sorted(bookings, key=lambda booking: (booking.start_time, booking.id), reverse=True)
    per_page = 5
    total = len(bookings)
    total_pages = max(1, math.ceil(total / per_page)) if total else 1
    safe_page = max(1, min(page, total_pages))
    start = (safe_page - 1) * per_page
    bookings_page = bookings[start : start + per_page]
    return templates.TemplateResponse(
        request=request,
        name="ui_calendar.html",
        context={
            "bookings_page": bookings_page,
            "resource_name_by_id": {resource.id: resource.name for resource in resources},
            "pagination": {"page": safe_page, "total_pages": total_pages, "has_prev": safe_page > 1, "has_next": safe_page < total_pages, "total": total},
            "resource_types": sorted({r.type for r in resources}),
            "user_options": services.list_users(session),
            "filters": {"status": status_filter or "", "resource_type": resource_type or "", "date": booking_date, "user": user_filter or ""},
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
        context={"users": services.list_users(session), "forbidden": False, "role_options": _role_options(), **_base_context(request, actor)},
    )


@router.post("/ui/admin/users")
def ui_admin_create_user(
    _request: Request,
    user_id: str = Form(...),
    name: str = Form(...),
    role: str = Form(default="employee"),
    temp_password: str = Form(...),
    session: Session = Depends(get_session),
    actor: User = Depends(get_current_user),
) -> RedirectResponse:
    try:
        require_admin(actor)
        role_value = UserRole(role)
        services.create_user(
            session,
            user_id=user_id.strip(),
            name=name.strip(),
            role=role_value,
            password_hash=hash_password(temp_password),
            is_active=True,
        )
    except HTTPException as exc:
        return _redirect_path("/ui/admin", FLASH_ERR, exc.detail)
    except ValueError:
        return _redirect_path("/ui/admin", FLASH_ERR, "Invalid role.")
    except services.BadRequestError as exc:
        return _redirect_path("/ui/admin", FLASH_ERR, exc.message)
    return _redirect_path("/ui/admin", FLASH_OK, "User created.")


@router.post("/ui/admin/users/{user_id}/reset-password")
def ui_admin_reset_password(
    _request: Request,
    user_id: str,
    temp_password: str = Form(...),
    session: Session = Depends(get_session),
    actor: User = Depends(get_current_user),
) -> RedirectResponse:
    try:
        require_admin(actor)
        services.reset_user_password(session, user_id, hash_password(temp_password))
    except HTTPException as exc:
        return _redirect_path("/ui/admin", FLASH_ERR, exc.detail)
    except services.NotFoundError as exc:
        return _redirect_path("/ui/admin", FLASH_ERR, exc.message)
    return _redirect_path("/ui/admin", FLASH_OK, "Password reset.")


@router.post("/ui/admin/users/{user_id}/toggle-active")
def ui_admin_toggle_user_active(
    _request: Request,
    user_id: str,
    is_active: str = Form(...),
    session: Session = Depends(get_session),
    actor: User = Depends(get_current_user),
) -> RedirectResponse:
    try:
        require_admin(actor)
        active_value = is_active.lower() in {"1", "true", "yes", "on"}
        services.set_user_active(session, user_id, active_value)
    except HTTPException as exc:
        return _redirect_path("/ui/admin", FLASH_ERR, exc.detail)
    except services.NotFoundError as exc:
        return _redirect_path("/ui/admin", FLASH_ERR, exc.message)
    return _redirect_path("/ui/admin", FLASH_OK, "User status updated.")


@router.get("/ui/analytics", response_class=Response)
def ui_analytics(
    request: Request,
    resource_type: str | None = Query(default=None),
    date: str | None = Query(default=None),
    building: str | None = Query(default=None),
    session: Session = Depends(get_session),
    actor: User = Depends(get_current_user),
) -> Response:
    if actor.role.value != "admin":
        return templates.TemplateResponse(
            request=request,
            name="ui_analytics.html",
            context={"forbidden": True, "forecast_result": None, "resource_types": [], "buildings": [], "filters": {}, **_base_context(request, actor)},
            status_code=403,
        )

    resources = services.list_resources(session)
    resource_types = sorted({resource.type for resource in resources})
    buildings = sorted({resource.building for resource in resources if resource.building})
    filters = {"resource_type": resource_type or "", "date": date or "", "building": building or ""}
    forecast_result = None

    if resource_type and date:
        try:
            parsed_date = datetime.strptime(date, "%Y-%m-%d").date()
            building_value = building.strip() if building and building.strip() else None
            forecast_result = get_demand_forecast(
                session,
                resource_type=resource_type,
                target_date=parsed_date,
                building=building_value,
            )
        except ValueError:
            return _redirect_path("/ui/analytics", FLASH_ERR, "Invalid date format. Use YYYY-MM-DD.")
        except FileNotFoundError as exc:
            return _redirect_path("/ui/analytics", FLASH_ERR, str(exc))

    return templates.TemplateResponse(
        request=request,
        name="ui_analytics.html",
        context={
            "forbidden": False,
            "forecast_result": forecast_result,
            "resource_types": resource_types,
            "buildings": buildings,
            "filters": filters,
            **_base_context(request, actor),
        },
    )
