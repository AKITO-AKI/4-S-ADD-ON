"""Pydantic schemas for LoRA model operations."""

from pydantic import BaseModel


class LoraModelInfo(BaseModel):
    """Metadata for a single LoRA model file stored in S3."""

    key: str
    filename: str
    size_bytes: int
    last_modified: str
    download_url: str


class LoraModelListResponse(BaseModel):
    user_id: str
    models: list[LoraModelInfo]


class LoraUploadResponse(BaseModel):
    key: str
    filename: str
    message: str = "Upload successful"
