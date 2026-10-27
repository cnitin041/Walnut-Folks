from typing import Any, Literal

from pydantic import BaseModel, Field


class SuccessResponse[T](BaseModel):
    success: Literal[True] = True
    data: T


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | None = None


class ErrorResponse(BaseModel):
    success: Literal[False] = False
    error: ErrorBody


class PaginationMeta(BaseModel):
    page: int = Field(ge=1)
    limit: int = Field(ge=1)
    total_records: int = Field(ge=0)
    total_pages: int = Field(ge=0)


class HealthResponse(BaseModel):
    status: str
    database: str
