"""Save and read the single onboarding profile for a user."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import commit_session, utcnow
from app.core.exceptions import not_found
from app.models.onboarding import OnboardingProfile
from app.models.user import User
from app.schemas.onboarding import OnboardingWrite

_USER_CONFLICTS = {
    "uq_onboarding_profiles_user_id": "Onboarding has already been saved",
}


async def get_onboarding(session: AsyncSession, user_id: uuid.UUID) -> OnboardingProfile:
    profile = await _find(session, user_id)
    if profile is None:
        raise not_found("Onboarding has not been saved")
    return profile


async def save_onboarding(
    session: AsyncSession,
    user_id: uuid.UUID,
    payload: OnboardingWrite,
) -> OnboardingProfile:
    profile = await _find(session, user_id)
    if profile is None:
        profile = OnboardingProfile(user_id=user_id)
        session.add(profile)
    profile.goals = payload.goals
    profile.concerns = payload.concerns
    profile.interests = payload.interests
    profile.target_30_day_goal = payload.target_30_day_goal
    user = await session.get(User, user_id)
    if user is not None:
        user.onboarding_completed = True
        if user.tracking_started_on is None:
            user.tracking_started_on = utcnow().date()
    await commit_session(session, _USER_CONFLICTS)
    return profile


async def _find(session: AsyncSession, user_id: uuid.UUID) -> OnboardingProfile | None:
    statement = select(OnboardingProfile).where(OnboardingProfile.user_id == user_id)
    return (await session.execute(statement)).scalar_one_or_none()
