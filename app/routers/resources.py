from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.auth import get_current_user, require_admin
from app.db import get_session
from app.models_db import User
from app.schemas import ResourceCreate, ResourceRead, ResourceUpdate
from app import services

router = APIRouter(prefix="/resources", tags=["resources"])


@router.post("", response_model=ResourceRead, status_code=status.HTTP_201_CREATED)
def create_resource(
    payload: ResourceCreate,
    session: Session = Depends(get_session),
    actor: User = Depends(get_current_user),
) -> ResourceRead:
    require_admin(actor)
    return services.create_resource(session, payload)


@router.get("", response_model=list[ResourceRead])
def list_resources(session: Session = Depends(get_session)) -> list[ResourceRead]:
    return services.list_resources(session)


@router.get("/{resource_id}", response_model=ResourceRead)
def get_resource(resource_id: str, session: Session = Depends(get_session)) -> ResourceRead:
    try:
        return services.get_resource(session, resource_id)
    except services.NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=exc.message) from exc


@router.put("/{resource_id}", response_model=ResourceRead)
def update_resource(
    resource_id: str,
    payload: ResourceUpdate,
    session: Session = Depends(get_session),
    actor: User = Depends(get_current_user),
) -> ResourceRead:
    require_admin(actor)
    try:
        return services.update_resource(session, resource_id, payload)
    except services.NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    except services.BadRequestError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=exc.message) from exc


@router.delete("/{resource_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_resource(
    resource_id: str,
    session: Session = Depends(get_session),
    actor: User = Depends(get_current_user),
) -> None:
    require_admin(actor)
    try:
        services.delete_resource(session, resource_id)
    except services.NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
