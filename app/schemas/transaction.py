from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.schemas.common import PaginationMeta
from app.schemas.money import Amount

TransactionType = Literal["credit", "debit"]

ReferenceId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
]

Description = Annotated[
    str,
    StringConstraints(strip_whitespace=True, max_length=1000),
]


class TransactionCreate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "type": "credit",
                    "amount": "500.00",
                    "description": "Initial deposit",
                    "reference_id": "REF-001",
                }
            ]
        },
    )

    type: TransactionType
    amount: Amount
    description: Description = ""
    reference_id: ReferenceId


class TransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    account_id: UUID
    type: TransactionType
    amount: Amount
    description: str
    reference_id: str
    created_at: datetime


class TransactionListResponse(BaseModel):
    success: Literal[True] = True
    data: list[TransactionResponse]
    pagination: PaginationMeta
