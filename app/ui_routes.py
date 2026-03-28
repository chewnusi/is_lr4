"""
HTML UI routes: forms and redirects for resource and booking CRUD.

Uses app.services for persistence rules; flashes use query params after redirect.
"""

from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Form, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from pydantic import ValidationError

from app.models import BookingCreate, BookingUpdate, ResourceCreate, ResourceUpdate
from app import services
from app.template_env import templates
from app.ui_helpers import build_ui_context, paginate_resources

router = APIRouter(tags=["ui"])

FLASH_OK = "ok"
FLASH_ERR = "error"


def _redirect_with_flash(path: str, notice: str, message: str) -> RedirectResponse:
    q = f"notice={notice}&msg={quote(message, safe='')}"
    sep = "&" if "?" in path else "?"
    return RedirectResponse(url=f"{path}{sep}{q}", status_code=status.HTTP_303_SEE_OTHER)


def _flash_context(request: Request) -> dict:
    return {
        "flash_notice": request.query_params.get("notice"),
        "flash_message": request.query_params.get("msg"),
    }


@router.get("/ui", response_class=Response)
def ui_overview(request: Request, page: int = 1) -> Response:
    """Combined read-only-style overview (resources + calendar)."""
    if page < 1:
        page = 1
    ctx = build_ui_context(page)
    ctx.update(_flash_context(request))
    return templates.TemplateResponse(
        request=request,
        name="ui_overview.html",
        context=ctx,
    )


@router.get("/ui/resources", response_class=Response)
def ui_resources_list(request: Request, page: int = 1) -> Response:
    if page < 1:
        page = 1
    resources_slice, pagination = paginate_resources(page)
    ctx = {
        "resources": resources_slice,
        "pagination": pagination,
        **_flash_context(request),
    }
    return templates.TemplateResponse(
        request=request,
        name="ui_resources.html",
        context=ctx,
    )


@router.post("/ui/resources")
def ui_resources_create(
    request: Request,
    name: str = Form(),
    resource_type: str = Form(),
    location: str = Form(),
    capacity: int = Form(),
    is_active: str = Form(default="true"),
    page: int = Form(default=1),
) -> RedirectResponse:
    try:
        payload = ResourceCreate(
            name=name.strip(),
            type=resource_type.strip(),
            location=location.strip(),
            capacity=capacity,
            is_active=is_active.lower() in ("true", "1", "on", "yes"),
        )
    except ValidationError:
        return _redirect_with_flash(
            f"/ui/resources?page={max(1, page)}",
            FLASH_ERR,
            "Could not create resource: check all fields (capacity must be at least 1).",
        )
    services.create_resource(payload)
    return _redirect_with_flash(
        f"/ui/resources?page={max(1, page)}",
        FLASH_OK,
        "Resource created.",
    )


@router.get("/ui/resources/{resource_id}/edit", response_class=Response)
def ui_resource_edit_form(request: Request, resource_id: str) -> Response:
    try:
        resource = services.get_resource(resource_id)
    except services.NotFoundError:
        raise HTTPException(status_code=404, detail="Resource not found")
    ctx = {"resource": resource.model_dump(), **_flash_context(request)}
    return templates.TemplateResponse(
        request=request,
        name="ui_resource_edit.html",
        context=ctx,
    )


@router.post("/ui/resources/{resource_id}/edit")
def ui_resource_edit_submit(
    request: Request,
    resource_id: str,
    name: str = Form(),
    resource_type: str = Form(),
    location: str = Form(),
    capacity: int = Form(),
    is_active: str = Form(default="true"),
) -> RedirectResponse:
    try:
        payload = ResourceUpdate(
            name=name.strip(),
            type=resource_type.strip(),
            location=location.strip(),
            capacity=capacity,
            is_active=is_active.lower() in ("true", "1", "on", "yes"),
        )
    except ValidationError:
        return _redirect_with_flash(
            f"/ui/resources/{resource_id}/edit",
            FLASH_ERR,
            "Could not update: invalid field values.",
        )
    try:
        services.update_resource(resource_id, payload)
    except services.NotFoundError:
        return _redirect_with_flash("/ui/resources", FLASH_ERR, "Resource not found.")
    except services.BadRequestError as e:
        return _redirect_with_flash(
            f"/ui/resources/{resource_id}/edit",
            FLASH_ERR,
            e.message,
        )
    return _redirect_with_flash("/ui/resources", FLASH_OK, "Resource updated.")


@router.post("/ui/resources/{resource_id}/delete")
def ui_resource_delete(
    request: Request,
    resource_id: str,
    page: int = Form(default=1),
) -> RedirectResponse:
    try:
        services.delete_resource(resource_id)
    except services.NotFoundError:
        return _redirect_with_flash(
            f"/ui/resources?page={max(1, page)}",
            FLASH_ERR,
            "Resource not found.",
        )
    return _redirect_with_flash(
        f"/ui/resources?page={max(1, page)}",
        FLASH_OK,
        "Resource deleted.",
    )


