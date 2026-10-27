from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.exceptions import (
    AccountNotFound,
    BalanceLimitExceeded,
    DuplicateTransaction,
    InsufficientBalance,
)
from app.models import Account, Transaction
from app.schemas.common import PaginationMeta
from app.schemas.money import MAX_BALANCE
from app.schemas.transaction import TransactionCreate, TransactionType
from app.services.accounts import get_account_for_update

DUPLICATE_TRANSACTION_CONSTRAINT = "uq_transactions_account_reference"


def constraint_name(exc: IntegrityError) -> str | None:
    diag = getattr(getattr(exc, "orig", None), "diag", None)
    return getattr(diag, "constraint_name", None)


def create_transaction(
    session: Session,
    account_id: UUID,
    payload: TransactionCreate,
) -> Transaction:
    try:
        with session.begin():
            account = get_account_for_update(session, account_id)

            existing = session.scalar(
                select(Transaction.id)
                .where(
                    Transaction.account_id == account_id,
                    Transaction.reference_id == payload.reference_id,
                )
                .limit(1)
            )
            if existing is not None:
                raise DuplicateTransaction(
                    details={
                        "account_id": str(account_id),
                        "reference_id": payload.reference_id,
                    }
                )

            delta = payload.amount if payload.type == "credit" else -payload.amount
            new_balance = account.balance + delta
            if new_balance < 0:
                raise InsufficientBalance(
                    details={
                        "account_id": str(account_id),
                        "balance": format(account.balance, ".2f"),
                        "requested_amount": format(payload.amount, ".2f"),
                    }
                )
            if new_balance > MAX_BALANCE:
                raise BalanceLimitExceeded(
                    details={
                        "account_id": str(account_id),
                        "balance": format(account.balance, ".2f"),
                        "requested_amount": format(payload.amount, ".2f"),
                        "max_balance": format(MAX_BALANCE, ".2f"),
                    }
                )

            transaction = Transaction(
                account_id=account_id,
                type=payload.type,
                amount=payload.amount,
                description=payload.description,
                reference_id=payload.reference_id,
            )
            account.balance = new_balance
            session.add(transaction)
            session.flush()
    except IntegrityError as exc:
        session.rollback()
        if constraint_name(exc) == DUPLICATE_TRANSACTION_CONSTRAINT:
            raise DuplicateTransaction(
                details={
                    "account_id": str(account_id),
                    "reference_id": payload.reference_id,
                }
            ) from exc
        raise

    return transaction


def list_transactions(
    session: Session,
    account_id: UUID,
    *,
    type_filter: TransactionType | None,
    page: int,
    limit: int,
) -> tuple[list[Transaction], PaginationMeta]:
    account = session.get(Account, account_id)
    if account is None:
        raise AccountNotFound(details={"account_id": str(account_id)})

    filters = [Transaction.account_id == account_id]
    if type_filter is not None:
        filters.append(Transaction.type == type_filter)

    total = session.scalar(select(func.count()).select_from(Transaction).where(*filters)) or 0
    transactions = list(
        session.scalars(
            select(Transaction)
            .where(*filters)
            .order_by(Transaction.created_at.desc(), Transaction.id.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        ).all()
    )
    total_pages = (total + limit - 1) // limit if total else 0

    return transactions, PaginationMeta(
        page=page,
        limit=limit,
        total_records=total,
        total_pages=total_pages,
    )
