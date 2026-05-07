"""Demo authorization helpers."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import Depends, Header, HTTPException, Query, Request, status
from sqlmodel import Session

from app.db import get_session
from app.models_db import User, UserRole
from app.security import verify_password


def get_current_user(
    request: Request,
    session: Session = Depends(get_session),
    x_user_id: str | None = Header(default=None),
    query_user_id: str | None = Query(default=None, alias="user_id"),
) -> User:
    session_user_id = request.session.get("user_id") if hasattr(request, "session") else None
    selected_id = session_user_id or query_user_id or x_user_id
    if not selected_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    user = session.get(User, selected_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail=f"Unknown user: {selected_id}")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="User account is inactive")
    return user


def require_admin(user: User) -> None:
    if user.role != UserRole.admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Admin role required")


def authenticate_user(session: Session, user_id: str, password: str) -> User | None:
    user = session.get(User, user_id)
    if user is None or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    user.last_login_at = datetime.now(UTC).replace(tzinfo=None)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user