@router.get("/ui/bookings", response_class=Response)
def ui_bookings_list(request: Request) -> Response:
    bookings = services.list_bookings()
    # Stable display order
    bookings_sorted = sorted(bookings, key=lambda b: (b.start_time, b.id))
    resource_options = services.list_resources()
    resource_name_by_id = {r.id: r.name for r in resource_options}
    ctx = {
        "bookings": bookings_sorted,
        "resource_options": resource_options,
        "resource_name_by_id": resource_name_by_id,
        **_flash_context(request),
    }
    return templates.TemplateResponse(
        request=request,
        name="ui_bookings.html",
        context=ctx,
    )


@router.post("/ui/bookings")
def ui_bookings_create(
    request: Request,
    resource_id: str = Form(),
    user_name: str = Form(),
    start_time: str = Form(),
    end_time: str = Form(),
    purpose: str = Form(),
) -> RedirectResponse:
    try:
        payload = BookingCreate(
            resource_id=resource_id.strip(),
            user_name=user_name.strip(),
            start_time=start_time.strip(),
            end_time=end_time.strip(),
            purpose=purpose.strip(),
        )
    except ValidationError:
        return _redirect_with_flash(
            "/ui/bookings",
            FLASH_ERR,
            "Could not create booking: fill all fields correctly.",
        )
    try:
        services.create_booking(payload)
    except services.BadRequestError as e:
        return _redirect_with_flash("/ui/bookings", FLASH_ERR, e.message)
    return _redirect_with_flash("/ui/bookings", FLASH_OK, "Booking created.")


@router.get("/ui/bookings/{booking_id}/edit", response_class=Response)
def ui_booking_edit_form(request: Request, booking_id: str) -> Response:
    try:
        booking = services.get_booking(booking_id)
    except services.NotFoundError:
        raise HTTPException(status_code=404, detail="Booking not found")
    resource_options = services.list_resources()
    ctx = {
        "booking": booking.model_dump(),
        "resource_options": resource_options,
        **_flash_context(request),
    }
    return templates.TemplateResponse(
        request=request,
        name="ui_booking_edit.html",
        context=ctx,
    )


@router.post("/ui/bookings/{booking_id}/edit")
def ui_booking_edit_submit(
    request: Request,
    booking_id: str,
    resource_id: str = Form(),
    user_name: str = Form(),
    start_time: str = Form(),
    end_time: str = Form(),
    purpose: str = Form(),
) -> RedirectResponse:
    try:
        payload = BookingUpdate(
            resource_id=resource_id.strip(),
            user_name=user_name.strip(),
            start_time=start_time.strip(),
            end_time=end_time.strip(),
            purpose=purpose.strip(),
        )
    except ValidationError:
        return _redirect_with_flash(
            f"/ui/bookings/{booking_id}/edit",
            FLASH_ERR,
            "Could not update: invalid field values.",
        )
    try:
        services.update_booking(booking_id, payload)
    except services.NotFoundError:
        return _redirect_with_flash("/ui/bookings", FLASH_ERR, "Booking not found.")
    except services.BadRequestError as e:
        return _redirect_with_flash(
            f"/ui/bookings/{booking_id}/edit",
            FLASH_ERR,
            e.message,
        )
    return _redirect_with_flash("/ui/bookings", FLASH_OK, "Booking updated.")


@router.post("/ui/bookings/{booking_id}/delete")
def ui_booking_delete(request: Request, booking_id: str) -> RedirectResponse:
    try:
        services.delete_booking(booking_id)
    except services.NotFoundError:
        return _redirect_with_flash("/ui/bookings", FLASH_ERR, "Booking not found.")
    return _redirect_with_flash("/ui/bookings", FLASH_OK, "Booking deleted.")


@router.post("/ui/bookings/{booking_id}/approve")
def ui_booking_approve(request: Request, booking_id: str) -> RedirectResponse:
    try:
        services.approve_booking(booking_id)
    except services.NotFoundError:
        return _redirect_with_flash("/ui/bookings", FLASH_ERR, "Booking not found.")
    except services.BadRequestError as e:
        return _redirect_with_flash("/ui/bookings", FLASH_ERR, e.message)
    return _redirect_with_flash("/ui/bookings", FLASH_OK, "Booking approved.")


@router.post("/ui/bookings/{booking_id}/cancel")
def ui_booking_cancel(request: Request, booking_id: str) -> RedirectResponse:
    try:
        services.cancel_booking(booking_id)
    except services.NotFoundError:
        return _redirect_with_flash("/ui/bookings", FLASH_ERR, "Booking not found.")
    return _redirect_with_flash("/ui/bookings", FLASH_OK, "Booking cancelled.")
