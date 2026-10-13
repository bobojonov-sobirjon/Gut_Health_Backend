"""Register, list, update, and remove a user's push-notification tokens."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import commit_session, utcnow
from app.core.exceptions import not_found
from app.models.device import UserDevice
from app.schemas.device import DeviceUpdate, DeviceUpsert

_TOKEN_CONFLICTS = {
    "uq_user_devices_token": "This device token is already registered",
}


async def list_devices(session: AsyncSession, user_id: uuid.UUID) -> list[UserDevice]:
    statement = (
        select(UserDevice)
        .where(UserDevice.user_id == user_id)
        .order_by(UserDevice.created_at.desc())
    )
    return list((await session.execute(statement)).scalars().all())


async def get_device(session: AsyncSession, user_id: uuid.UUID, device_id: uuid.UUID) -> UserDevice:
    device = await _owned_device(session, user_id, device_id)
    if device is None:
        raise not_found("Device not found")
    return device


async def upsert_device(
    session: AsyncSession,
    user_id: uuid.UUID,
    payload: DeviceUpsert,
) -> UserDevice:
    statement = select(UserDevice).where(UserDevice.token == payload.token)
    device = (await session.execute(statement)).scalar_one_or_none()
    now = utcnow()
    if device is None:
        device = UserDevice(
            user_id=user_id,
            token=payload.token,
            platform=payload.platform,
            device_name=payload.device_name,
            app_version=payload.app_version,
            is_active=True,
            last_seen_at=now,
        )
        session.add(device)
    else:
        device.user_id = user_id
        device.platform = payload.platform
        device.device_name = payload.device_name
        device.app_version = payload.app_version
        device.is_active = True
        device.last_seen_at = now
    await commit_session(session, _TOKEN_CONFLICTS)
    return device


async def update_device(
    session: AsyncSession,
    user_id: uuid.UUID,
    device_id: uuid.UUID,
    payload: DeviceUpdate,
) -> UserDevice:
    device = await get_device(session, user_id, device_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(device, key, value)
    device.last_seen_at = utcnow()
    await commit_session(session)
    return device


async def delete_device(session: AsyncSession, user_id: uuid.UUID, device_id: uuid.UUID) -> None:
    device = await get_device(session, user_id, device_id)
    await session.delete(device)
    await commit_session(session)


async def _owned_device(
    session: AsyncSession,
    user_id: uuid.UUID,
    device_id: uuid.UUID,
) -> UserDevice | None:
    statement = select(UserDevice).where(UserDevice.id == device_id, UserDevice.user_id == user_id)
    return (await session.execute(statement)).scalar_one_or_none()
