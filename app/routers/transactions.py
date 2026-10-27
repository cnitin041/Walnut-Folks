from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, status

from app.dependencies import SessionDep
from app.schemas.common import ErrorResponse, SuccessResponse
from app.schemas.transaction import (
    TransactionCreate,
    TransactionListResponse,
    TransactionResponse,
    TransactionType,
)
from app.services import transactions as transaction_service

router = APIRouter(prefix="/accounts", tags=["transactions"])

ERROR_RESPONSES = {
    400: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
}


@router.post(
    "/{account_id}/transactions",
    response_model=SuccessResponse[TransactionResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a credit or debit transaction",
    responses=ERROR_RESPONSES,
)
def create_transaction(
    account_id: UUID,
    payload: TransactionCreate,
    session: SessionDep,
):
    transaction = transaction_service.create_transaction(session, account_id, payload)
    return {"success": True, "data": transaction}


@router.get(
    "/{account_id}/transactions",
    response_model=TransactionListResponse,
    summary="List an account's transaction history",
    responses=ERROR_RESPONSES,
)
def list_transactions(
    account_id: UUID,
    session: SessionDep,
    type: Annotated[
        TransactionType | None,
        Query(description="Filter by ledger entry type."),
    ] = None,
    page: Annotated[
        int,
        Query(ge=1, description="Page number, starting at 1."),
    ] = 1,
    limit: Annotated[
        int,
        Query(ge=1, le=100, description="Page size, maximum 100."),
    ] = 10,
):
    transactions, pagination = transaction_service.list_transactions(
        session,
        account_id,
        type_filter=type,
        page=page,
        limit=limit,
    )
    return {
        "success": True,
        "data": transactions,
        "pagination": pagination,
    }
