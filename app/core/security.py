"""Password hashing and JSON Web Token helpers."""

import logging
import uuid
from datetime import datetime, timedelta

import jwt
from pwdlib import PasswordHash

from app.core.config import get_settings
from app.core.database import utcnow
from app.core.exceptions import unauthorized

logger = logging.getLogger(__name__)
_hasher = PasswordHash.recommended()
_dummy_hash: str | None = None


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    try:
        return _hasher.verify(password, hashed_password)
    except Exception:
        logger.warning("Password hash verification failed")
        return False


def verify_password_dummy(password: str) -> None:
    """Spend a hash verification when the account does not exist."""

    global _dummy_hash
    if _dummy_hash is None:
        _dummy_hash = hash_password("not-a-real-password")
    verify_password(password, _dummy_hash)


def create_access_token(subject: uuid.UUID) -> tuple[str, int]:
    settings = get_settings()
    expires_in = settings.access_token_expire_minutes * 60
    token = _encode(
        subject=subject,
        token_type="access",
        expires_at=utcnow() + timedelta(seconds=expires_in),
    )
    return token, expires_in


def create_refresh_token(subject: uuid.UUID) -> tuple[str, uuid.UUID, datetime]:
    settings = get_settings()
    jti = uuid.uuid4()
    expires_at = utcnow() + timedelta(days=settings.refresh_token_expire_days)
    token = _encode(
        subject=subject,
        token_type="refresh",
        expires_at=expires_at,
        jti=jti,
    )
    return token, jti, expires_at


def decode_access_token(token: str) -> uuid.UUID:
    payload = _decode(token, expected_type="access")
    return _subject(payload)


def decode_refresh_token(token: str) -> tuple[uuid.UUID, uuid.UUID]:
    payload = _decode(token, expected_type="refresh")
    raw_jti = payload.get("jti")
    if not isinstance(raw_jti, str):
        raise unauthorized("Invalid refresh token")
    try:
        jti = uuid.UUID(raw_jti)
    except ValueError as exc:
        raise unauthorized("Invalid refresh token") from exc
    return _subject(payload), jti


def _encode(
    *,
    subject: uuid.UUID,
    token_type: str,
    expires_at: datetime,
    jti: uuid.UUID | None = None,
) -> str:
    settings = get_settings()
    payload: dict[str, object] = {
        "sub": str(subject),
        "type": token_type,
        "iat": utcnow(),
        "exp": expires_at,
    }
    if jti is not None:
        payload["jti"] = str(jti)
    encoded = jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)
    if isinstance(encoded, bytes):
        return encoded.decode("ascii")
    return encoded


def _decode(token: str, *, expected_type: str) -> dict[str, object]:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", "iat", "sub", "type"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise unauthorized("Token has expired") from exc
    except jwt.InvalidTokenError as exc:
        raise unauthorized("Invalid token") from exc
    if payload.get("type") != expected_type:
        raise unauthorized("Invalid token type")
    return payload


def _subject(payload: dict[str, object]) -> uuid.UUID:
    raw_subject = payload.get("sub")
    if not isinstance(raw_subject, str):
        raise unauthorized("Invalid token")
    try:
        return uuid.UUID(raw_subject)
    except ValueError as exc:
        raise unauthorized("Invalid token") from exc
