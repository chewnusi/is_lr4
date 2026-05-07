"""Database engine and session helpers."""

from __future__ import annotations

from sqlmodel import Session, SQLModel, create_engine

from app.config import settings


engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})


def get_session():
    with Session(engine) as session:
        yield session


def init_db() -> None:
    SQLModel.metadata.create_all(engine)
