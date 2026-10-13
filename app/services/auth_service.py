"""Account registration, refresh sessions, and profile updates."""

import asyncio
import hashlib
import hmac
import logging
import secrets
import smtplib
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import commit_session, utcnow
from app.core.exceptions import AppError, conflict, unauthorized
from app.core.firebase import FirebaseIdentity, provider_from_firebase, verify_firebase_id_token
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    verify_password,
    verify_password_dummy,
)
from app.models.user import AuthProvider, EmailLoginCode, RefreshToken, User
from app.schemas.auth import RegisterRequest, UserUpdate

logger = logging.getLogger(__name__)

_EMAIL_CONFLICTS = {
    "uq_users_email": "An account with this email already exists",
}


@dataclass(frozen=True, slots=True)
class IssuedTokens:
    access_token: str
    refresh_token: str
    expires_in: int


async def register_user(
    session: AsyncSession,
    payload: RegisterRequest,
) -> tuple[User, IssuedTokens]:
    existing = await _get_user_by_email(session, payload.email)
    if existing is not None:
        raise conflict("An account with this email already exists")

    user = User(
        email=str(payload.email),
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        auth_provider=AuthProvider.EMAIL,
    )
    session.add(user)
    await session.flush()
    tokens = await _issue_tokens(session, user)
    await commit_session(session, _EMAIL_CONFLICTS)
    return user, tokens


async def authenticate_user(
    session: AsyncSession,
    email: str,
    password: str,
) -> tuple[User, IssuedTokens]:
    user = await _get_user_by_email(session, email)
    if user is None or not user.is_active or user.hashed_password is None:
        verify_password_dummy(password)
        raise unauthorized("Invalid email or password")
    if not verify_password(password, user.hashed_password):
        raise unauthorized("Invalid email or password")

    tokens = await _issue_tokens(session, user)
    await commit_session(session)
    return user, tokens


async def login_admin(session: AsyncSession, email: str, password: str) -> tuple[User, IssuedTokens]:
    """Sign in the configured administrator, creating that account on first use."""

    settings = get_settings()
    if not settings.admin_email or not settings.admin_password:
        raise AppError(503, "Admin login is not configured", "admin_not_configured")
    if email != settings.admin_email.strip().lower():
        verify_password_dummy(password)
        raise unauthorized("Invalid email or password")

    user = await _get_user_by_email(session, email)
    try:
        env_match = secrets.compare_digest(password, settings.admin_password)
    except (TypeError, ValueError):
        env_match = False
    stored_match = bool(
        user and user.hashed_password and verify_password(password, user.hashed_password)
    )
    if user is None:
        if not env_match:
            verify_password_dummy(password)
            raise unauthorized("Invalid email or password")
        user = User(
            email=email,
            hashed_password=hash_password(password),
            full_name="Administrator",
            auth_provider=AuthProvider.EMAIL,
            is_admin=True,
        )
        session.add(user)
        await session.flush()
    elif env_match:
        user.is_admin = True
        user.is_active = True
        if not stored_match:
            user.hashed_password = hash_password(password)
    elif not (stored_match and user.is_admin and user.is_active):
        raise unauthorized("Invalid email or password")

    tokens = await _issue_tokens(session, user)
    await commit_session(session, _EMAIL_CONFLICTS)
    return user, tokens


async def refresh_session(session: AsyncSession, raw_token: str) -> IssuedTokens:
    user_id, jti = decode_refresh_token(raw_token)
    token_row = await session.get(RefreshToken, jti)
    if token_row is None or token_row.user_id != user_id:
        raise unauthorized("Invalid refresh token")
    if token_row.revoked_at is not None:
        logger.warning(
            "Revoked refresh token reused for user %s; revoking all sessions",
            user_id,
        )
        await _revoke_all(session, user_id)
        await commit_session(session)
        raise unauthorized("Refresh token has been revoked")
    if _as_utc(token_row.expires_at) <= utcnow():
        raise unauthorized("Refresh token has expired")

    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise unauthorized("Invalid refresh token")

    token_row.revoked_at = utcnow()
    tokens = await _issue_tokens(session, user)
    await commit_session(session)
    return tokens


async def logout(session: AsyncSession, raw_token: str) -> None:
    user_id, jti = decode_refresh_token(raw_token)
    token_row = await session.get(RefreshToken, jti)
    if token_row is None or token_row.user_id != user_id:
        raise unauthorized("Invalid refresh token")
    if token_row.revoked_at is None:
        token_row.revoked_at = utcnow()
        await commit_session(session)


async def login_with_firebase(
    session: AsyncSession,
    id_token: str,
    *,
    expected_provider: AuthProvider | None = None,
) -> tuple[User, IssuedTokens]:
    identity = await asyncio.to_thread(verify_firebase_id_token, id_token)
    provider = provider_from_firebase(identity.sign_in_provider)
    if expected_provider is not None and provider is not expected_provider:
        raise unauthorized("This Firebase token does not match the requested provider")
    user = await _upsert_firebase_user(session, identity, provider)
    tokens = await _issue_tokens(session, user)
    await commit_session(session, _EMAIL_CONFLICTS)
    return user, tokens


