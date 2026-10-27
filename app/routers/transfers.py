from fastapi import APIRouter, status

from app.dependencies import SessionDep
from app.schemas.common import ErrorResponse, SuccessResponse
from app.schemas.transfer import TransferCreate, TransferResponse
from app.services import transfers as transfer_service

router = APIRouter(prefix="/transfers", tags=["transfers"])

ERROR_RESPONSES = {
    400: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
}


@router.post(
    "",
    response_model=SuccessResponse[TransferResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Transfer funds atomically between two accounts",
    responses=ERROR_RESPONSES,
)
def create_transfer(payload: TransferCreate, session: SessionDep):
    result = transfer_service.create_transfer(session, payload)
    transfer = result.transfer
    return {
        "success": True,
        "data": {
            "id": transfer.id,
            "source_account_id": transfer.source_account_id,
            "destination_account_id": transfer.destination_account_id,
            "amount": transfer.amount,
            "description": transfer.description,
            "reference_id": transfer.reference_id,
            "created_at": transfer.created_at,
            "debit_transaction_id": result.debit_transaction.id,
            "credit_transaction_id": result.credit_transaction.id,
        },
    }
