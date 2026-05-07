from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.db import get_session
from app.main import app
from app.models_db import User, UserRole
from app.security import hash_password


@pytest.fixture()
def db_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(User(id="demo-employee", name="Demo Employee", role=UserRole.employee, password_hash=hash_password("ChangeMe123!"), is_active=True))
        session.add(User(id="demo-admin", name="Demo Admin", role=UserRole.admin, password_hash=hash_password("ChangeMe123!"), is_active=True))
        session.commit()
    return engine


@pytest.fixture()
def client(db_engine):
    def _override_session():
        with Session(db_engine) as session:
            yield session

    app.dependency_overrides[get_session] = _override_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def booking_payload():
    base = datetime.now().replace(minute=0, second=0, microsecond=0) + timedelta(days=1)
    return {
        "resource_id": "",
        "user_id": "demo-employee",
        "start_time": base.isoformat(),
        "end_time": (base + timedelta(hours=1)).isoformat(),
        "purpose": "Team sync",
    }
