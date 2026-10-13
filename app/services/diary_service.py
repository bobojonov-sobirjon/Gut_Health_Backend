"""Diary commands scoped to the authenticated user.

The calendar query counts child rows with scalar subqueries so a month view
does not load every bowel log and food row. The day view eager-loads both
collections through the diary_entry_id indexes.
"""

import logging
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import commit_session, utcnow
from app.core.exceptions import AppError, not_found
from app.models.diary import BowelMovement, DiaryEntry, FoodDrinkLog
from app.models.user import UploadPurpose, UploadedFile, User
from app.schemas.diary import (
    BowelMovementWrite,
    DiaryCalendarItem,
    DiaryEntryCreate,
    DiaryEntryUpdate,
    FoodDrinkWrite,
)
from app.services.storage_service import as_stored_path, delete_stored

logger = logging.getLogger(__name__)

_DATE_CONFLICTS = {
    "uq_diary_entries_user_date": "A diary entry already exists for this date",
}
_SCALAR_FIELDS = {
    "entry_date",
    "no_bowel_movement",
    "stress_level",
    "sleep_hours",
    "exercise_minutes",
    "water_ml",
    "other_factors",
    "factors",
}
_MAX_RANGE_DAYS = 366
_ENTRY_OPTIONS = (
    selectinload(DiaryEntry.bowel_movements),
    selectinload(DiaryEntry.food_drinks),
)


async def list_calendar(
    session: AsyncSession,
    user_id: uuid.UUID,
    start_date: date | None,
    end_date: date | None,
) -> tuple[list[DiaryCalendarItem], date | None]:
    user = await session.get(User, user_id)
    started = user.tracking_started_on if user is not None else None
    today = utcnow().date()
    start_date, end_date = _normalize_range(start_date, end_date, started, today)
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
        select(
            DiaryEntry.entry_date,
            DiaryEntry.no_bowel_movement,
            bowel_count.label("bowel_movement_count"),
            food_count.label("food_drink_count"),
            DiaryEntry.created_at,
        )
        .where(
            DiaryEntry.user_id == user_id,
            DiaryEntry.entry_date >= start_date,
            DiaryEntry.entry_date <= end_date,
        )
    )
    rows = (await session.execute(statement)).all()
    by_date = {row.entry_date: row for row in rows}
    items: list[DiaryCalendarItem] = []
    day = end_date
    while day >= start_date:
        row = by_date.get(day)
        day_status, stool_status = _day_statuses(day, row, started, today)
        items.append(
            DiaryCalendarItem(
                entry_date=day,
                day_status=day_status,
                stool_status=stool_status,
                has_entry=row is not None,
                no_bowel_movement=bool(row.no_bowel_movement) if row is not None else False,
                bowel_movement_count=row.bowel_movement_count if row is not None else 0,
                food_drink_count=row.food_drink_count if row is not None else 0,
                created_at=row.created_at if row is not None else None,
            )
        )
        day -= timedelta(days=1)
    return items, started


async def create_entry(
    session: AsyncSession,
    user_id: uuid.UUID,
    payload: DiaryEntryCreate,
) -> DiaryEntry:
    _reject_conflicting_bowel_flag(payload.no_bowel_movement, payload.bowel_movements)
    entry = DiaryEntry(
        user_id=user_id,
        entry_date=payload.entry_date,
        no_bowel_movement=payload.no_bowel_movement,
        stress_level=payload.stress_level,
        sleep_hours=_sleep_hours(payload.sleep_hours),
        exercise_minutes=payload.exercise_minutes,
        water_ml=payload.water_ml,
        other_factors=payload.other_factors,
        factors=list(payload.factors),
    )
    session.add(entry)
    await session.flush()
    await _note_tracking_start(session, user_id, payload.entry_date)
    if not payload.no_bowel_movement:
        for item in payload.bowel_movements:
            session.add(_new_bowel(entry.id, item))
    for item in payload.food_drinks:
        session.add(await _new_food(session, user_id, entry.id, item))
    await commit_session(session, _DATE_CONFLICTS)
    logger.info("Created diary entry %s for user %s", entry.id, user_id)
    return await _get_or_404(session, user_id, payload.entry_date)


async def get_entry(
    session: AsyncSession,
    user_id: uuid.UUID,
    entry_date: date,
) -> DiaryEntry:
    return await _get_or_404(session, user_id, entry_date)


