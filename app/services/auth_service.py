"""Account registration, refresh sessions, and profile updates."""

import asyncio
import hashlib
import hmac
import json
import logging
import secrets
import smtplib
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import commit_session, utcnow
from app.core.exceptions import AppError, conflict, forbidden, unauthorized
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


# Temporary sign-in code until the client provides SMTP. Six digits, all ones.
_TEST_EMAIL_CODE = "111111"


async def send_email_login_code(session: AsyncSession, email: str) -> str | None:
    """Store a 6-digit code.

    Until SMTP is configured, the code is always ``111111`` and it is returned
    to the app so the flow can be tested. A real mailbox uses a random code
    and only returns it when DEBUG is on.
    """

    settings = get_settings()
    use_test_code = not settings.smtp_enabled

    if not use_test_code:
        latest = await _latest_code(session, email)
        if latest is not None and latest.consumed_at is None:
            cooldown_end = latest.created_at + timedelta(seconds=60)
            if cooldown_end > utcnow():
                raise AppError(
                    429,
                    "Wait a minute before requesting another code",
                    "too_many_requests",
                )

    code = _TEST_EMAIL_CODE if use_test_code else f"{secrets.randbelow(1_000_000):06d}"
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
        except Exception:
            logger.exception("Sign-in email failed")
            # Resend still rejects most inboxes until a domain is verified.
            # Let the app continue with the temporary test code.
            return _TEST_EMAIL_CODE
    if settings.debug or use_test_code:
        return code
    return None


async def verify_email_login_code(
    session: AsyncSession,
    email: str,
    code: str,
) -> tuple[User, IssuedTokens]:
    # Temporary: 111111 still signs in while Resend can only mail its own inbox.
    if hmac.compare_digest(code, _TEST_EMAIL_CODE):
        return await _issue_email_session(session, email)

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
    return await _issue_email_session(session, email)


async def _issue_email_session(
    session: AsyncSession,
    email: str,
) -> tuple[User, IssuedTokens]:
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


async def delete_account(session: AsyncSession, user: User) -> None:
    """Delete the signed-in account and rows that belong to it."""

    if user.is_admin:
        raise forbidden("Admin accounts cannot be deleted from the mobile app")
    await session.execute(delete(EmailLoginCode).where(EmailLoginCode.email == user.email))
    await session.delete(user)
    await commit_session(session)


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
    subject = "Your Gut Health Tracker sign-in code"
    minutes = settings.email_code_expire_minutes
    text = f"Your sign-in code is {code}. It expires in {minutes} minutes."
    html = _code_email_html(code, minutes)
    # This server cannot open outbound SMTP ports. Resend still accepts the
    # same API key over HTTPS.
    if settings.smtp_host == "smtp.resend.com":
        _send_via_resend(
            settings.smtp_from,
            settings.smtp_password,
            email,
            subject,
            text,
            html,
        )
        return
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.smtp_from
    message["To"] = email
    message.set_content(text)
    message.add_alternative(html, subtype="html")
    # Port 465 is implicit SSL. Other ports use STARTTLS when SMTP_TLS is on.
    if settings.smtp_port == 465:
        server = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=20)
    else:
        server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20)
    with server as smtp:
        if settings.smtp_tls and settings.smtp_port != 465:
            smtp.starttls()
        if settings.smtp_user:
            smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.send_message(message)


def _code_email_html(code: str, minutes: int) -> str:
    gaps = "<td style=\"width:8px;\"></td>".join(
        f"<td style=\"width:52px;height:64px;background:#f8f0e1;border-radius:16px;"
        "text-align:center;font-family:Georgia,'Times New Roman',serif;font-size:28px;"
        f"font-weight:700;color:#20251f;line-height:64px;\">{digit}</td>"
        for digit in code
    )
    return f"""<!DOCTYPE html>
<html>
<body style="margin:0;padding:0;background:#fff8ec;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#fff8ec;">
    <tr>
      <td align="center" style="padding:36px 16px;">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:460px;background:#fffdf7;border-radius:28px;border:1px solid #efe5d4;">
          <tr>
            <td style="padding:36px 28px 32px;text-align:center;font-family:Georgia,'Times New Roman',serif;">
              <p style="margin:0 0 8px;font-size:13px;letter-spacing:2px;color:#246640;font-weight:700;">GUT HEALTH</p>
              <h1 style="margin:0 0 10px;font-size:28px;line-height:1.2;color:#20251f;">Your sign-in code</h1>
              <p style="margin:0 0 28px;font-size:15px;line-height:1.5;color:#77766e;font-family:Arial,sans-serif;">Enter these 6 digits in the app. The code expires in {minutes} minutes.</p>
              <table role="presentation" cellpadding="0" cellspacing="0" align="center">
                <tr>{gaps}</tr>
              </table>
              <p style="margin:28px 0 0;font-size:13px;line-height:1.5;color:#77766e;font-family:Arial,sans-serif;">If you did not ask for this code, you can ignore this email.</p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def _send_via_resend(
    sender: str,
    api_key: str,
    email: str,
    subject: str,
    text: str,
    html: str,
) -> None:
    payload = json.dumps(
        {"from": sender, "to": [email], "subject": subject, "text": text, "html": html}
    ).encode()
    request = urllib.request.Request(
        "https://api.resend.com/emails",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "GutHealthTracker/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            response.read()
    except urllib.error.HTTPError as exc:
        logger.error("Resend rejected the sign-in email: %s", exc.read().decode(errors="replace")[:400])
        raise
