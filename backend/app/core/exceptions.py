from typing import Any
from fastapi import HTTPException, status


class QUEBETError(HTTPException):
    """Base exception class for all QUEBET AI errors."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(
            status_code=status_code,
            detail={
                "code": code,
                "message": message,
                "details": details or {},
            },
        )


class AuthenticationError(QUEBETError):
    def __init__(self, message: str = "Invalid authentication credentials"):
        super().__init__(
            code="AUTH_INVALID_CREDENTIALS",
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
        )


class PermissionDeniedError(QUEBETError):
    def __init__(self, message: str = "Action not permitted for your subscription plan"):
        super().__init__(
            code="PERMISSION_DENIED",
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
        )


class RateLimitExceededError(QUEBETError):
    def __init__(self, message: str = "Daily generation limit reached for your plan"):
        super().__init__(
            code="RATE_LIMIT_EXCEEDED",
            message=message,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )


class AIServiceError(QUEBETError):
    def __init__(self, message: str = "AI service temporarily unavailable"):
        super().__init__(
            code="AI_SERVICE_UNAVAILABLE",
            message=message,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
