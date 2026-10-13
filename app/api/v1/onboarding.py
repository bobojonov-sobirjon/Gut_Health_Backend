"""Save and read onboarding answers."""

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.schemas.onboarding import OnboardingRead, OnboardingWrite
from app.services import onboarding_service

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@router.get("", response_model=OnboardingRead)
async def read_onboarding(current_user: CurrentUser, session: DbSession) -> OnboardingRead:
    """Return the saved onboarding profile."""

    profile = await onboarding_service.get_onboarding(session, current_user.id)
    return OnboardingRead.model_validate(profile)


@router.put("", response_model=OnboardingRead)
async def save_onboarding(
    payload: OnboardingWrite,
    current_user: CurrentUser,
    session: DbSession,
) -> OnboardingRead:
    """Create or replace onboarding answers for the authenticated user."""

    profile = await onboarding_service.save_onboarding(session, current_user.id, payload)
    return OnboardingRead.model_validate(profile)
