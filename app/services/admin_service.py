"""Read-only operations and account controls for the admin panel."""

import uuid
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import commit_session
from app.core.exceptions import AppError, not_found
from app.models.device import UserDevice
from app.models.diary import BowelMovement, DiaryEntry, FoodDrinkLog
from app.models.onboarding import OnboardingProfile
from app.models.user import UploadedFile, User
from app.schemas.admin import (
    AdminBowelListItem,
    AdminBowelRead,
    AdminDeviceRead,
    AdminDiaryDetail,
    AdminDiaryListItem,
    AdminDiarySummary,
    AdminFoodListItem,
    AdminFoodRead,
    AdminOnboardingRead,
    AdminStats,
    AdminUploadRead,
    AdminUserDetail,
    AdminUserListItem,
    AdminUserUpdate,
)
from app.schemas.device import DeviceRead, DeviceUpdate
from app.services.storage_service import to_public_url


def page_window(limit: int, offset: int) -> tuple[int, int]:
    return min(max(limit, 1), 100), max(offset, 0)


async def stats(session: AsyncSession) -> AdminStats:
    return AdminStats(
        users=await _count(session, User),
        active_users=await _count(session, User, User.is_active.is_(True)),
        admins=await _count(session, User, User.is_admin.is_(True)),
        devices=await _count(session, UserDevice),
        active_devices=await _count(session, UserDevice, UserDevice.is_active.is_(True)),
        onboarding_profiles=await _count(session, OnboardingProfile),
        diary_entries=await _count(session, DiaryEntry),
        bowel_movements=await _count(session, BowelMovement),
        food_drinks=await _count(session, FoodDrinkLog),
        uploads=await _count(session, UploadedFile),
    )


async def list_users(
    session: AsyncSession,
    *,
    query: str | None,
    limit: int,
    offset: int,
) -> tuple[list[User], int]:
    limit, offset = page_window(limit, offset)
    filters = _user_search(query)
    total = await _count(session, User, *filters)
    statement = select(User).order_by(User.created_at.desc()).limit(limit).offset(offset)
    if filters:
        statement = statement.where(*filters)
    return list((await session.execute(statement)).scalars().all()), total


async def get_user_detail(session: AsyncSession, user_id: uuid.UUID) -> AdminUserDetail:
    user = await session.get(User, user_id)
    if user is None:
        raise not_found("User not found")
    devices = list(
        (
            await session.execute(
                select(UserDevice).where(UserDevice.user_id == user_id).order_by(UserDevice.created_at.desc())
            )
        ).scalars().all()
    )
    onboarding = (
        await session.execute(select(OnboardingProfile).where(OnboardingProfile.user_id == user_id))
    ).scalar_one_or_none()
    uploads = list(
        (
            await session.execute(
                select(UploadedFile)
                .where(UploadedFile.user_id == user_id)
                .order_by(UploadedFile.created_at.desc())
            )
        ).scalars().all()
    )
    entries = list(
        (
            await session.execute(
                select(DiaryEntry)
                .where(DiaryEntry.user_id == user_id)
                .options(
                    selectinload(DiaryEntry.bowel_movements),
                    selectinload(DiaryEntry.food_drinks),
                )
                .order_by(DiaryEntry.entry_date.desc())
                .limit(50)
            )
        ).scalars().all()
    )
    diary_count = await _count(session, DiaryEntry, DiaryEntry.user_id == user_id)
    profile = AdminUserListItem.model_validate(user).model_dump()
    return AdminUserDetail(
        **profile,
        devices=[DeviceRead.model_validate(device) for device in devices],
        onboarding=_onboarding_read(onboarding, user.email) if onboarding else None,
        diary_entries=[_diary_summary(entry) for entry in entries],
        uploads=[_upload_read(item) for item in uploads],
        device_count=len(devices),
        diary_count=diary_count,
        upload_count=len(uploads),
    )


