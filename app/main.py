"""Resource Booking Management System entrypoint."""

from fastapi import FastAPI, status
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session, select

from app.config import settings
from app.db import engine, init_db
from app.models_db import User, UserRole
from app.routers import analytics, bookings, recommendations, resources, users
from app.seed import seed_if_empty
from app import ui_routes
from app.template_env import APP_DIR

app = FastAPI(
    title="Resource Booking Management System",
    description="REST API for organizational resources and bookings (SQLite/SQLModel).",
    version="1.0.0",
)

app.include_router(ui_routes.router)
app.include_router(resources.router)
app.include_router(bookings.router)
app.include_router(users.router)
app.include_router(analytics.router)
app.include_router(recommendations.router)


def _seed_default_users() -> None:
    with Session(engine) as session:
        if session.exec(select(User)).first() is not None:
            return
        session.add(User(id="demo-employee", name="Demo Employee", role=UserRole.employee))
        session.add(User(id="demo-admin", name="Demo Admin", role=UserRole.admin))
        session.commit()


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    _seed_default_users()
    if settings.seed_on_start:
        seed_if_empty(engine)


@app.get("/", tags=["root"])
def read_root() -> dict:
    return {
        "service": "Resource Booking Management System",
        "version": "1.0.0",
        "docs": "/docs",
        "openapi": "/openapi.json",
        "ui": "/ui/dashboard",
    }


@app.exception_handler(ValueError)
def value_error_handler(_request, exc: ValueError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": str(exc)},
    )

app.mount(
    "/static",
    StaticFiles(directory=str(APP_DIR / "static")),
    name="static",
)