async def update_entry(
    session: AsyncSession,
    user_id: uuid.UUID,
    entry_date: date,
    payload: DiaryEntryUpdate,
) -> DiaryEntry:
    entry = await _get_or_404(session, user_id, entry_date)
    entry.updated_at = utcnow()
    provided = payload.model_fields_set
    flag = payload.no_bowel_movement if "no_bowel_movement" in provided else entry.no_bowel_movement
    if "bowel_movements" in provided and payload.bowel_movements is not None:
        _reject_conflicting_bowel_flag(flag, payload.bowel_movements)

    changes = payload.model_dump(exclude_unset=True)
    if "sleep_hours" in changes:
        changes["sleep_hours"] = _sleep_hours(changes["sleep_hours"])
    for key, value in changes.items():
        if key in _SCALAR_FIELDS:
            setattr(entry, key, value)

    removed_photos: set[str] = set()
    if flag:
        await _clear_bowel(session, entry)
    elif "bowel_movements" in provided and payload.bowel_movements is not None:
        await _replace_bowel(session, entry, payload.bowel_movements)

    if "food_drinks" in provided and payload.food_drinks is not None:
        removed_photos = await _replace_food(session, user_id, entry, payload.food_drinks)

    await _note_tracking_start(session, user_id, entry.entry_date)
    await session.flush()
    unused_photos = await _drop_unused_photos(session, user_id, removed_photos)
    await commit_session(session, _DATE_CONFLICTS)
    for path in unused_photos:
        delete_stored(path)

    saved_date = entry.entry_date
    logger.info("Updated diary entry %s for user %s", entry.id, user_id)
    return await _get_or_404(session, user_id, saved_date)


async def delete_entry(
    session: AsyncSession,
    user_id: uuid.UUID,
    entry_date: date,
) -> None:
    entry = await _get_or_404(session, user_id, entry_date)
    photos = {item.photo_url for item in entry.food_drinks if item.photo_url}
    await session.delete(entry)
    await session.flush()
    unused_photos = await _drop_unused_photos(session, user_id, photos)
    await commit_session(session)
    for path in unused_photos:
        delete_stored(path)
    logger.info("Deleted diary entry for user %s on %s", user_id, entry_date)


async def sync_entries(
    session: AsyncSession,
    user_id: uuid.UUID,
    entries: list[DiaryEntryCreate],
    since: datetime | None,
) -> list[DiaryEntry]:
    """Replace days from the device, then return days changed since the cursor."""

    latest: dict[date, DiaryEntryCreate] = {}
    for item in entries:
        latest[item.entry_date] = item
    for item in latest.values():
        exists = await session.scalar(
            select(DiaryEntry.id).where(
                DiaryEntry.user_id == user_id,
                DiaryEntry.entry_date == item.entry_date,
            )
        )
        if exists is None:
            await create_entry(session, user_id, item)
            continue
        await update_entry(
            session,
            user_id,
            item.entry_date,
            DiaryEntryUpdate(
                no_bowel_movement=item.no_bowel_movement,
                stress_level=item.stress_level,
                sleep_hours=item.sleep_hours,
                exercise_minutes=item.exercise_minutes,
                water_ml=item.water_ml,
                other_factors=item.other_factors,
                factors=item.factors,
                bowel_movements=item.bowel_movements,
                food_drinks=item.food_drinks,
            ),
        )
    return await list_entries_since(session, user_id, since)


async def list_entries_since(
    session: AsyncSession,
    user_id: uuid.UUID,
    since: datetime | None,
) -> list[DiaryEntry]:
    cutoff = since or (utcnow() - timedelta(days=31))
    statement = (
        select(DiaryEntry)
        .where(DiaryEntry.user_id == user_id, DiaryEntry.updated_at >= cutoff)
        .options(*_ENTRY_OPTIONS)
        .execution_options(populate_existing=True)
        .order_by(DiaryEntry.entry_date)
        .limit(90)
    )
    return list((await session.execute(statement)).scalars().all())


def _normalize_range(
    start_date: date | None,
    end_date: date | None,
    tracking_started_on: date | None,
    today: date,
) -> tuple[date, date]:
    if start_date is None and end_date is None:
        end_date = today
        start_date = end_date - timedelta(days=30)
        if tracking_started_on is not None and start_date < tracking_started_on <= end_date:
            start_date = tracking_started_on
    elif start_date is None or end_date is None:
        raise AppError(
            400,
            "Provide both start_date and end_date, or neither",
            "invalid_date_range",
        )
    if end_date < start_date:
        raise AppError(400, "end_date must be on or after start_date", "invalid_date_range")
    if (end_date - start_date).days > _MAX_RANGE_DAYS:
        raise AppError(400, "Date range cannot exceed 366 days", "invalid_date_range")
    return start_date, end_date


