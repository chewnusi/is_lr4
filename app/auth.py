"""Demo authorization helpers."""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException, Query, status
from sqlmodel import Session

from app.db import get_session
from app.models_db import User, UserRole


def get_current_user(
    session: Session = Depends(get_session),
    x_user_id: str | None = Header(default=None),
    user_id: str | None = Query(default=None),
) -> User:
    selected_id = user_id or x_user_id or "demo-employee"
    user = session.get(User, selected_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail=f"Unknown user: {selected_id}")
    return user


def require_admin(user: User) -> None:
    if user.role != UserRole.admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Admin role required")
