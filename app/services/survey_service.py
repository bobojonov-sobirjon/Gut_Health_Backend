"""Admin-managed onboarding questions and the answers stored on each user."""

import uuid
from collections import OrderedDict

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import commit_session
from app.core.exceptions import AppError, not_found
from app.models.survey import SurveyAnswer, SurveyOption, SurveyQuestion, SurveyQuestionKind
from app.models.user import User
from app.schemas.survey import (
    SurveyAnswerGroup,
    SurveyAnswerInput,
    SurveyOptionUpdate,
    SurveyOptionWrite,
    SurveyQuestionUpdate,
    SurveyQuestionWrite,
    UserSurveyRead,
)


async def list_questions(session: AsyncSession, *, active_only: bool) -> list[SurveyQuestion]:
    statement = select(SurveyQuestion).order_by(SurveyQuestion.sort_order, SurveyQuestion.created_at)
    if active_only:
        statement = statement.where(SurveyQuestion.is_active.is_(True))
    return list((await session.execute(statement)).scalars().unique().all())


async def create_question(session: AsyncSession, payload: SurveyQuestionWrite) -> SurveyQuestion:
    if payload.title is None:
        raise AppError(400, "Title is required", "validation_error")
    question = SurveyQuestion(**payload.model_dump())
    session.add(question)
    await commit_session(session)
    return await _question(session, question.id)


