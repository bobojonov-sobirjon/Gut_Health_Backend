"""Domain errors mapped to JSON responses by the API layer."""


class AppError(Exception):
    """Expected application failure with a stable client-facing code."""

    def __init__(
        self,
        status_code: int,
        detail: str,
        code: str,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self.detail = detail
        self.code = code
        self.headers = headers
        super().__init__(detail)


def unauthorized(detail: str = "Could not validate credentials") -> AppError:
    return AppError(
        status_code=401,
        detail=detail,
        code="unauthorized",
        headers={"WWW-Authenticate": "Bearer"},
    )


def not_found(detail: str) -> AppError:
    return AppError(status_code=404, detail=detail, code="not_found")


def forbidden(detail: str = "Admin access required") -> AppError:
    return AppError(status_code=403, detail=detail, code="forbidden")


def conflict(detail: str) -> AppError:
    return AppError(status_code=409, detail=detail, code="conflict")
