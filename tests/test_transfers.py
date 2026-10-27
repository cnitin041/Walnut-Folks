from decimal import Decimal
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select
from sqlalchemy.orm import Session

from app.models import Account, Transaction, Transfer
from tests.helpers import assert_error, create_account, create_transaction, get_balance


def _transfer(
    client: TestClient,
    source_id: str,
    destination_id: str,
    *,
    amount: str = "100.00",
    reference_id: str = "TRANSFER-001",
    description: str = "Payment",
):
    return client.post(
        "/api/v1/transfers",
        json={
            "source_account_id": source_id,
            "destination_account_id": destination_id,
            "amount": amount,
            "reference_id": reference_id,
            "description": description,
        },
    )


def test_successful_transfer_updates_both_balances_and_ledger(
    client: TestClient,
    db_session: Session,
) -> None:
    source = create_account(client, "Source")
    destination = create_account(client, "Destination")
    create_transaction(client, source["id"], amount="500.00", reference_id="REF-1")

    response = _transfer(client, source["id"], destination["id"])

    assert response.status_code == 201, response.text
    data = response.json()["data"]
    assert data["source_account_id"] == source["id"]
    assert data["destination_account_id"] == destination["id"]
    assert data["amount"] == "100.00"
    assert data["description"] == "Payment"
    assert data["reference_id"] == "TRANSFER-001"
    assert get_balance(client, source["id"]) == "400.00"
    assert get_balance(client, destination["id"]) == "100.00"

    transfer_id = UUID(data["id"])
    entries = list(
        db_session.scalars(
            select(Transaction)
            .where(Transaction.transfer_id == transfer_id)
            .order_by(Transaction.type)
        ).all()
    )
    assert len(entries) == 2
    entries_by_type = {entry.type: entry for entry in entries}
    debit = entries_by_type["debit"]
    credit = entries_by_type["credit"]
    assert debit.type == "debit"
    assert debit.account_id == UUID(source["id"])
    assert debit.amount == Decimal("100.00")
    assert credit.type == "credit"
    assert credit.account_id == UUID(destination["id"])
    assert credit.amount == Decimal("100.00")
    assert data["debit_transaction_id"] == str(debit.id)
    assert data["credit_transaction_id"] == str(credit.id)

    source_history = client.get(f"/api/v1/accounts/{source['id']}/transactions").json()["data"]
    destination_history = client.get(f"/api/v1/accounts/{destination['id']}/transactions").json()[
        "data"
    ]
    assert source_history[0]["reference_id"] == f"transfer:{transfer_id}:debit"
    assert destination_history[0]["reference_id"] == f"transfer:{transfer_id}:credit"


def test_transfer_with_unknown_source_returns_404(client: TestClient) -> None:
    destination = create_account(client, "Destination")

    response = _transfer(
        client,
        "00000000-0000-0000-0000-000000000000",
        destination["id"],
    )

    body = assert_error(response, 404, "ACCOUNT_NOT_FOUND")
    assert body["error"]["details"]["account_id"] == ("00000000-0000-0000-0000-000000000000")


def test_transfer_with_unknown_destination_returns_404(client: TestClient) -> None:
    source = create_account(client, "Source")

    response = _transfer(
        client,
        source["id"],
        "00000000-0000-0000-0000-000000000000",
    )

    body = assert_error(response, 404, "ACCOUNT_NOT_FOUND")
    assert body["error"]["details"]["account_id"] == ("00000000-0000-0000-0000-000000000000")


def test_transfer_to_same_account_is_rejected(client: TestClient) -> None:
    account = create_account(client, "Source")
    create_transaction(client, account["id"], amount="100.00", reference_id="REF-1")

    response = _transfer(client, account["id"], account["id"], amount="10.00")

    assert_error(response, 400, "SAME_ACCOUNT_TRANSFER")
    assert get_balance(client, account["id"]) == "100.00"


def test_transfer_with_insufficient_balance_leaves_no_trace(
    client: TestClient,
    db_session: Session,
) -> None:
    source = create_account(client, "Source")
    destination = create_account(client, "Destination")
    create_transaction(client, source["id"], amount="50.00", reference_id="REF-1")

    response = _transfer(client, source["id"], destination["id"], amount="100.00")

    assert_error(response, 400, "INSUFFICIENT_BALANCE")
    assert get_balance(client, source["id"]) == "50.00"
    assert get_balance(client, destination["id"]) == "0.00"
    assert db_session.scalar(select(func.count()).select_from(Transfer)) == 0
    assert db_session.scalar(select(func.count()).select_from(Transaction)) == 1


