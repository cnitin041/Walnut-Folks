from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.schemas.money import Amount

Description = Annotated[
    str,
    StringConstraints(strip_whitespace=True, max_length=1000),
]

ReferenceId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
]


class TransferCreate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "source_account_id": "00000000-0000-0000-0000-000000000001",
                    "destination_account_id": "00000000-0000-0000-0000-000000000002",
                    "amount": "100.00",
                    "reference_id": "TRANSFER-001",
                    "description": "Payment",
                }
            ]
        },
    )

    source_account_id: UUID
    destination_account_id: UUID
    amount: Amount
    description: Description = ""
    reference_id: ReferenceId


class TransferResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source_account_id: UUID
    destination_account_id: UUID
    amount: Amount
    description: str
    reference_id: str
    created_at: datetime
    debit_transaction_id: UUID
    credit_transaction_id: UUID
