from typing import Any


class AppError(Exception):
    status_code = 400
    code = "APP_ERROR"
    message = "Application error."

    def __init__(
        self,
        message: str | None = None,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.message = message or self.message
        self.details = details
        super().__init__(self.message)


class AccountNotFound(AppError):
    status_code = 404
    code = "ACCOUNT_NOT_FOUND"
    message = "Account not found."


class DuplicateTransaction(AppError):
    status_code = 409
    code = "DUPLICATE_TRANSACTION"
    message = "A transaction with this reference_id already exists for the account."


class DuplicateTransfer(AppError):
    status_code = 409
    code = "DUPLICATE_TRANSFER"
    message = "A transfer with this reference_id already exists."


class InsufficientBalance(AppError):
    status_code = 400
    code = "INSUFFICIENT_BALANCE"
    message = "Insufficient balance for this debit transaction."


class BalanceLimitExceeded(AppError):
    status_code = 400
    code = "BALANCE_LIMIT_EXCEEDED"
    message = "The resulting balance exceeds the supported maximum."


class SameAccountTransfer(AppError):
    status_code = 400
    code = "SAME_ACCOUNT_TRANSFER"
    message = "Source and destination accounts must be different."


class InvalidRequest(AppError):
    status_code = 400
    code = "VALIDATION_ERROR"
    message = "The request is invalid."


class ConflictError(AppError):
    status_code = 409
    code = "CONFLICT"
    message = "The request conflicts with the current state."


def error_content(
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return {"success": False, "error": error}
