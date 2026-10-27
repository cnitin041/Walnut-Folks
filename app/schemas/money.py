from decimal import Decimal
from typing import Annotated, Any

from pydantic import BeforeValidator, Field, PlainSerializer

MAX_BALANCE = Decimal("9999999999999999.99")


def reject_float(value: Any) -> Any:
    if isinstance(value, float):
        raise ValueError("must be provided as a decimal string or integer")
    return value


Amount = Annotated[
    Decimal,
    BeforeValidator(reject_float),
    Field(gt=0, max_digits=18, decimal_places=2),
    PlainSerializer(lambda value: format(value, ".2f"), return_type=str),
]

Balance = Annotated[
    Decimal,
    BeforeValidator(reject_float),
    Field(ge=0, max_digits=18, decimal_places=2),
    PlainSerializer(lambda value: format(value, ".2f"), return_type=str),
]
