"""Registration, login, and the authenticated profile."""

from fastapi import APIRouter, Response, status

from app.api.deps import CurrentUser, DbSession
from app.core.config import get_settings
from app.models.user import AuthProvider, User
from app.schemas.auth import (
    AuthResponse,
    EmailCodeResponse,
    EmailSendCodeRequest,
    EmailVerifyCodeRequest,
    FirebaseAuthRequest,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserRead,
    UserUpdate,
)
from app.services.auth_service import (
    IssuedTokens,
    authenticate_user,
    delete_account,
    login_with_firebase,
    logout,
    refresh_session,
    register_user,
    send_email_login_code,
    update_profile,
    verify_email_login_code,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _auth_response(user: User, tokens: IssuedTokens) -> AuthResponse:
    return AuthResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        expires_in=tokens.expires_in,
        user=UserRead.model_validate(user),
    )


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, session: DbSession) -> AuthResponse:
    """Create an account and start a session."""

    user, tokens = await register_user(session, payload)
    return _auth_response(user, tokens)


@router.post("/login", response_model=AuthResponse)
async def login(payload: LoginRequest, session: DbSession) -> AuthResponse:
    """Exchange an email and password for a session."""

    user, tokens = await authenticate_user(session, str(payload.email), payload.password)
    return _auth_response(user, tokens)


@router.post("/firebase", response_model=AuthResponse)
async def login_firebase(payload: FirebaseAuthRequest, session: DbSession) -> AuthResponse:
    """Exchange a Firebase ID token from Google, Apple, or email for a session."""

    user, tokens = await login_with_firebase(session, payload.id_token)
    return _auth_response(user, tokens)


@router.post("/google", response_model=AuthResponse)
async def login_google(payload: FirebaseAuthRequest, session: DbSession) -> AuthResponse:
    """Exchange a Firebase ID token that was issued by Google sign-in."""

    user, tokens = await login_with_firebase(
        session,
        payload.id_token,
        expected_provider=AuthProvider.GOOGLE,
    )
    return _auth_response(user, tokens)


@router.post("/apple", response_model=AuthResponse)
async def login_apple(payload: FirebaseAuthRequest, session: DbSession) -> AuthResponse:
    """Exchange a Firebase ID token that was issued by Apple sign-in."""

    user, tokens = await login_with_firebase(
        session,
        payload.id_token,
        expected_provider=AuthProvider.APPLE,
    )
    return _auth_response(user, tokens)


@router.post("/email/send-code", response_model=EmailCodeResponse)
async def send_email_code(payload: EmailSendCodeRequest, session: DbSession) -> EmailCodeResponse:
    """Send a 6-digit sign-in code. The code is included only when DEBUG is true."""

    code = await send_email_login_code(session, str(payload.email))
    return EmailCodeResponse(
        detail="Sign-in code created",
        expires_in=get_settings().email_code_expire_minutes * 60,
        debug_code=code,
    )


@router.post("/email/verify-code", response_model=AuthResponse)
async def verify_email_code(payload: EmailVerifyCodeRequest, session: DbSession) -> AuthResponse:
    """Create or resume an account after a valid email code."""

    user, tokens = await verify_email_login_code(session, str(payload.email), payload.code)
    return _auth_response(user, tokens)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(payload: RefreshRequest, session: DbSession) -> TokenResponse:
    """Rotate a refresh token and return a new token pair."""

    tokens = await refresh_session(session, payload.refresh_token)
    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        expires_in=tokens.expires_in,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout_session(payload: LogoutRequest, session: DbSession) -> Response:
    """Revoke a refresh token."""

    await logout(session, payload.refresh_token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserRead)
async def read_profile(current_user: CurrentUser) -> User:
    """Return the authenticated profile."""

    return current_user


@router.patch("/me", response_model=UserRead)
async def patch_profile(
    payload: UserUpdate,
    current_user: CurrentUser,
    session: DbSession,
) -> User:
    """Update the authenticated profile."""

    return await update_profile(session, current_user, payload)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_profile(current_user: CurrentUser, session: DbSession) -> Response:
    """Delete the signed-in account, diary, devices, and uploads metadata."""

    await delete_account(session, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
