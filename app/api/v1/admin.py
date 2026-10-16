"""Admin panel API. Every collection has a list and a full detail route."""

from uuid import UUID

from fastapi import APIRouter, Query, Response, status

from app.api.deps import CurrentAdmin, DbSession
from app.schemas.admin import (
    AdminBowelListItem,
    AdminBowelPage,
    AdminDevicePage,
    AdminDeviceRead,
    AdminDiaryDetail,
    AdminDiaryPage,
    AdminFoodListItem,
    AdminFoodPage,
    AdminLoginRequest,
    AdminLoginResponse,
    AdminOnboardingPage,
    AdminOnboardingRead,
    AdminProfile,
    AdminStats,
    AdminUserDetail,
    AdminUserListItem,
    AdminUserPage,
    AdminUserUpdate,
)
from app.schemas.device import DeviceUpdate
from app.schemas.survey import (
    SurveyOptionUpdate,
    SurveyOptionWrite,
    SurveyQuestionRead,
    SurveyQuestionUpdate,
    SurveyQuestionWrite,
    UserSurveyRead,
)
from app.services import admin_service, survey_service
from app.services.auth_service import login_admin

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/login", response_model=AdminLoginResponse)
async def admin_login(payload: AdminLoginRequest, session: DbSession) -> AdminLoginResponse:
    """Sign in with the administrator email and password from the environment."""

    user, tokens = await login_admin(session, str(payload.email), payload.password)
    return AdminLoginResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        expires_in=tokens.expires_in,
        admin=AdminProfile.model_validate(user),
    )


@router.get("/me", response_model=AdminProfile)
async def admin_me(current_admin: CurrentAdmin) -> AdminProfile:
    """Return the signed-in administrator."""

    return AdminProfile.model_validate(current_admin)


@router.get("/stats", response_model=AdminStats)
async def admin_stats(current_admin: CurrentAdmin, session: DbSession) -> AdminStats:
    """Counts for the dashboard."""

    return await admin_service.stats(session)


