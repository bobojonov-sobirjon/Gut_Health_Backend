"""Image upload. The database stores the path; the response includes the public URL."""

from typing import Annotated

from fastapi import APIRouter, File, Query, UploadFile, status
from pydantic import BaseModel

from app.api.deps import CurrentUser, DbSession
from app.models.user import UploadPurpose
from app.services.storage_service import to_public_url
from app.services.upload_service import store_upload

router = APIRouter(prefix="/uploads", tags=["uploads"])


class UploadResponse(BaseModel):
    path: str
    url: str
    purpose: UploadPurpose


@router.post("", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_image(
    current_user: CurrentUser,
    session: DbSession,
    purpose: Annotated[UploadPurpose, Query(description="avatar saves the path on the user. log stores a diary photo.")],
    file: UploadFile = File(...),
) -> UploadResponse:
    """Save a JPEG, PNG, or WebP image and return the URL the app should display."""

    record = await store_upload(session, current_user, file, purpose)
    url = to_public_url(record.stored_path)
    if url is None:
        raise RuntimeError("Stored upload is missing a public URL")
    return UploadResponse(path=record.stored_path, url=url, purpose=record.purpose)
