from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.exceptions import AccountNotFound
from app.models import Account


def create_account(session: Session, name: str) -> Account:
    account = Account(name=name, balance=Decimal("0.00"))
    try:
        session.add(account)
        session.commit()
        return account
    except Exception:
        session.rollback()
        raise


def get_account(session: Session, account_id: UUID) -> Account:
    account = session.get(Account, account_id)
    if account is None:
        raise AccountNotFound(details={"account_id": str(account_id)})
    return account


def get_account_for_update(session: Session, account_id: UUID) -> Account:
    account = session.scalar(select(Account).where(Account.id == account_id).with_for_update())
    if account is None:
        raise AccountNotFound(details={"account_id": str(account_id)})
    return account


def get_balance(session: Session, account_id: UUID) -> Decimal:
    return get_account(session, account_id).balance