async def update_user(
    session: AsyncSession,
    user_id: uuid.UUID,
    payload: AdminUserUpdate,
    *,
    actor_id: uuid.UUID,
) -> User:
    user = await session.get(User, user_id)
    if user is None:
        raise not_found("User not found")
    if user_id == actor_id and payload.is_active is False:
        raise AppError(400, "You cannot deactivate your own admin account", "invalid_admin_update")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(user, key, value)
    await commit_session(session)
    return user


async def list_devices(
    session: AsyncSession,
    *,
    query: str | None,
    limit: int,
    offset: int,
) -> tuple[list[AdminDeviceRead], int]:
    limit, offset = page_window(limit, offset)
    filters = []
    if query and query.strip():
        term = f"%{query.strip()}%"
        filters.append(or_(User.email.ilike(term), UserDevice.device_name.ilike(term), UserDevice.token.ilike(term)))
    total_statement = select(func.count()).select_from(UserDevice).join(User, User.id == UserDevice.user_id)
    if filters:
        total_statement = total_statement.where(*filters)
    total = int(await session.scalar(total_statement) or 0)
    statement = (
        select(UserDevice)
        .join(User, User.id == UserDevice.user_id)
        .options(selectinload(UserDevice.user))
        .order_by(UserDevice.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if filters:
        statement = statement.where(*filters)
    devices = list((await session.execute(statement)).scalars().all())
    return [_device_read(device) for device in devices], total


async def get_device(session: AsyncSession, device_id: uuid.UUID) -> AdminDeviceRead:
    statement = (
        select(UserDevice).where(UserDevice.id == device_id).options(selectinload(UserDevice.user))
    )
    device = (await session.execute(statement)).scalar_one_or_none()
    if device is None:
        raise not_found("Device not found")
    return _device_read(device)


async def update_device(
    session: AsyncSession,
    device_id: uuid.UUID,
    payload: DeviceUpdate,
) -> AdminDeviceRead:
    device = await session.get(UserDevice, device_id)
    if device is None:
        raise not_found("Device not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(device, key, value)
    await commit_session(session)
    return await get_device(session, device_id)


async def delete_device(session: AsyncSession, device_id: uuid.UUID) -> None:
    device = await session.get(UserDevice, device_id)
    if device is None:
        raise not_found("Device not found")
    await session.delete(device)
    await commit_session(session)


async def list_onboarding(
    session: AsyncSession,
    *,
    query: str | None,
    limit: int,
    offset: int,
) -> tuple[list[AdminOnboardingRead], int]:
    limit, offset = page_window(limit, offset)
    filters = []
    if query and query.strip():
        filters.append(User.email.ilike(f"%{query.strip()}%"))
    total_statement = (
        select(func.count()).select_from(OnboardingProfile).join(User, User.id == OnboardingProfile.user_id)
    )
    if filters:
        total_statement = total_statement.where(*filters)
    total = int(await session.scalar(total_statement) or 0)
    statement = (
        select(OnboardingProfile)
        .join(User, User.id == OnboardingProfile.user_id)
        .options(selectinload(OnboardingProfile.user))
        .order_by(OnboardingProfile.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if filters:
        statement = statement.where(*filters)
    rows = list((await session.execute(statement)).scalars().all())
    return [_onboarding_read(row, row.user.email) for row in rows], total


async def get_onboarding(session: AsyncSession, profile_id: uuid.UUID) -> AdminOnboardingRead:
    statement = (
        select(OnboardingProfile)
        .where(OnboardingProfile.id == profile_id)
        .options(selectinload(OnboardingProfile.user))
    )
    row = (await session.execute(statement)).scalar_one_or_none()
    if row is None:
        raise not_found("Onboarding profile not found")
    return _onboarding_read(row, row.user.email)


async def list_diary(
    session: AsyncSession,
    *,
    query: str | None,
    limit: int,
    offset: int,
) -> tuple[list[AdminDiaryListItem], int]:
    limit, offset = page_window(limit, offset)
    filters = []
    if query and query.strip():
        filters.append(User.email.ilike(f"%{query.strip()}%"))
    total_statement = select(func.count()).select_from(DiaryEntry).join(User, User.id == DiaryEntry.user_id)
    if filters:
        total_statement = total_statement.where(*filters)
    total = int(await session.scalar(total_statement) or 0)
    bowel_count = (
        select(func.count(BowelMovement.id))
        .where(BowelMovement.diary_entry_id == DiaryEntry.id)
        .correlate(DiaryEntry)
        .scalar_subquery()
    )
    food_count = (
        select(func.count(FoodDrinkLog.id))
        .where(FoodDrinkLog.diary_entry_id == DiaryEntry.id)
        .correlate(DiaryEntry)
        .scalar_subquery()
    )
    statement = (
        select(DiaryEntry, User.email, bowel_count, food_count)
        .join(User, User.id == DiaryEntry.user_id)
        .order_by(DiaryEntry.entry_date.desc())
        .limit(limit)
        .offset(offset)
    )
    if filters:
        statement = statement.where(*filters)
    rows = (await session.execute(statement)).all()
    return [
        _diary_list_item(entry, email, int(bowel or 0), int(food or 0))
        for entry, email, bowel, food in rows
    ], total


async def get_diary(session: AsyncSession, entry_id: uuid.UUID) -> AdminDiaryDetail:
    statement = (
        select(DiaryEntry)
        .where(DiaryEntry.id == entry_id)
        .options(
            selectinload(DiaryEntry.user),
            selectinload(DiaryEntry.bowel_movements),
            selectinload(DiaryEntry.food_drinks),
        )
    )
    entry = (await session.execute(statement)).scalar_one_or_none()
    if entry is None:
        raise not_found("Diary entry not found")
    base = _diary_list_item(
        entry,
        entry.user.email,
        len(entry.bowel_movements),
        len(entry.food_drinks),
    )
    return AdminDiaryDetail(
        **base.model_dump(),
        bowel_movements=[AdminBowelRead.model_validate(item) for item in entry.bowel_movements],
        food_drinks=[AdminFoodRead.model_validate(item) for item in entry.food_drinks],
    )


async def list_bowel(
    session: AsyncSession,
    *,
    query: str | None,
    limit: int,
    offset: int,
) -> tuple[list[AdminBowelListItem], int]:
    return await _list_day_children(session, BowelMovement, AdminBowelListItem, query, limit, offset)


async def get_bowel(session: AsyncSession, movement_id: uuid.UUID) -> AdminBowelListItem:
    return await _get_day_child(session, BowelMovement, AdminBowelListItem, movement_id, "Bowel log not found")


async def list_food(
    session: AsyncSession,
    *,
    query: str | None,
    limit: int,
    offset: int,
) -> tuple[list[AdminFoodListItem], int]:
    return await _list_day_children(
        session,
        FoodDrinkLog,
        AdminFoodListItem,
        query,
        limit,
        offset,
        extra_search=FoodDrinkLog.name,
    )


async def get_food(session: AsyncSession, food_id: uuid.UUID) -> AdminFoodListItem:
    return await _get_day_child(session, FoodDrinkLog, AdminFoodListItem, food_id, "Food or drink log not found")


async def _list_day_children(session, model, schema, query, limit, offset, extra_search=None):
    limit, offset = page_window(limit, offset)
    filters = []
    if query and query.strip():
        term = f"%{query.strip()}%"
        clauses = [User.email.ilike(term)]
        if extra_search is not None:
            clauses.append(extra_search.ilike(term))
        filters.append(or_(*clauses))
    joined = (
        select(func.count())
        .select_from(model)
        .join(DiaryEntry, model.diary_entry_id == DiaryEntry.id)
        .join(User, User.id == DiaryEntry.user_id)
    )
    if filters:
        joined = joined.where(*filters)
    total = int(await session.scalar(joined) or 0)
    statement = (
        select(model, User.id, User.email, DiaryEntry.entry_date)
        .join(DiaryEntry, model.diary_entry_id == DiaryEntry.id)
        .join(User, User.id == DiaryEntry.user_id)
        .order_by(DiaryEntry.entry_date.desc(), model.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if filters:
        statement = statement.where(*filters)
    rows = (await session.execute(statement)).all()
    return [_child_item(schema, row, user_id, email, entry_date) for row, user_id, email, entry_date in rows], total


async def _get_day_child(session, model, schema, item_id, missing: str):
    statement = (
        select(model, User.id, User.email, DiaryEntry.entry_date)
        .join(DiaryEntry, model.diary_entry_id == DiaryEntry.id)
        .join(User, User.id == DiaryEntry.user_id)
        .where(model.id == item_id)
    )
    row = (await session.execute(statement)).one_or_none()
    if row is None:
        raise not_found(missing)
    item, user_id, email, entry_date = row
    return _child_item(schema, item, user_id, email, entry_date)


def _child_item(schema, row, user_id, email, entry_date):
    base = AdminBowelRead if schema is AdminBowelListItem else AdminFoodRead
    data = base.model_validate(row).model_dump()
    data["user_id"] = user_id
    data["user_email"] = email
    data["entry_date"] = entry_date
    return schema.model_validate(data)


async def _count(session: AsyncSession, model: type, *filters: object) -> int:
    statement = select(func.count()).select_from(model)
    if filters:
        statement = statement.where(*filters)
    return int(await session.scalar(statement) or 0)


def _user_search(query: str | None) -> list[object]:
    if not query or not query.strip():
        return []
    term = f"%{query.strip()}%"
    return [or_(User.email.ilike(term), User.full_name.ilike(term))]


def _onboarding_read(row: OnboardingProfile, email: str) -> AdminOnboardingRead:
    data = AdminOnboardingRead.model_validate(row).model_dump()
    data["user_email"] = email
    return AdminOnboardingRead.model_validate(data)


def _upload_read(row: UploadedFile) -> AdminUploadRead:
    return AdminUploadRead(
        id=row.id,
        user_id=row.user_id,
        stored_path=row.stored_path,
        purpose=row.purpose,
        created_at=row.created_at,
        url=to_public_url(row.stored_path),
    )


def _device_read(device: UserDevice) -> AdminDeviceRead:
    data = DeviceRead.model_validate(device).model_dump()
    data["user_email"] = device.user.email
    return AdminDeviceRead.model_validate(data)


def _sleep(value: Decimal | None) -> float | None:
    if value is None:
        return None
    return float(value)


def _diary_list_item(
    entry: DiaryEntry,
    email: str,
    bowel_count: int,
    food_count: int,
) -> AdminDiaryListItem:
    return AdminDiaryListItem(
        id=entry.id,
        user_id=entry.user_id,
        user_email=email,
        entry_date=entry.entry_date,
        no_bowel_movement=entry.no_bowel_movement,
        stress_level=entry.stress_level,
        sleep_hours=_sleep(entry.sleep_hours),
        exercise_minutes=entry.exercise_minutes,
        water_ml=entry.water_ml,
        other_factors=entry.other_factors,
        factors=list(entry.factors or []),
        bowel_movement_count=bowel_count,
        food_drink_count=food_count,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
    )


def _diary_summary(entry: DiaryEntry) -> AdminDiarySummary:
    return AdminDiarySummary(
        id=entry.id,
        entry_date=entry.entry_date,
        no_bowel_movement=entry.no_bowel_movement,
        bowel_movement_count=len(entry.bowel_movements),
        food_drink_count=len(entry.food_drinks),
        created_at=entry.created_at,
        updated_at=entry.updated_at,
    )
