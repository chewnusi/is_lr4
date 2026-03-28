"""
Resource Booking Management System — FastAPI entrypoint and routes.
"""

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.models import (
    Booking,
    BookingCreate,
    BookingUpdate,
    Resource,
    ResourceCreate,
    ResourceUpdate,
)
from app import services
from app import ui_routes
from app.template_env import APP_DIR

app = FastAPI(
    title="Resource Booking Management System",
    description="REST API for organizational resources and bookings (JSON file storage).",
    version="0.1.0",
)

app.include_router(ui_routes.router)


def _http_from_service(fn, *args, **kwargs):
    """Map service-layer errors to HTTP exceptions (shared by JSON API)."""
    try:
        return fn(*args, **kwargs)
    except services.NotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=e.message) from e
    except services.BadRequestError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=e.message) from e


@app.get("/", tags=["root"])
def read_root() -> dict:
    """Service info and link to interactive docs."""
    return {
        "service": "Resource Booking Management System",
        "docs": "/docs",
        "openapi": "/openapi.json",
        "ui": "/ui",
    }


# --- Resources ---


@app.post(
    "/resources",
    response_model=Resource,
    status_code=status.HTTP_201_CREATED,
    tags=["resources"],
)
def create_resource(payload: ResourceCreate) -> Resource:
    return services.create_resource(payload)


@app.get("/resources", response_model=list[Resource], tags=["resources"])
def list_resources() -> list[Resource]:
    return services.list_resources()


@app.get("/resources/{resource_id}", response_model=Resource, tags=["resources"])
def get_resource(resource_id: str) -> Resource:
    return _http_from_service(services.get_resource, resource_id)


@app.put("/resources/{resource_id}", response_model=Resource, tags=["resources"])
def update_resource(resource_id: str, payload: ResourceUpdate) -> Resource:
    return _http_from_service(services.update_resource, resource_id, payload)


@app.delete("/resources/{resource_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["resources"])
def delete_resource(resource_id: str) -> None:
    _http_from_service(services.delete_resource, resource_id)


# --- Bookings ---


@app.post(
    "/bookings",
    response_model=Booking,
    status_code=status.HTTP_201_CREATED,
    tags=["bookings"],
)
def create_booking(payload: BookingCreate) -> Booking:
    return _http_from_service(services.create_booking, payload)


@app.get("/bookings", response_model=list[Booking], tags=["bookings"])
def list_bookings() -> list[Booking]:
    return services.list_bookings()


@app.get("/bookings/{booking_id}", response_model=Booking, tags=["bookings"])
def get_booking(booking_id: str) -> Booking:
    return _http_from_service(services.get_booking, booking_id)


@app.put("/bookings/{booking_id}", response_model=Booking, tags=["bookings"])
def update_booking(booking_id: str, payload: BookingUpdate) -> Booking:
    return _http_from_service(services.update_booking, booking_id, payload)


@app.patch(
    "/bookings/{booking_id}/approve",
    response_model=Booking,
    tags=["bookings"],
)
def approve_booking(booking_id: str) -> Booking:
    return _http_from_service(services.approve_booking, booking_id)


@app.patch(
    "/bookings/{booking_id}/cancel",
    response_model=Booking,
    tags=["bookings"],
)
def cancel_booking(booking_id: str) -> Booking:
    return _http_from_service(services.cancel_booking, booking_id)


@app.delete("/bookings/{booking_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["bookings"])
def delete_booking(booking_id: str) -> None:
    _http_from_service(services.delete_booking, booking_id)


@app.exception_handler(ValueError)
def value_error_handler(_request, exc: ValueError) -> JSONResponse:
    """Return 500 if on-disk JSON is corrupted or malformed."""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": str(exc)},
    )

app.mount(
    "/static",
    StaticFiles(directory=str(APP_DIR / "static")),
    name="static",
)
