"""Persist an uploaded image and record its path in PostgreSQL."""

from fastapi import UploadFile
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import commit_session
from app.models.user import UploadPurpose, UploadedFile, User
from app.services.storage_service import delete_stored, save_image

_PATH_CONFLICTS = {
    "uq_uploaded_files_stored_path": "This file path is already stored",
}


async def store_upload(
    session: AsyncSession,
    user: User,
    upload: UploadFile,
    purpose: UploadPurpose,
) -> UploadedFile:
    folder = "avatars" if purpose is UploadPurpose.AVATAR else "logs"
    stored_path = await save_image(upload, folder=folder, name_prefix=str(user.id))
    record = UploadedFile(user_id=user.id, stored_path=stored_path, purpose=purpose)
    session.add(record)

    previous_avatar = user.avatar_url if purpose is UploadPurpose.AVATAR else None
    if purpose is UploadPurpose.AVATAR:
        user.avatar_url = stored_path
        if previous_avatar and previous_avatar != stored_path:
            await session.execute(
                delete(UploadedFile).where(
                    UploadedFile.user_id == user.id,
                    UploadedFile.stored_path == previous_avatar,
                )
            )

    try:
        await commit_session(session, _PATH_CONFLICTS)
    except Exception:
        delete_stored(stored_path)
        raise

    if previous_avatar and previous_avatar != stored_path:
        delete_stored(previous_avatar)
    return record
