"""Pydantic schemas for generation parameter snapshots."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class SnapshotCreate(BaseModel):
    name: str
    parameters: dict[str, Any]


class SnapshotUpdate(BaseModel):
    name: str | None = None
    parameters: dict[str, Any] | None = None


class SnapshotResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    parameters: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