@pytest.mark.parametrize("amount", ["0.00", "-1.00", "1.001"])
def test_transfer_rejects_invalid_amounts(
    client: TestClient,
    amount: str,
) -> None:
    source = create_account(client, "Source")
    destination = create_account(client, "Destination")

    response = _transfer(client, source["id"], destination["id"], amount=amount)

    assert_error(response, 422, "INVALID_AMOUNT")


def test_transfer_that_would_overflow_destination_balance_is_rejected(
    client: TestClient,
    db_session: Session,
) -> None:
    source = create_account(client, "Source")
    destination = create_account(client, "Destination")
    create_transaction(client, source["id"], amount="500.00", reference_id="REF-1")
    create_transaction(
        client,
        destination["id"],
        amount="9999999999999999.99",
        reference_id="REF-MAX",
    )

    response = _transfer(client, source["id"], destination["id"], amount="1.00")

    assert_error(response, 400, "BALANCE_LIMIT_EXCEEDED")
    assert get_balance(client, source["id"]) == "500.00"
    assert get_balance(client, destination["id"]) == "9999999999999999.99"
    assert db_session.scalar(select(func.count()).select_from(Transfer)) == 0


def test_duplicate_transfer_does_not_move_money_twice(
    client: TestClient,
    db_session: Session,
) -> None:
    source = create_account(client, "Source")
    destination = create_account(client, "Destination")
    create_transaction(client, source["id"], amount="500.00", reference_id="REF-1")
    assert _transfer(client, source["id"], destination["id"]).status_code == 201

    response = _transfer(client, source["id"], destination["id"])

    assert_error(response, 409, "DUPLICATE_TRANSFER")
    assert get_balance(client, source["id"]) == "400.00"
    assert get_balance(client, destination["id"]) == "100.00"
    assert db_session.scalar(select(func.count()).select_from(Transfer)) == 1
    assert (
        db_session.scalar(
            select(func.count())
            .select_from(Transaction)
            .where(Transaction.transfer_id.is_not(None))
        )
        == 2
    )


def test_transfer_invalid_account_uuid_is_rejected(client: TestClient) -> None:
    source = create_account(client, "Source")

    response = client.post(
        "/api/v1/transfers",
        json={
            "source_account_id": source["id"],
            "destination_account_id": "not-a-uuid",
            "amount": "10.00",
            "reference_id": "TRANSFER-001",
        },
    )

    assert_error(response, 422, "INVALID_ACCOUNT_ID")


def test_transfer_missing_reference_id_is_rejected(client: TestClient) -> None:
    source = create_account(client, "Source")
    destination = create_account(client, "Destination")

    response = client.post(
        "/api/v1/transfers",
        json={
            "source_account_id": source["id"],
            "destination_account_id": destination["id"],
            "amount": "10.00",
        },
    )

    assert_error(response, 422, "INVALID_REFERENCE_ID")


def test_transfer_unexpected_field_is_rejected(client: TestClient) -> None:
    source = create_account(client, "Source")
    destination = create_account(client, "Destination")

    response = client.post(
        "/api/v1/transfers",
        json={
            "source_account_id": source["id"],
            "destination_account_id": destination["id"],
            "amount": "10.00",
            "reference_id": "TRANSFER-001",
            "balance": "100.00",
        },
    )

    assert_error(response, 422, "VALIDATION_ERROR")


def test_failed_transfer_rolls_back_all_changes(
    client: TestClient,
    db_session: Session,
) -> None:
    source = create_account(client, "Source")
    destination = create_account(client, "Destination")
    create_transaction(client, source["id"], amount="500.00", reference_id="REF-1")

    def force_invalid_destination_balance(session, flush_context, instances):
        if any(
            isinstance(item, Transaction) and item.transfer_id is not None for item in session.new
        ):
            for item in session.dirty:
                if isinstance(item, Account) and item.id == UUID(destination["id"]):
                    item.balance = Decimal("-1.00")

    event.listen(Session, "before_flush", force_invalid_destination_balance)
    try:
        response = _transfer(client, source["id"], destination["id"])
    finally:
        event.remove(Session, "before_flush", force_invalid_destination_balance)

    assert_error(response, 409, "CONFLICT")
    assert get_balance(client, source["id"]) == "500.00"
    assert get_balance(client, destination["id"]) == "0.00"
    assert db_session.scalar(select(func.count()).select_from(Transfer)) == 0
    assert (
        db_session.scalar(
            select(func.count())
            .select_from(Transaction)
            .where(Transaction.transfer_id.is_not(None))
        )
        == 0
    )
