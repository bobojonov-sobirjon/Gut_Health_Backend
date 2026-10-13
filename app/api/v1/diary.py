"""Diary days: calendar view and create, read, update, delete for one date."""

from datetime import date, datetime, timezone

from fastapi import APIRouter, Query, Response, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.diary import (
    DiaryCalendarResponse,
    DiaryEntryCreate,
    DiaryEntryRead,
    DiaryEntryUpdate,
    DiarySyncRequest,
    DiarySyncResponse,
)
from app.services import diary_service

router = APIRouter(prefix="/diary", tags=["diary"])


@router.get("", response_model=DiaryCalendarResponse)
async def calendar_view(
    current_user: CurrentUser,
    session: DbSession,
    start_date: date | None = Query(default=None, description="Inclusive range start."),
    end_date: date | None = Query(default=None, description="Inclusive range end."),
) -> DiaryCalendarResponse:
    """Fill every day in the range with tracked, missed, open, or before_start.

    Omitting both dates returns today and up to 30 earlier days, not before
    tracking_started_on when that date is already set.
    """

    items, started = await diary_service.list_calendar(session, current_user.id, start_date, end_date)
    return DiaryCalendarResponse(tracking_started_on=started, items=items, total=len(items))


@router.post("", response_model=DiaryEntryRead, status_code=status.HTTP_201_CREATED)
async def create_diary_entry(
    payload: DiaryEntryCreate,
    current_user: CurrentUser,
    session: DbSession,
) -> DiaryEntryRead:
    """Create the diary entry for one calendar date."""

    entry = await diary_service.create_entry(session, current_user.id, payload)
    return DiaryEntryRead.model_validate(entry)


@router.post("/sync", response_model=DiarySyncResponse)
async def sync_diary(
    payload: DiarySyncRequest,
    current_user: CurrentUser,
    session: DbSession,
) -> DiarySyncResponse:
    """Push local days, then pull days changed since the cursor."""

    entries = await diary_service.sync_entries(
        session,
        current_user.id,
        payload.entries,
        payload.since,
    )
    return DiarySyncResponse(
        server_time=datetime.now(timezone.utc),
        entries=[DiaryEntryRead.model_validate(entry) for entry in entries],
    )


@router.get("/{entry_date}", response_model=DiaryEntryRead)
async def read_diary_day(
    entry_date: date,
    current_user: CurrentUser,
    session: DbSession,
) -> DiaryEntryRead:
    """Return one day, including bowel logs, food and drink, and factors."""

    entry = await diary_service.get_entry(session, current_user.id, entry_date)
    return DiaryEntryRead.model_validate(entry)


@router.patch("/{entry_date}", response_model=DiaryEntryRead)
async def update_diary_day(
    entry_date: date,
    payload: DiaryEntryUpdate,
    current_user: CurrentUser,
    session: DbSession,
) -> DiaryEntryRead:
    """Update a day. Sending bowel_movements or food_drinks replaces that list."""

    entry = await diary_service.update_entry(session, current_user.id, entry_date, payload)
    return DiaryEntryRead.model_validate(entry)


@router.delete("/{entry_date}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_diary_day(
    entry_date: date,
    current_user: CurrentUser,
    session: DbSession,
) -> Response:
    """Delete the diary entry for a calendar date."""

    await diary_service.delete_entry(session, current_user.id, entry_date)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
