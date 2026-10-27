from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.exceptions import (
    BalanceLimitExceeded,
    DuplicateTransfer,
    InsufficientBalance,
    SameAccountTransfer,
)
from app.models import Account, Transaction, Transfer
from app.schemas.money import MAX_BALANCE
from app.schemas.transfer import TransferCreate
from app.services.accounts import get_account_for_update
from app.services.transactions import constraint_name

DUPLICATE_TRANSFER_CONSTRAINT = "uq_transfers_reference_id"


@dataclass(frozen=True)
class TransferResult:
    transfer: Transfer
    debit_transaction: Transaction
    credit_transaction: Transaction


def _lock_accounts(session: Session, account_ids: set[UUID]) -> dict[UUID, Account]:
    accounts = {}
    for account_id in sorted(account_ids, key=str):
        accounts[account_id] = get_account_for_update(session, account_id)
    return accounts


def create_transfer(session: Session, payload: TransferCreate) -> TransferResult:
    if payload.source_account_id == payload.destination_account_id:
        raise SameAccountTransfer(details={"account_id": str(payload.source_account_id)})

    try:
        with session.begin():
            accounts = _lock_accounts(
                session,
                {payload.source_account_id, payload.destination_account_id},
            )
            source = accounts[payload.source_account_id]
            destination = accounts[payload.destination_account_id]

            existing = session.scalar(
                select(Transfer.id).where(Transfer.reference_id == payload.reference_id).limit(1)
            )
            if existing is not None:
                raise DuplicateTransfer(details={"reference_id": payload.reference_id})

            new_source_balance = source.balance - payload.amount
            if new_source_balance < 0:
                raise InsufficientBalance(
                    details={
                        "account_id": str(source.id),
                        "balance": format(source.balance, ".2f"),
                        "requested_amount": format(payload.amount, ".2f"),
                    }
                )

            new_destination_balance = destination.balance + payload.amount
            if new_destination_balance > MAX_BALANCE:
                raise BalanceLimitExceeded(
                    details={
                        "account_id": str(destination.id),
                        "balance": format(destination.balance, ".2f"),
                        "requested_amount": format(payload.amount, ".2f"),
                        "max_balance": format(MAX_BALANCE, ".2f"),
                    }
                )

            transfer = Transfer(
                source_account_id=source.id,
                destination_account_id=destination.id,
                amount=payload.amount,
                reference_id=payload.reference_id,
                description=payload.description,
            )
            session.add(transfer)
            session.flush()

            debit_transaction = Transaction(
                account_id=source.id,
                transfer_id=transfer.id,
                type="debit",
                amount=payload.amount,
                description=payload.description,
                reference_id=f"transfer:{transfer.id}:debit",
            )
            credit_transaction = Transaction(
                account_id=destination.id,
                transfer_id=transfer.id,
                type="credit",
                amount=payload.amount,
                description=payload.description,
                reference_id=f"transfer:{transfer.id}:credit",
            )
            source.balance = new_source_balance
            destination.balance = new_destination_balance
            session.add_all([debit_transaction, credit_transaction])
            session.flush()
    except IntegrityError as exc:
        session.rollback()
        if constraint_name(exc) == DUPLICATE_TRANSFER_CONSTRAINT:
            raise DuplicateTransfer(details={"reference_id": payload.reference_id}) from exc
        raise

    return TransferResult(
        transfer=transfer,
        debit_transaction=debit_transaction,
        credit_transaction=credit_transaction,
    )
