"""Save and read onboarding answers."""

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.schemas.onboarding import OnboardingRead, OnboardingWrite
from app.schemas.survey import SurveyQuestionRead
from app.services import onboarding_service, survey_service

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@router.get("/questions", response_model=list[SurveyQuestionRead])
async def list_questions(current_user: CurrentUser, session: DbSession) -> list[SurveyQuestionRead]:
    """Active onboarding questions, in the order the app should show them."""

    questions = await survey_service.list_questions(session, active_only=True)
    visible: list[SurveyQuestionRead] = []
    for question in questions:
        data = SurveyQuestionRead.model_validate(question).model_dump()
        data["options"] = [option for option in data["options"] if option["is_active"]]
        visible.append(SurveyQuestionRead.model_validate(data))
    return visible


@router.get("", response_model=OnboardingRead)
async def read_onboarding(current_user: CurrentUser, session: DbSession) -> OnboardingRead:
    """Return the saved onboarding profile."""

    return await onboarding_service.get_onboarding(session, current_user.id)


@router.put("", response_model=OnboardingRead)
async def save_onboarding(
    payload: OnboardingWrite,
    current_user: CurrentUser,
    session: DbSession,
) -> OnboardingRead:
    """Create or replace onboarding answers for the authenticated user."""

    return await onboarding_service.save_onboarding(session, current_user.id, payload)