def _day_statuses(day: date, row: object | None, started: date | None, today: date) -> tuple[str, str]:
    if started is not None and day < started:
        return "before_start", "unknown"
    if row is None:
        if day > today:
            return "future", "unknown"
        if day == today:
            return "open", "unknown"
        return "missed", "unknown"
    if row.no_bowel_movement:
        return "tracked", "none"
    if row.bowel_movement_count > 0:
        return "tracked", "logged"
    return "tracked", "unknown"


async def _note_tracking_start(session: AsyncSession, user_id: uuid.UUID, on_date: date) -> None:
    user = await session.get(User, user_id)
    if user is None:
        return
    if user.tracking_started_on is None or on_date < user.tracking_started_on:
        user.tracking_started_on = on_date


def _reject_conflicting_bowel_flag(no_bowel_movement: bool, movements: list[BowelMovementWrite]) -> None:
    if no_bowel_movement and movements:
        raise AppError(
            400,
            "A day marked with no bowel movement cannot include bowel logs",
            "invalid_bowel_state",
        )


def _sleep_hours(value: float | None) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value)).quantize(Decimal("0.1"))


def _new_bowel(entry_id: uuid.UUID, payload: BowelMovementWrite) -> BowelMovement:
    return BowelMovement(
        diary_entry_id=entry_id,
        occurred_at=payload.occurred_at,
        bristol_type=payload.bristol_type,
        pain_level=payload.pain_level,
        blood_present=payload.blood_present,
    )


async def _new_food(
    session: AsyncSession,
    user_id: uuid.UUID,
    entry_id: uuid.UUID,
    payload: FoodDrinkWrite,
) -> FoodDrinkLog:
    return FoodDrinkLog(
        diary_entry_id=entry_id,
        kind=payload.kind,
        name=payload.name,
        consumed_at=payload.consumed_at,
        notes=payload.notes,
        photo_url=await _owned_log_photo(session, user_id, payload.photo_url),
    )


async def _clear_bowel(session: AsyncSession, entry: DiaryEntry) -> None:
    for item in list(entry.bowel_movements):
        await session.delete(item)


async def _replace_bowel(
    session: AsyncSession,
    entry: DiaryEntry,
    movements: list[BowelMovementWrite],
) -> None:
    for item in list(entry.bowel_movements):
        await session.delete(item)
    await session.flush()
    for item in movements:
        session.add(_new_bowel(entry.id, item))


async def _replace_food(
    session: AsyncSession,
    user_id: uuid.UUID,
    entry: DiaryEntry,
    items: list[FoodDrinkWrite],
) -> set[str]:
    previous = {item.photo_url for item in entry.food_drinks if item.photo_url}
    for item in list(entry.food_drinks):
        await session.delete(item)
    await session.flush()
    incoming: set[str] = set()
    for item in items:
        food = await _new_food(session, user_id, entry.id, item)
        if food.photo_url:
            incoming.add(food.photo_url)
        session.add(food)
    return previous - incoming


async def _owned_log_photo(
    session: AsyncSession,
    user_id: uuid.UUID,
    raw_value: str | None,
) -> str | None:
    stored_path = as_stored_path(raw_value)
    if stored_path is None:
        return None
    statement = select(UploadedFile.id).where(
        UploadedFile.user_id == user_id,
        UploadedFile.stored_path == stored_path,
        UploadedFile.purpose == UploadPurpose.LOG,
    )
    found = (await session.execute(statement)).scalar_one_or_none()
    if found is None:
        raise AppError(400, "Photo was not uploaded for this account", "invalid_media_path")
    return stored_path


async def _drop_unused_photos(
    session: AsyncSession,
    user_id: uuid.UUID,
    paths: set[str],
) -> list[str]:
    if not paths:
        return []
    statement = select(FoodDrinkLog.photo_url).where(FoodDrinkLog.photo_url.in_(paths))
    still_used = {path for path in (await session.execute(statement)).scalars().all() if path}
    unused = paths - still_used
    if unused:
        await session.execute(
            delete(UploadedFile).where(
                UploadedFile.user_id == user_id,
                UploadedFile.stored_path.in_(unused),
            )
        )
    return sorted(unused)


async def _get_or_404(
    session: AsyncSession,
    user_id: uuid.UUID,
    entry_date: date,
) -> DiaryEntry:
    statement = (
        select(DiaryEntry)
        .where(DiaryEntry.user_id == user_id, DiaryEntry.entry_date == entry_date)
        .options(*_ENTRY_OPTIONS)
        .execution_options(populate_existing=True)
    )
    entry = (await session.execute(statement)).scalar_one_or_none()
    if entry is None:
        raise not_found("Diary entry not found")
    return entry
