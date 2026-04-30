"""Snapshots router – save and retrieve generation parameter snapshots."""

import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import decode_access_token
from models.snapshot import GenerationSnapshot
from schemas.snapshot import SnapshotCreate, SnapshotResponse, SnapshotUpdate

router = APIRouter(prefix="/snapshots", tags=["snapshots"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user_id(token: str = Depends(oauth2_scheme)) -> str:
    try:
        return decode_access_token(token)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _snapshot_to_response(snap: GenerationSnapshot) -> SnapshotResponse:
    return SnapshotResponse(
        id=snap.id,
        user_id=snap.user_id,
        name=snap.name,
        parameters=json.loads(snap.parameters),
        created_at=snap.created_at,
        updated_at=snap.updated_at,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/",
    response_model=SnapshotResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Save a generation parameter snapshot",
)
async def create_snapshot(
    payload: SnapshotCreate,
    current_user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    snap = GenerationSnapshot(
        user_id=uuid.UUID(current_user_id),
        name=payload.name,
        parameters=json.dumps(payload.parameters),
    )
    db.add(snap)
    await db.flush()
    await db.refresh(snap)
    return _snapshot_to_response(snap)


@router.get(
    "/",
    response_model=list[SnapshotResponse],
    summary="List all snapshots for the authenticated user",
)
async def list_snapshots(
    current_user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(GenerationSnapshot).where(
            GenerationSnapshot.user_id == uuid.UUID(current_user_id)
        )
    )
    snaps = result.scalars().all()
    return [_snapshot_to_response(s) for s in snaps]


@router.get(
    "/{snapshot_id}",
    response_model=SnapshotResponse,
    summary="Retrieve a single snapshot by ID",
)
async def get_snapshot(
    snapshot_id: uuid.UUID,
    current_user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    snap = await db.get(GenerationSnapshot, snapshot_id)
    if snap is None or str(snap.user_id) != current_user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Snapshot not found")
    return _snapshot_to_response(snap)


@router.put(
    "/{snapshot_id}",
    response_model=SnapshotResponse,
    summary="Update an existing snapshot",
)
async def update_snapshot(
    snapshot_id: uuid.UUID,
    payload: SnapshotUpdate,
    current_user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    snap = await db.get(GenerationSnapshot, snapshot_id)
    if snap is None or str(snap.user_id) != current_user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Snapshot not found")

    if payload.name is not None:
        snap.name = payload.name
    if payload.parameters is not None:
        snap.parameters = json.dumps(payload.parameters)

    await db.flush()
    await db.refresh(snap)
    return _snapshot_to_response(snap)


@router.delete(
    "/{snapshot_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a snapshot",
)
async def delete_snapshot(
    snapshot_id: uuid.UUID,
    current_user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    snap = await db.get(GenerationSnapshot, snapshot_id)
    if snap is None or str(snap.user_id) != current_user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Snapshot not found")
    await db.delete(snap)
