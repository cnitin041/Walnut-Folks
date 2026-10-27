from uuid import UUID

from fastapi import APIRouter, status

from app.dependencies import SessionDep
from app.schemas.account import AccountBalanceResponse, AccountCreate, AccountResponse
from app.schemas.common import ErrorResponse, SuccessResponse
from app.services import accounts as account_service

router = APIRouter(prefix="/accounts", tags=["accounts"])

ERROR_RESPONSES = {
    400: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
}


@router.post(
    "",
    response_model=SuccessResponse[AccountResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create an account",
    responses=ERROR_RESPONSES,
)
def create_account(payload: AccountCreate, session: SessionDep):
    account = account_service.create_account(session, payload.name)
    return {"success": True, "data": account}


@router.get(
    "/{account_id}",
    response_model=SuccessResponse[AccountResponse],
    summary="Retrieve an account",
    responses=ERROR_RESPONSES,
)
def get_account(account_id: UUID, session: SessionDep):
    account = account_service.get_account(session, account_id)
    return {"success": True, "data": account}


@router.get(
    "/{account_id}/balance",
    response_model=SuccessResponse[AccountBalanceResponse],
    summary="Get an account balance",
    responses=ERROR_RESPONSES,
)
def get_balance(account_id: UUID, session: SessionDep):
    balance = account_service.get_balance(session, account_id)
    return {"success": True, "data": {"account_id": account_id, "balance": balance}}
