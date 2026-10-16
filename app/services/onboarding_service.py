"""Save and read the single onboarding profile for a user."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import commit_session, utcnow
from app.core.exceptions import not_found
from app.models.onboarding import OnboardingProfile
from app.models.user import User
from app.schemas.onboarding import OnboardingRead, OnboardingWrite
from app.schemas.survey import SurveyAnswerGroup
from app.services import survey_service

_USER_CONFLICTS = {
    "uq_onboarding_profiles_user_id": "Onboarding has already been saved",
}


async def get_onboarding(session: AsyncSession, user_id: uuid.UUID) -> OnboardingRead:
    profile = await _find(session, user_id)
    if profile is None:
        raise not_found("Onboarding has not been saved")
    return await _read(session, profile)


async def save_onboarding(
    session: AsyncSession,
    user_id: uuid.UUID,
    payload: OnboardingWrite,
) -> OnboardingRead:
    profile = await _find(session, user_id)
    if profile is None:
        profile = OnboardingProfile(user_id=user_id)
        session.add(profile)
    if payload.answers is not None:
        goals, concerns, interests, text_value = await survey_service.save_user_answers(
            session,
            user_id,
            payload.answers,
        )
        profile.goals = goals
        profile.concerns = concerns
        profile.interests = interests
        profile.target_30_day_goal = text_value
    else:
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
    return await _read(session, profile)


async def _read(session: AsyncSession, profile: OnboardingProfile) -> OnboardingRead:
    answers: list[SurveyAnswerGroup] = await survey_service.answers_for_user(session, profile.user_id)
    data = OnboardingRead.model_validate(profile).model_dump()
    data["answers"] = answers
    return OnboardingRead.model_validate(data)


async def _find(session: AsyncSession, user_id: uuid.UUID) -> OnboardingProfile | None:
    statement = select(OnboardingProfile).where(OnboardingProfile.user_id == user_id)
    return (await session.execute(statement)).scalar_one_or_none()