async def update_question(
    session: AsyncSession,
    question_id: uuid.UUID,
    payload: SurveyQuestionUpdate,
) -> SurveyQuestion:
    question = await _question(session, question_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(question, key, value)
    await commit_session(session)
    return await _question(session, question.id)


async def delete_question(session: AsyncSession, question_id: uuid.UUID) -> None:
    question = await session.get(SurveyQuestion, question_id)
    if question is None:
        raise not_found("Question not found")
    await session.delete(question)
    await commit_session(session)


async def create_option(
    session: AsyncSession,
    question_id: uuid.UUID,
    payload: SurveyOptionWrite,
) -> SurveyQuestion:
    await _question(session, question_id)
    if payload.label is None:
        raise AppError(400, "Option text is required", "validation_error")
    session.add(SurveyOption(question_id=question_id, **payload.model_dump()))
    await commit_session(session, {"uq_survey_options_question_label": "That answer is already on this question"})
    return await _question(session, question_id)


async def update_option(
    session: AsyncSession,
    option_id: uuid.UUID,
    payload: SurveyOptionUpdate,
) -> SurveyQuestion:
    option = await session.get(SurveyOption, option_id)
    if option is None:
        raise not_found("Answer option not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(option, key, value)
    await commit_session(session, {"uq_survey_options_question_label": "That answer is already on this question"})
    return await _question(session, option.question_id)


async def delete_option(session: AsyncSession, option_id: uuid.UUID) -> SurveyQuestion:
    option = await session.get(SurveyOption, option_id)
    if option is None:
        raise not_found("Answer option not found")
    question_id = option.question_id
    await session.delete(option)
    await commit_session(session)
    return await _question(session, question_id)


async def save_user_answers(
    session: AsyncSession,
    user_id: uuid.UUID,
    items: list[SurveyAnswerInput],
) -> tuple[list[str], list[str], list[str], str | None]:
    """Replace this user's survey answers. Returns legacy goal/concern/interest/text buckets."""

    questions = {
        question.id: question
        for question in await list_questions(session, active_only=False)
    }
    await session.execute(delete(SurveyAnswer).where(SurveyAnswer.user_id == user_id))
    goals: list[str] = []
    concerns: list[str] = []
    interests: list[str] = []
    text_value: str | None = None

    for item in items:
        question = questions.get(item.question_id)
        if question is None or not question.is_active:
            raise AppError(400, "That question is not available", "unknown_question")
        options = {option.id: option for option in question.options if option.is_active}
        if question.kind == SurveyQuestionKind.TEXT:
            if not item.text_value:
                continue
            text_value = item.text_value
            session.add(
                SurveyAnswer(
                    user_id=user_id,
                    question_id=question.id,
                    question_title=question.title,
                    question_kind=question.kind.value,
                    value_text=item.text_value,
                )
            )
            continue
        if question.kind == SurveyQuestionKind.SINGLE and len(item.option_ids) > 1:
            raise AppError(400, "This question accepts one answer", "too_many_answers")
        chosen: list[SurveyOption] = []
        for option_id in item.option_ids:
            option = options.get(option_id)
            if option is None:
                raise AppError(400, "That answer does not belong to the question", "unknown_option")
            chosen.append(option)
        for option in chosen:
            session.add(
                SurveyAnswer(
                    user_id=user_id,
                    question_id=question.id,
                    option_id=option.id,
                    question_title=question.title,
                    question_kind=question.kind.value,
                    value_text=option.label,
                )
            )
        labels = [option.label for option in chosen]
        if question.kind == SurveyQuestionKind.SINGLE:
            goals.extend(labels)
        elif question.kind == SurveyQuestionKind.TILES:
            interests.extend(labels)
        else:
            concerns.extend(labels)
    return goals, concerns, interests, text_value


async def delete_user_answers(session: AsyncSession, user_id: uuid.UUID) -> None:
    user = await session.get(User, user_id)
    if user is None:
        raise not_found("User not found")
    await session.execute(delete(SurveyAnswer).where(SurveyAnswer.user_id == user_id))
    await commit_session(session)


async def answers_for_user(session: AsyncSession, user_id: uuid.UUID) -> list[SurveyAnswerGroup]:
    rows = list(
        (
            await session.execute(
                select(SurveyAnswer)
                .where(SurveyAnswer.user_id == user_id)
                .order_by(SurveyAnswer.created_at)
            )
        ).scalars().all()
    )
    return _group(rows)


async def list_user_surveys(session: AsyncSession, query: str | None) -> list[UserSurveyRead]:
    statement = select(SurveyAnswer, User).join(User, User.id == SurveyAnswer.user_id)
    if query and query.strip():
        term = f"%{query.strip()}%"
        statement = statement.where(User.email.ilike(term) | User.full_name.ilike(term))
    rows = (await session.execute(statement.order_by(User.email, SurveyAnswer.created_at))).all()
    grouped: OrderedDict[uuid.UUID, tuple[User, list[SurveyAnswer]]] = OrderedDict()
    for answer, user in rows:
        bucket = grouped.setdefault(user.id, (user, []))
        bucket[1].append(answer)
    result: list[UserSurveyRead] = []
    for user, answers in grouped.values():
        updated = max((item.updated_at for item in answers), default=None)
        result.append(
            UserSurveyRead(
                user_id=user.id,
                user_email=user.email,
                full_name=user.full_name,
                answers=_group(answers),
                updated_at=updated,
            )
        )
    return result


def _group(rows: list[SurveyAnswer]) -> list[SurveyAnswerGroup]:
    ordered: OrderedDict[str, SurveyAnswerGroup] = OrderedDict()
    for row in rows:
        key = str(row.question_id or row.question_title)
        group = ordered.get(key)
        if group is None:
            ordered[key] = SurveyAnswerGroup(
                question_id=row.question_id,
                question_title=row.question_title,
                question_kind=row.question_kind,
                values=[row.value_text],
            )
        elif row.value_text not in group.values:
            group.values.append(row.value_text)
    return list(ordered.values())


async def _question(session: AsyncSession, question_id: uuid.UUID) -> SurveyQuestion:
    question = (
        await session.execute(
            select(SurveyQuestion)
            .where(SurveyQuestion.id == question_id)
            .options(selectinload(SurveyQuestion.options))
        )
    ).scalar_one_or_none()
    if question is None:
        raise not_found("Question not found")
    question.options = sorted(question.options, key=lambda option: (option.sort_order, option.created_at))
    return question
