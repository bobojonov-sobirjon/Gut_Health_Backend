"""Request dependencies: database session and authenticated user."""

from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session as get_db
from app.core.exceptions import forbidden, unauthorized
from app.core.security import decode_access_token
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)

DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    session: DbSession,
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthorized("Not authenticated")
    user_id = decode_access_token(credentials.credentials)
    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise unauthorized("Not authenticated")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_current_admin(current_user: CurrentUser) -> User:
    if not current_user.is_admin:
        raise forbidden()
    return current_user


CurrentAdmin = Annotated[User, Depends(get_current_admin)]