@router.get("/users", response_model=AdminUserPage)
async def admin_users(
    current_admin: CurrentAdmin,
    session: DbSession,
    q: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> AdminUserPage:
    users, total = await admin_service.list_users(session, query=q, limit=limit, offset=offset)
    return AdminUserPage(
        items=[AdminUserListItem.model_validate(user) for user in users],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/users/{user_id}", response_model=AdminUserDetail)
async def admin_user_detail(
    user_id: UUID,
    current_admin: CurrentAdmin,
    session: DbSession,
) -> AdminUserDetail:
    return await admin_service.get_user_detail(session, user_id)


@router.patch("/users/{user_id}", response_model=AdminUserListItem)
async def admin_user_update(
    user_id: UUID,
    payload: AdminUserUpdate,
    current_admin: CurrentAdmin,
    session: DbSession,
) -> AdminUserListItem:
    user = await admin_service.update_user(session, user_id, payload, actor_id=current_admin.id)
    return AdminUserListItem.model_validate(user)


@router.get("/devices", response_model=AdminDevicePage)
async def admin_devices(
    current_admin: CurrentAdmin,
    session: DbSession,
    q: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> AdminDevicePage:
    items, total = await admin_service.list_devices(session, query=q, limit=limit, offset=offset)
    return AdminDevicePage(items=items, total=total, limit=limit, offset=offset)


@router.get("/devices/{device_id}", response_model=AdminDeviceRead)
async def admin_device_detail(
    device_id: UUID,
    current_admin: CurrentAdmin,
    session: DbSession,
) -> AdminDeviceRead:
    return await admin_service.get_device(session, device_id)


@router.patch("/devices/{device_id}", response_model=AdminDeviceRead)
async def admin_device_update(
    device_id: UUID,
    payload: DeviceUpdate,
    current_admin: CurrentAdmin,
    session: DbSession,
) -> AdminDeviceRead:
    return await admin_service.update_device(session, device_id, payload)


@router.delete("/devices/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_device_delete(
    device_id: UUID,
    current_admin: CurrentAdmin,
    session: DbSession,
) -> Response:
    await admin_service.delete_device(session, device_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/onboarding", response_model=AdminOnboardingPage)
async def admin_onboarding(
    current_admin: CurrentAdmin,
    session: DbSession,
    q: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> AdminOnboardingPage:
    items, total = await admin_service.list_onboarding(session, query=q, limit=limit, offset=offset)
    return AdminOnboardingPage(items=items, total=total, limit=limit, offset=offset)


@router.delete("/onboarding/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_onboarding_delete(
    profile_id: UUID,
    current_admin: CurrentAdmin,
    session: DbSession,
) -> Response:
    await admin_service.delete_onboarding(session, profile_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/onboarding/{profile_id}", response_model=AdminOnboardingRead)
async def admin_onboarding_detail(
    profile_id: UUID,
    current_admin: CurrentAdmin,
    session: DbSession,
) -> AdminOnboardingRead:
    return await admin_service.get_onboarding(session, profile_id)


@router.get("/diary", response_model=AdminDiaryPage)
async def admin_diary(
    current_admin: CurrentAdmin,
    session: DbSession,
    q: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> AdminDiaryPage:
    items, total = await admin_service.list_diary(session, query=q, limit=limit, offset=offset)
    return AdminDiaryPage(items=items, total=total, limit=limit, offset=offset)


@router.delete("/diary/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_diary_delete(
    entry_id: UUID,
    current_admin: CurrentAdmin,
    session: DbSession,
) -> Response:
    await admin_service.delete_diary(session, entry_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/diary/{entry_id}", response_model=AdminDiaryDetail)
async def admin_diary_detail(
    entry_id: UUID,
    current_admin: CurrentAdmin,
    session: DbSession,
) -> AdminDiaryDetail:
    return await admin_service.get_diary(session, entry_id)


@router.get("/bowel", response_model=AdminBowelPage)
async def admin_bowel(
    current_admin: CurrentAdmin,
    session: DbSession,
    q: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> AdminBowelPage:
    items, total = await admin_service.list_bowel(session, query=q, limit=limit, offset=offset)
    return AdminBowelPage(items=items, total=total, limit=limit, offset=offset)


@router.delete("/bowel/{movement_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_bowel_delete(
    movement_id: UUID,
    current_admin: CurrentAdmin,
    session: DbSession,
) -> Response:
    await admin_service.delete_bowel(session, movement_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/bowel/{movement_id}", response_model=AdminBowelListItem)
async def admin_bowel_detail(
    movement_id: UUID,
    current_admin: CurrentAdmin,
    session: DbSession,
) -> AdminBowelListItem:
    return await admin_service.get_bowel(session, movement_id)


@router.get("/food", response_model=AdminFoodPage)
async def admin_food(
    current_admin: CurrentAdmin,
    session: DbSession,
    q: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> AdminFoodPage:
    items, total = await admin_service.list_food(session, query=q, limit=limit, offset=offset)
    return AdminFoodPage(items=items, total=total, limit=limit, offset=offset)


@router.delete("/food/{food_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_food_delete(
    food_id: UUID,
    current_admin: CurrentAdmin,
    session: DbSession,
) -> Response:
    await admin_service.delete_food(session, food_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/food/{food_id}", response_model=AdminFoodListItem)
async def admin_food_detail(
    food_id: UUID,
    current_admin: CurrentAdmin,
    session: DbSession,
) -> AdminFoodListItem:
    return await admin_service.get_food(session, food_id)


@router.get("/survey/questions", response_model=list[SurveyQuestionRead])
async def admin_survey_questions(
    current_admin: CurrentAdmin,
    session: DbSession,
) -> list[SurveyQuestionRead]:
    questions = await survey_service.list_questions(session, active_only=False)
    return [SurveyQuestionRead.model_validate(question) for question in questions]


@router.post("/survey/questions", response_model=SurveyQuestionRead, status_code=status.HTTP_201_CREATED)
async def admin_create_survey_question(
    payload: SurveyQuestionWrite,
    current_admin: CurrentAdmin,
    session: DbSession,
) -> SurveyQuestionRead:
    question = await survey_service.create_question(session, payload)
    return SurveyQuestionRead.model_validate(question)


@router.patch("/survey/questions/{question_id}", response_model=SurveyQuestionRead)
async def admin_update_survey_question(
    question_id: UUID,
    payload: SurveyQuestionUpdate,
    current_admin: CurrentAdmin,
    session: DbSession,
) -> SurveyQuestionRead:
    question = await survey_service.update_question(session, question_id, payload)
    return SurveyQuestionRead.model_validate(question)


@router.delete("/survey/questions/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_survey_question(
    question_id: UUID,
    current_admin: CurrentAdmin,
    session: DbSession,
) -> Response:
    await survey_service.delete_question(session, question_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/survey/questions/{question_id}/options",
    response_model=SurveyQuestionRead,
    status_code=status.HTTP_201_CREATED,
)
async def admin_create_survey_option(
    question_id: UUID,
    payload: SurveyOptionWrite,
    current_admin: CurrentAdmin,
    session: DbSession,
) -> SurveyQuestionRead:
    question = await survey_service.create_option(session, question_id, payload)
    return SurveyQuestionRead.model_validate(question)


@router.patch("/survey/options/{option_id}", response_model=SurveyQuestionRead)
async def admin_update_survey_option(
    option_id: UUID,
    payload: SurveyOptionUpdate,
    current_admin: CurrentAdmin,
    session: DbSession,
) -> SurveyQuestionRead:
    question = await survey_service.update_option(session, option_id, payload)
    return SurveyQuestionRead.model_validate(question)


@router.delete("/survey/options/{option_id}", response_model=SurveyQuestionRead)
async def admin_delete_survey_option(
    option_id: UUID,
    current_admin: CurrentAdmin,
    session: DbSession,
) -> SurveyQuestionRead:
    question = await survey_service.delete_option(session, option_id)
    return SurveyQuestionRead.model_validate(question)


@router.delete("/survey/answers/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_survey_answers(
    user_id: UUID,
    current_admin: CurrentAdmin,
    session: DbSession,
) -> Response:
    await survey_service.delete_user_answers(session, user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/survey/answers", response_model=list[UserSurveyRead])
async def admin_survey_answers(
    current_admin: CurrentAdmin,
    session: DbSession,
    q: str | None = Query(default=None),
) -> list[UserSurveyRead]:
    return await survey_service.list_user_surveys(session, q)
