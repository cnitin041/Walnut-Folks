from collections import defaultdict
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Account, Transaction
from tests.helpers import create_account, create_transaction


def test_stored_balances_match_the_ledger(
    client: TestClient,
    db_session: Session,
) -> None:
    first = create_account(client, "First")
    second = create_account(client, "Second")
    third = create_account(client, "Third")

    create_transaction(client, first["id"], amount="500.00", reference_id="CREDIT-1")
    create_transaction(client, second["id"], amount="50.00", reference_id="CREDIT-2")
    create_transaction(
        client,
        second["id"],
        type_="debit",
        amount="20.00",
        reference_id="DEBIT-1",
    )
    create_transaction(client, third["id"], amount="75.50", reference_id="CREDIT-3")

    transfers = [
        (first["id"], second["id"], "100.00", "TRANSFER-1"),
        (second["id"], third["id"], "25.00", "TRANSFER-2"),
        (third["id"], first["id"], "10.50", "TRANSFER-3"),
    ]
    for source, destination, amount, reference in transfers:
        response = client.post(
            "/api/v1/transfers",
            json={
                "source_account_id": source,
                "destination_account_id": destination,
                "amount": amount,
                "reference_id": reference,
            },
        )
        assert response.status_code == 201, response.text

    failed_debit = client.post(
        f"/api/v1/accounts/{second['id']}/transactions",
        json={"type": "debit", "amount": "999.00", "reference_id": "FAILED-1"},
    )
    assert failed_debit.status_code == 400

    failed_transfer = client.post(
        "/api/v1/transfers",
        json={
            "source_account_id": second["id"],
            "destination_account_id": first["id"],
            "amount": "999.00",
            "reference_id": "FAILED-TRANSFER",
        },
    )
    assert failed_transfer.status_code == 400

    totals = db_session.execute(
        select(
            Transaction.account_id,
            Transaction.type,
            func.sum(Transaction.amount),
        ).group_by(Transaction.account_id, Transaction.type)
    ).all()
    derived = defaultdict(lambda: Decimal("0.00"))
    for account_id, transaction_type, total in totals:
        if transaction_type == "credit":
            derived[account_id] += total
        else:
            derived[account_id] -= total

    accounts = list(db_session.scalars(select(Account)).all())
    assert len(accounts) == 3
    for account in accounts:
        assert account.balance == derived[account.id]
        assert account.balance >= 0

    transfer_totals = dict(
        db_session.execute(
            select(Transaction.type, func.sum(Transaction.amount))
            .where(Transaction.transfer_id.is_not(None))
            .group_by(Transaction.type)
        ).all()
    )
    assert transfer_totals["debit"] == transfer_totals["credit"]
