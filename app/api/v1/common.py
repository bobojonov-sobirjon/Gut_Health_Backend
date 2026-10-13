"""Service health."""

from pydantic import BaseModel
from sqlalchemy import text

from fastapi import APIRouter

from app.api.deps import DbSession

router = APIRouter(tags=["common"])


class HealthResponse(BaseModel):
    status: str


@router.get("/health", response_model=HealthResponse)
async def health(session: DbSession) -> HealthResponse:
    """Report that the API can reach the database."""

    await session.execute(text("SELECT 1"))
    return HealthResponse(status="ok")
