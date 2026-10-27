import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.exceptions import AppError, error_content
from app.routers import accounts, health, transactions, transfers

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description=(
        "A transaction ledger API with atomic credit/debit processing, "
        "immutable ledger entries, duplicate protection, and atomic transfers."
    ),
)

app.include_router(health.router)
app.include_router(accounts.router, prefix="/api/v1")
app.include_router(transactions.router, prefix="/api/v1")
app.include_router(transfers.router, prefix="/api/v1")


@app.get("/", include_in_schema=False)
def root() -> dict[str, str]:
    return {"name": settings.app_name, "docs": "/docs", "health": "/health"}


@app.exception_handler(AppError)
async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=error_content(exc.code, exc.message, exc.details),
    )


def _validation_code(loc: tuple[Any, ...]) -> str:
    if loc and loc[0] == "query":
        if len(loc) > 1 and loc[1] in {"page", "limit"}:
            return "INVALID_PAGINATION"
        if len(loc) > 1 and loc[1] == "type":
            return "INVALID_TRANSACTION_TYPE"
    if loc and loc[0] == "path":
        if len(loc) > 1 and loc[1] == "account_id":
            return "INVALID_ACCOUNT_ID"
        return "INVALID_UUID"
    if loc and loc[0] == "body" and len(loc) > 1:
        if loc[1] == "amount":
            return "INVALID_AMOUNT"
        if loc[1] == "type":
            return "INVALID_TRANSACTION_TYPE"
        if loc[1] == "reference_id":
            return "INVALID_REFERENCE_ID"
        if loc[1] in {"source_account_id", "destination_account_id"}:
            return "INVALID_ACCOUNT_ID"
    return "VALIDATION_ERROR"


@app.exception_handler(RequestValidationError)
async def handle_validation_error(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    errors: list[dict[str, str]] = []
    codes: list[str] = []

    for error in exc.errors():
        loc = tuple(error.get("loc", ()))
        if loc and loc[0] in {"body", "query", "path"}:
            field = ".".join(str(part) for part in loc[1:])
        else:
            field = ".".join(str(part) for part in loc)
        message = error.get("msg", "Invalid value")
        if message.startswith("Value error, "):
            message = message.removeprefix("Value error, ")
        errors.append(
            {
                "field": field,
                "message": message,
                "type": error.get("type", "validation_error"),
            }
        )
        codes.append(_validation_code(loc))

    code = next((item for item in codes if item != "VALIDATION_ERROR"), "VALIDATION_ERROR")
    return JSONResponse(
        status_code=422,
        content=error_content(
            code,
            "Request validation failed.",
            {"errors": errors},
        ),
    )


@app.exception_handler(StarletteHTTPException)
async def handle_http_error(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    code = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}.get(
        exc.status_code,
        "HTTP_ERROR",
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=error_content(code, str(exc.detail)),
    )


@app.exception_handler(IntegrityError)
async def handle_integrity_error(request: Request, exc: IntegrityError) -> JSONResponse:
    logger.exception("Database integrity error")
    return JSONResponse(
        status_code=409,
        content=error_content(
            "CONFLICT",
            "The request conflicts with the current state.",
        ),
    )


@app.exception_handler(SQLAlchemyError)
async def handle_database_error(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    logger.exception("Database error")
    return JSONResponse(
        status_code=500,
        content=error_content("DATABASE_ERROR", "A database error occurred."),
    )


@app.exception_handler(Exception)
async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error")
    return JSONResponse(
        status_code=500,
        content=error_content("INTERNAL_ERROR", "An unexpected error occurred."),
    )