async def send_email_login_code(session: AsyncSession, email: str) -> str | None:
    """Store a 6-digit code. Returns the code only when DEBUG is enabled."""

    settings = get_settings()
    if not settings.debug and not settings.smtp_enabled:
        raise AppError(
            503,
            "Email delivery is not configured. Set SMTP_HOST and SMTP_FROM.",
            "email_not_configured",
        )

    latest = await _latest_code(session, email)
    if latest is not None and latest.consumed_at is None:
        cooldown_end = latest.created_at + timedelta(seconds=60)
        if cooldown_end > utcnow():
            raise AppError(429, "Wait a minute before requesting another code", "too_many_requests")

    code = f"{secrets.randbelow(1_000_000):06d}"
    session.add(
        EmailLoginCode(
            email=email,
            code_hash=_hash_login_code(email, code),
            expires_at=utcnow() + timedelta(minutes=settings.email_code_expire_minutes),
        )
    )
    await commit_session(session)
    if settings.smtp_enabled:
        try:
            await asyncio.to_thread(_send_code_email, email, code)
        except Exception as exc:
            logger.exception("Sign-in email failed")
            raise AppError(502, "The sign-in email could not be sent", "email_failed") from exc
    if settings.debug:
        return code
    return None


async def verify_email_login_code(
    session: AsyncSession,
    email: str,
    code: str,
) -> tuple[User, IssuedTokens]:
    row = await _active_code(session, email)
    if row is None:
        raise unauthorized("Invalid or expired code")
    row.attempt_count += 1
    if not hmac.compare_digest(row.code_hash, _hash_login_code(email, code)):
        if row.attempt_count >= 5:
            row.consumed_at = utcnow()
        await commit_session(session)
        raise unauthorized("Invalid or expired code")

    row.consumed_at = utcnow()
    user = await _get_user_by_email(session, email)
    if user is None:
        user = User(email=email, hashed_password=None, auth_provider=AuthProvider.EMAIL)
        session.add(user)
        await session.flush()
    elif not user.is_active:
        raise unauthorized("Invalid or expired code")
    tokens = await _issue_tokens(session, user)
    await commit_session(session, _EMAIL_CONFLICTS)
    return user, tokens


async def update_profile(
    session: AsyncSession,
    user: User,
    payload: UserUpdate,
) -> User:
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(user, key, value)
    await commit_session(session)
    return user


async def _issue_tokens(session: AsyncSession, user: User) -> IssuedTokens:
    access_token, expires_in = create_access_token(user.id)
    refresh_token, jti, expires_at = create_refresh_token(user.id)
    session.add(RefreshToken(jti=jti, user_id=user.id, expires_at=expires_at))
    await session.flush()
    return IssuedTokens(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
    )


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


async def _get_user_by_email(session: AsyncSession, email: str) -> User | None:
    statement = select(User).where(User.email == email)
    return (await session.execute(statement)).scalar_one_or_none()


async def _revoke_all(session: AsyncSession, user_id: uuid.UUID) -> None:
    statement = (
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )
    await session.execute(statement)


async def _upsert_firebase_user(
    session: AsyncSession,
    identity: FirebaseIdentity,
    provider: AuthProvider,
) -> User:
    statement = select(User).where(User.provider_subject == identity.uid)
    user = (await session.execute(statement)).scalar_one_or_none()
    if user is None and identity.email:
        existing = await _get_user_by_email(session, identity.email)
        if existing is not None:
            if not identity.email_verified:
                raise unauthorized("Verify this email in Firebase before linking the account")
            if existing.provider_subject and existing.provider_subject != identity.uid:
                raise conflict("This email is already linked to another sign-in")
            user = existing
    if user is None:
        if not identity.email:
            raise AppError(400, "The Firebase account did not include an email", "email_required")
        user = User(
            email=identity.email,
            hashed_password=None,
            full_name=identity.name,
            auth_provider=provider,
            provider_subject=identity.uid,
        )
        session.add(user)
    else:
        if not user.is_active:
            raise unauthorized("This account is disabled")
        user.provider_subject = identity.uid
        user.auth_provider = provider
        if identity.name and not user.full_name:
            user.full_name = identity.name
        if identity.email and identity.email_verified and user.email != identity.email:
            user.email = identity.email
    await session.flush()
    return user


async def _latest_code(session: AsyncSession, email: str) -> EmailLoginCode | None:
    statement = (
        select(EmailLoginCode)
        .where(EmailLoginCode.email == email)
        .order_by(EmailLoginCode.created_at.desc())
        .limit(1)
    )
    return (await session.execute(statement)).scalar_one_or_none()


async def _active_code(session: AsyncSession, email: str) -> EmailLoginCode | None:
    statement = (
        select(EmailLoginCode)
        .where(
            EmailLoginCode.email == email,
            EmailLoginCode.consumed_at.is_(None),
            EmailLoginCode.expires_at > utcnow(),
        )
        .order_by(EmailLoginCode.created_at.desc())
        .limit(1)
    )
    return (await session.execute(statement)).scalar_one_or_none()


def _hash_login_code(email: str, code: str) -> str:
    payload = f"{email}:{code}".encode()
    return hmac.new(get_settings().secret_key.encode(), payload, hashlib.sha256).hexdigest()


def _send_code_email(email: str, code: str) -> None:
    settings = get_settings()
    message = EmailMessage()
    message["Subject"] = "Your Gut Health Tracker sign-in code"
    message["From"] = settings.smtp_from
    message["To"] = email
    message.set_content(
        f"Your sign-in code is {code}. It expires in {settings.email_code_expire_minutes} minutes."
    )
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as smtp:
        if settings.smtp_tls:
            smtp.starttls()
        if settings.smtp_user:
            smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.send_message(message)
