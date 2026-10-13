"""Local image storage.

Files are written under ``app/media/avatars`` or ``app/media/logs``.
PostgreSQL stores the site path, for example ``/media/avatars/<id>.jpg``.
API schemas turn that path into an absolute URL.
"""

import asyncio
import logging
import uuid

from fastapi import UploadFile

from app.core.config import get_settings
from app.core.exceptions import AppError

logger = logging.getLogger(__name__)
_ALLOWED_FOLDERS = frozenset({"avatars", "logs"})


def to_public_url(stored_path: str | None) -> str | None:
    """Build the absolute URL a Flutter client can load."""

    if not stored_path:
        return None
    if stored_path.startswith(("http://", "https://")):
        return stored_path
    settings = get_settings()
    if not stored_path.startswith("/"):
        stored_path = f"/{stored_path}"
    return f"{settings.public_base_url}{stored_path}"


def as_stored_path(value: str | None) -> str | None:
    """Accept either a stored path or the absolute URL and return the stored path."""

    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    settings = get_settings()
    if value.startswith(settings.public_base_url):
        value = value[len(settings.public_base_url) :]
    if not value.startswith("/"):
        value = f"/{value}"
    prefix = settings.media_url_prefix.rstrip("/") + "/"
    if not value.startswith(prefix) or ".." in value.split("/"):
        raise AppError(
            400,
            "Photo URL must point at an uploaded media file",
            "invalid_media_path",
        )
    return value


async def save_image(
    upload: UploadFile,
    *,
    folder: str,
    name_prefix: str | None = None,
) -> str:
    """Validate an upload and return the stored path, such as ``/media/logs/<id>.jpg``."""

    if folder not in _ALLOWED_FOLDERS:
        raise RuntimeError(f"Unsupported storage folder: {folder}")

    settings = get_settings()
    try:
        data = await upload.read(settings.max_upload_bytes + 1)
    finally:
        await upload.close()

    if not data:
        raise AppError(400, "The uploaded file is empty", "empty_file")
    if len(data) > settings.max_upload_bytes:
        raise AppError(413, "File exceeds the upload size limit", "file_too_large")

    extension = _image_extension(data)
    if extension is None:
        raise AppError(
            400,
            "Only JPEG, PNG, and WebP images are accepted",
            "unsupported_file_type",
        )

    prefix = f"{name_prefix}_" if name_prefix else ""
    filename = f"{prefix}{uuid.uuid4()}{extension}"
    destination_dir = settings.media_dir / folder
    destination = destination_dir / filename
    try:
        await asyncio.to_thread(destination_dir.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(destination.write_bytes, data)
    except OSError as exc:
        logger.exception("Failed to store upload")
        raise AppError(500, "Could not store the file", "storage_failed") from exc
    return f"{settings.media_url_prefix}/{folder}/{filename}"


def delete_stored(stored_path: str | None) -> None:
    """Remove a file previously saved by :func:`save_image`. Missing files are ignored."""

    if not stored_path:
        return
    settings = get_settings()
    prefix = settings.media_url_prefix.rstrip("/")
    if stored_path.startswith(prefix + "/"):
        relative = stored_path[len(prefix) + 1 :]
    else:
        relative = stored_path.lstrip("/")
    root = settings.media_dir.resolve()
    candidate = (root / relative).resolve()
    try:
        inside = candidate.is_relative_to(root)
    except ValueError:
        inside = False
    if not inside or candidate == root:
        logger.warning("Refusing to delete a path outside media storage")
        return
    try:
        candidate.unlink(missing_ok=True)
    except OSError:
        logger.warning("Could not delete stored file")


def _image_extension(data: bytes) -> str | None:
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if len(data) >= 12 and data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return ".webp"
    return None
