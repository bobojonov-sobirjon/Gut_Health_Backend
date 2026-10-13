"""Push-notification device tokens for the signed-in user."""

from uuid import UUID

from fastapi import APIRouter, Response, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.device import DeviceRead, DeviceUpdate, DeviceUpsert
from app.services import device_service

router = APIRouter(prefix="/devices", tags=["devices"])


@router.get("", response_model=list[DeviceRead])
async def list_my_devices(current_user: CurrentUser, session: DbSession) -> list[DeviceRead]:
    """List push tokens registered for the current account."""

    devices = await device_service.list_devices(session, current_user.id)
    return [DeviceRead.model_validate(device) for device in devices]


@router.post("", response_model=DeviceRead, status_code=status.HTTP_201_CREATED)
async def register_device(
    payload: DeviceUpsert,
    current_user: CurrentUser,
    session: DbSession,
) -> DeviceRead:
    """Create or refresh the push token for this device."""

    device = await device_service.upsert_device(session, current_user.id, payload)
    return DeviceRead.model_validate(device)


@router.get("/{device_id}", response_model=DeviceRead)
async def read_device(
    device_id: UUID,
    current_user: CurrentUser,
    session: DbSession,
) -> DeviceRead:
    """Return one of the current user's devices."""

    device = await device_service.get_device(session, current_user.id, device_id)
    return DeviceRead.model_validate(device)


@router.patch("/{device_id}", response_model=DeviceRead)
async def patch_device(
    device_id: UUID,
    payload: DeviceUpdate,
    current_user: CurrentUser,
    session: DbSession,
) -> DeviceRead:
    """Update the name, platform, app version, or active flag."""

    device = await device_service.update_device(session, current_user.id, device_id, payload)
    return DeviceRead.model_validate(device)


@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_device(
    device_id: UUID,
    current_user: CurrentUser,
    session: DbSession,
) -> Response:
    """Remove a push token from this account."""

    await device_service.delete_device(session, current_user.id, device_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
