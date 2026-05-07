"""Resource Booking Management System entrypoint."""

from fastapi import FastAPI, status
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from sqlalchemy.exc import OperationalError
from starlette.middleware.sessions import SessionMiddleware
from sqlmodel import Session, select

from app.config import settings
from app.db import engine, init_db
from app.models_db import User, UserRole
from app.routers import analytics, bookings, cancellation_risk, recommendations, resources, users
from app.seed import seed_if_empty
from app import ui_routes
from app.security import hash_password
from app.template_env import APP_DIR

app = FastAPI(
    title="Resource Booking Management System",
    description="REST API for organizational resources and bookings (SQLite/SQLModel).",
    version="1.0.0",
)
app.add_middleware(SessionMiddleware, secret_key=settings.session_secret)

app.include_router(ui_routes.router)
app.include_router(resources.router)
app.include_router(bookings.router)
app.include_router(users.router)
app.include_router(analytics.router)
app.include_router(cancellation_risk.router)
app.include_router(recommendations.router)


def _seed_default_users() -> None:
    demo_employees = [
        User(
            id=f"demo-employee-{index:03d}",
            name=f"Demo Employee {index:03d}",
            role=UserRole.employee,
            password_hash=hash_password(settings.seed_temp_password),
            is_active=True,
        )
        for index in range(1, 51)
    ]
    baseline_users = [
        User(
            id="demo-employee",
            name="Demo Employee",
            role=UserRole.employee,
            password_hash=hash_password(settings.seed_temp_password),
            is_active=True,
        ),
        User(
            id="demo-admin",
            name="Demo Admin",
            role=UserRole.admin,
            password_hash=hash_password(settings.seed_temp_password),
            is_active=True,
        ),
        *demo_employees,
    ]
    with Session(engine) as session:
        existing = {user.id: user for user in session.exec(select(User)).all()}
        for user in baseline_users:
            current = existing.get(user.id)
            if current:
                changed = False
                if not current.password_hash:
                    current.password_hash = user.password_hash
                    changed = True
                if not current.is_active:
                    current.is_active = True
                    changed = True
                if changed:
                    session.add(current)
                continue
            session.add(user)
        session.commit()


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    try:
        _seed_default_users()
    except OperationalError:
        # Tests can bootstrap their own isolated schemas without app DB migrations.
        pass
    if settings.seed_on_start:
        try:
            seed_if_empty(engine)
        except OperationalError:
            pass


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


@app.exception_handler(HTTPException)
def http_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code == status.HTTP_401_UNAUTHORIZED and request.url.path.startswith("/ui") and request.url.path != "/ui/login":
        return RedirectResponse(url="/ui/login", status_code=status.HTTP_303_SEE_OTHER)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

app.mount(
    "/static",
    StaticFiles(directory=str(APP_DIR / "static")),
    name="static",
)
