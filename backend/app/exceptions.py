"""Domain exceptions mapped to HTTP responses in ``app.main``."""


class AppError(Exception):
    status_code = 400
    code = "APP_ERROR"

    def __init__(self, message: str, code: str = "") -> None:
        super().__init__(message)
        self.message = message
        if code:
            self.code = code


class AuthenticationError(AppError):
    status_code = 401
    code = "AUTHENTICATION_FAILED"


class ForbiddenError(AppError):
    status_code = 403
    code = "FORBIDDEN"


class NotFoundError(AppError):
    status_code = 404
    code = "NOT_FOUND"


class ConflictError(AppError):
    status_code = 409
    code = "CONFLICT"


class BusinessRuleError(AppError):
    status_code = 422
    code = "BUSINESS_RULE_VIOLATION"
