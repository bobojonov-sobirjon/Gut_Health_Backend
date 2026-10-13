"""Firebase Admin token checks for Google, Apple, and email sign-in."""

import logging
from dataclasses import dataclass

import firebase_admin
from firebase_admin import auth, credentials

from app.core.config import get_settings
from app.core.exceptions import AppError, unauthorized
from app.models.user import AuthProvider

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class FirebaseIdentity:
    uid: str
    email: str | None
    email_verified: bool
    name: str | None
    sign_in_provider: str


def verify_firebase_id_token(id_token: str) -> FirebaseIdentity:
    _ensure_app()
    try:
        decoded = auth.verify_id_token(id_token, check_revoked=True)
    except Exception as exc:
        logger.warning("Firebase token was rejected (%s)", type(exc).__name__)
        raise unauthorized("Invalid Firebase token") from exc

    firebase_claims = decoded.get("firebase") or {}
    identities = firebase_claims.get("identities") or {}
    email = decoded.get("email")
    if not isinstance(email, str) or not email.strip():
        identity_emails = identities.get("email") or []
        email = identity_emails[0] if identity_emails else None
    if isinstance(email, str):
        email = email.strip().lower()
    name = decoded.get("name")
    provider = firebase_claims.get("sign_in_provider")
    uid = decoded.get("uid") or decoded.get("sub")
    if not isinstance(uid, str) or not isinstance(provider, str):
        raise unauthorized("Invalid Firebase token")
    return FirebaseIdentity(
        uid=uid,
        email=email,
        email_verified=bool(decoded.get("email_verified")),
        name=name.strip() if isinstance(name, str) and name.strip() else None,
        sign_in_provider=provider,
    )


def provider_from_firebase(sign_in_provider: str) -> AuthProvider:
    if sign_in_provider == "google.com":
        return AuthProvider.GOOGLE
    if sign_in_provider == "apple.com":
        return AuthProvider.APPLE
    if sign_in_provider in {"password", "emailLink", "email"}:
        return AuthProvider.EMAIL
    raise AppError(400, "This Firebase sign-in provider is not supported", "unsupported_provider")


def _ensure_app() -> None:
    settings = get_settings()
    if not settings.firebase_enabled:
        raise AppError(503, "Firebase is not configured", "firebase_not_configured")
    try:
        firebase_admin.get_app()
        return
    except ValueError:
        pass
    firebase_admin.initialize_app(credentials.Certificate(_certificate()))


def _certificate() -> dict[str, str]:
    settings = get_settings()
    return {
        "type": settings.firebase_type or "service_account",
        "project_id": settings.firebase_project_id,
        "private_key_id": settings.firebase_private_key_id,
        "private_key": settings.firebase_private_key,
        "client_email": settings.firebase_client_email,
        "client_id": settings.firebase_client_id,
        "auth_uri": settings.firebase_auth_uri,
        "token_uri": settings.firebase_token_uri,
        "auth_provider_x509_cert_url": settings.firebase_auth_provider_x509_cert_url,
        "client_x509_cert_url": settings.firebase_client_x509_cert_url,
        "universe_domain": settings.firebase_universe_domain,
    }
