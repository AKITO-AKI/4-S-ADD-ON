"""Models router – LoRA file upload, download, list, and delete."""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.responses import Response
from fastapi.security import OAuth2PasswordBearer

from core.security import decode_access_token
from schemas.lora import LoraModelInfo, LoraModelListResponse, LoraUploadResponse
from services import storage

router = APIRouter(tags=["models"])

# ---------------------------------------------------------------------------
# Dependency: current user ID from Bearer token
# ---------------------------------------------------------------------------

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
# Endpoints
# ---------------------------------------------------------------------------


def _require_same_user(current_user_id: str, user_id: str) -> None:
    """Raise 403 if the authenticated user does not own the requested resource."""
    if current_user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")


@router.get(
    "/models/{user_id}/lora",
    response_model=LoraModelListResponse,
    summary="List LoRA models for a user (used by Blender add-on)",
)
async def list_lora_models(
    user_id: str,
    current_user_id: str = Depends(get_current_user_id),
):
    """Return metadata for every LoRA model stored in S3 under the given user_id."""
    _require_same_user(current_user_id, user_id)
    items = storage.list_lora_models(user_id)
    lora_models = [LoraModelInfo(**item) for item in items]
    return LoraModelListResponse(user_id=user_id, models=lora_models)


@router.post(
    "/models/{user_id}/lora",
    response_model=LoraUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a LoRA model file",
)
async def upload_lora_model(
    user_id: str,
    file: UploadFile,
    current_user_id: str = Depends(get_current_user_id),
):
    """Upload a `.safetensors` or `.pt` LoRA model to S3."""
    _require_same_user(current_user_id, user_id)

    if file.filename is None or not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Filename is required")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File is empty")

    key = storage.upload_lora_model(user_id, file.filename, data)
    return LoraUploadResponse(key=key, filename=file.filename)


@router.get(
    "/models/{user_id}/lora/{filename}",
    summary="Download a LoRA model file",
)
async def download_lora_model(
    user_id: str,
    filename: str,
    current_user_id: str = Depends(get_current_user_id),
):
    """Stream a LoRA model file from S3."""
    _require_same_user(current_user_id, user_id)

    try:
        data = storage.download_lora_model(user_id, filename)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return Response(
        content=data,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.delete(
    "/models/{user_id}/lora/{filename}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a LoRA model file",
)
async def delete_lora_model(
    user_id: str,
    filename: str,
    current_user_id: str = Depends(get_current_user_id),
):
    _require_same_user(current_user_id, user_id)
    try:
        storage.delete_lora_model(user_id, filename)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
