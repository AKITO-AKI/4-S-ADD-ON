"""S3-compatible storage service using boto3."""

from __future__ import annotations

import io
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

from core.config import settings


def _get_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key_id,
        aws_secret_access_key=settings.s3_secret_access_key,
        region_name=settings.s3_region_name,
    )


def _lora_prefix(user_id: str) -> str:
    return f"users/{user_id}/lora/"


def upload_lora_model(user_id: str, filename: str, data: bytes) -> str:
    """Upload a LoRA model file to S3 and return its object key."""
    client = _get_client()
    key = f"{_lora_prefix(user_id)}{filename}"
    client.put_object(
        Bucket=settings.s3_bucket_name,
        Key=key,
        Body=data,
    )
    return key


def download_lora_model(user_id: str, filename: str) -> bytes:
    """Download a LoRA model file from S3 and return its raw bytes."""
    client = _get_client()
    key = f"{_lora_prefix(user_id)}{filename}"
    try:
        response = client.get_object(Bucket=settings.s3_bucket_name, Key=key)
        return response["Body"].read()
    except ClientError as exc:
        error_code = exc.response["Error"]["Code"]
        if error_code in ("NoSuchKey", "404"):
            raise FileNotFoundError(f"Model not found: {filename}") from exc
        raise


def list_lora_models(user_id: str) -> list[dict]:
    """List all LoRA model files for a user.

    Returns a list of dicts with keys: key, filename, size_bytes, last_modified,
    download_url.
    """
    client = _get_client()
    prefix = _lora_prefix(user_id)
    paginator = client.get_paginator("list_objects_v2")
    items: list[dict] = []

    for page in paginator.paginate(Bucket=settings.s3_bucket_name, Prefix=prefix):
        for obj in page.get("Contents", []):
            key: str = obj["Key"]
            filename = key.removeprefix(prefix)
            if not filename:
                continue
            last_modified: datetime = obj["LastModified"]
            download_url = client.generate_presigned_url(
                "get_object",
                Params={"Bucket": settings.s3_bucket_name, "Key": key},
                ExpiresIn=3600,
            )
            items.append(
                {
                    "key": key,
                    "filename": filename,
                    "size_bytes": obj["Size"],
                    "last_modified": last_modified.astimezone(timezone.utc).isoformat(),
                    "download_url": download_url,
                }
            )

    return items


def delete_lora_model(user_id: str, filename: str) -> None:
    """Delete a LoRA model file from S3.

    Raises FileNotFoundError if the object does not exist.
    """
    client = _get_client()
    key = f"{_lora_prefix(user_id)}{filename}"
    # S3 delete_object is idempotent; perform a head check first to surface 404 explicitly.
    try:
        client.head_object(Bucket=settings.s3_bucket_name, Key=key)
    except ClientError as exc:
        error_code = exc.response["Error"]["Code"]
        if error_code in ("NoSuchKey", "404", "403"):
            raise FileNotFoundError(f"Model not found: {filename}") from exc
        raise
    client.delete_object(Bucket=settings.s3_bucket_name, Key=key)
