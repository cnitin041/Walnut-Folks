from datetime import datetime
from decimal import Decimal
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select
from sqlalchemy.orm import Session

from app.models import Account, Transaction
from tests.helpers import (
    assert_error,
    create_account,
    create_transaction,
    get_balance,
)


def test_credit_transaction(client: TestClient) -> None:
    account = create_account(client, "Alice")

    response = client.post(
        f"/api/v1/accounts/{account['id']}/transactions",
        json={
            "type": "credit",
            "amount": "500.00",
            "description": "Initial deposit",
            "reference_id": "REF-001",
        },
    )

    assert response.status_code == 201, response.text
    data = response.json()["data"]
    assert data["account_id"] == account["id"]
    assert data["type"] == "credit"
    assert data["amount"] == "500.00"
    assert data["description"] == "Initial deposit"
    assert data["reference_id"] == "REF-001"
    UUID(data["id"])
    datetime.fromisoformat(data["created_at"])
    assert get_balance(client, account["id"]) == "500.00"


def test_debit_transaction(client: TestClient) -> None:
    account = create_account(client, "Alice")
    create_transaction(client, account["id"], amount="500.00", reference_id="REF-1")

    response = client.post(
        f"/api/v1/accounts/{account['id']}/transactions",
        json={"type": "debit", "amount": "200.00", "reference_id": "REF-2"},
    )

    assert response.status_code == 201, response.text
    assert response.json()["data"]["amount"] == "200.00"
    assert get_balance(client, account["id"]) == "300.00"


def test_insufficient_debit_is_rejected_without_changes(
    client: TestClient,
    db_session: Session,
) -> None:
    account = create_account(client, "Alice")
    create_transaction(client, account["id"], amount="50.00", reference_id="REF-1")

    response = client.post(
        f"/api/v1/accounts/{account['id']}/transactions",
        json={"type": "debit", "amount": "60.00", "reference_id": "REF-2"},
    )

    body = assert_error(response, 400, "INSUFFICIENT_BALANCE")
    assert body["error"]["details"]["balance"] == "50.00"
    assert get_balance(client, account["id"]) == "50.00"
    count = db_session.scalar(
        select(func.count())
        .select_from(Transaction)
        .where(Transaction.account_id == UUID(account["id"]))
    )
    assert count == 1


@pytest.mark.parametrize(
    "amount",
    ["0", "0.00", "-1.00", "1.001", "10000000000000000.00"],
)
def test_invalid_amounts_are_rejected(client: TestClient, amount: str) -> None:
    account = create_account(client, "Alice")

    response = client.post(
        f"/api/v1/accounts/{account['id']}/transactions",
        json={"type": "credit", "amount": amount, "reference_id": "REF-1"},
    )

    assert_error(response, 422, "INVALID_AMOUNT")


def test_float_amount_is_rejected(client: TestClient) -> None:
    account = create_account(client, "Alice")

    response = client.post(
        f"/api/v1/accounts/{account['id']}/transactions",
        json={"type": "credit", "amount": 10.5, "reference_id": "REF-1"},
    )

    assert_error(response, 422, "INVALID_AMOUNT")


def test_invalid_transaction_type_is_rejected(client: TestClient) -> None:
    account = create_account(client, "Alice")

    response = client.post(
        f"/api/v1/accounts/{account['id']}/transactions",
        json={"type": "hold", "amount": "10.00", "reference_id": "REF-1"},
    )

    assert_error(response, 422, "INVALID_TRANSACTION_TYPE")


@pytest.mark.parametrize("payload", [{}, {"reference_id": "   "}])
def test_missing_or_blank_reference_id_is_rejected(
    client: TestClient,
    payload: dict,
) -> None:
    account = create_account(client, "Alice")
    body = {"type": "credit", "amount": "10.00", **payload}

    response = client.post(
        f"/api/v1/accounts/{account['id']}/transactions",
        json=body,
    )

    assert_error(response, 422, "INVALID_REFERENCE_ID")


def test_transaction_for_unknown_account_returns_404(client: TestClient) -> None:
    response = client.post(
        "/api/v1/accounts/00000000-0000-0000-0000-000000000000/transactions",
        json={"type": "credit", "amount": "10.00", "reference_id": "REF-1"},
    )

    assert_error(response, 404, "ACCOUNT_NOT_FOUND")


def test_credit_that_would_overflow_balance_is_rejected(
    client: TestClient,
    db_session: Session,
) -> None:
    account = create_account(client, "Alice")
    create_transaction(
        client,
        account["id"],
        amount="9999999999999999.99",
        reference_id="REF-MAX",
    )

    response = client.post(
        f"/api/v1/accounts/{account['id']}/transactions",
        json={"type": "credit", "amount": "0.01", "reference_id": "REF-OVERFLOW"},
    )

    assert_error(response, 400, "BALANCE_LIMIT_EXCEEDED")
    assert get_balance(client, account["id"]) == "9999999999999999.99"
    count = db_session.scalar(
        select(func.count())
        .select_from(Transaction)
        .where(Transaction.account_id == UUID(account["id"]))
    )
    assert count == 1


def test_duplicate_reference_on_same_account_is_rejected(
    client: TestClient,
    db_session: Session,
) -> None:
    account = create_account(client, "Alice")
    create_transaction(client, account["id"], amount="100.00", reference_id="REF-1")

    response = client.post(
        f"/api/v1/accounts/{account['id']}/transactions",
        json={"type": "credit", "amount": "50.00", "reference_id": "REF-1"},
    )

    assert_error(response, 409, "DUPLICATE_TRANSACTION")
    assert get_balance(client, account["id"]) == "100.00"
    count = db_session.scalar(
        select(func.count())
        .select_from(Transaction)
        .where(Transaction.account_id == UUID(account["id"]))
    )
    assert count == 1


def test_same_reference_is_allowed_on_different_accounts(client: TestClient) -> None:
    first = create_account(client, "Alice")
    second = create_account(client, "Bob")

    create_transaction(client, first["id"], amount="100.00", reference_id="REF-1")
    create_transaction(client, second["id"], amount="50.00", reference_id="REF-1")

    assert get_balance(client, first["id"]) == "100.00"
    assert get_balance(client, second["id"]) == "50.00"


def test_unexpected_fields_are_rejected(client: TestClient) -> None:
    account = create_account(client, "Alice")

    response = client.post(
        f"/api/v1/accounts/{account['id']}/transactions",
        json={
            "type": "credit",
            "amount": "10.00",
            "reference_id": "REF-1",
            "balance": "1000.00",
        },
    )

    assert_error(response, 422, "VALIDATION_ERROR")


def test_too_long_description_is_rejected(client: TestClient) -> None:
    account = create_account(client, "Alice")

    response = client.post(
        f"/api/v1/accounts/{account['id']}/transactions",
        json={
            "type": "credit",
            "amount": "10.00",
            "reference_id": "REF-1",
            "description": "x" * 1001,
        },
    )

    assert_error(response, 422, "VALIDATION_ERROR")


def test_transactions_cannot_be_modified_or_deleted(client: TestClient) -> None:
    account = create_account(client, "Alice")
    transaction = create_transaction(
        client,
        account["id"],
        amount="10.00",
        reference_id="REF-1",
    )
    collection_url = f"/api/v1/accounts/{account['id']}/transactions"
    item_url = f"{collection_url}/{transaction['id']}"

    assert_error(client.put(collection_url, json={}), 405, "METHOD_NOT_ALLOWED")
    assert_error(client.delete(collection_url), 405, "METHOD_NOT_ALLOWED")
    assert_error(client.put(item_url, json={}), 404, "NOT_FOUND")
    assert_error(client.delete(item_url), 404, "NOT_FOUND")


def test_balance_and_ledger_roll_back_if_ledger_insert_fails(
    client: TestClient,
    db_session: Session,
) -> None:
    account = create_account(client, "Alice")

    def fail_on_new_transaction(session, flush_context, instances):
        if any(isinstance(item, Transaction) for item in session.new):
            raise RuntimeError("simulated ledger insert failure")

    event.listen(Session, "before_flush", fail_on_new_transaction)
    try:
        response = client.post(
            f"/api/v1/accounts/{account['id']}/transactions",
            json={"type": "credit", "amount": "10.00", "reference_id": "REF-1"},
        )
    finally:
        event.remove(Session, "before_flush", fail_on_new_transaction)

    assert_error(response, 500, "INTERNAL_ERROR")
    assert get_balance(client, account["id"]) == "0.00"
    count = db_session.scalar(select(func.count()).select_from(Transaction))
    assert count == 0


def test_balance_and_ledger_roll_back_if_balance_update_fails(
    client: TestClient,
    db_session: Session,
) -> None:
    account = create_account(client, "Alice")

    def force_invalid_balance(session, flush_context, instances):
        if any(isinstance(item, Transaction) for item in session.new):
            for item in session.dirty:
                if isinstance(item, Account):
                    item.balance = Decimal("-1.00")

    event.listen(Session, "before_flush", force_invalid_balance)
    try:
        response = client.post(
            f"/api/v1/accounts/{account['id']}/transactions",
            json={"type": "credit", "amount": "10.00", "reference_id": "REF-1"},
        )
    finally:
        event.remove(Session, "before_flush", force_invalid_balance)

    assert_error(response, 409, "CONFLICT")
    assert get_balance(client, account["id"]) == "0.00"
    count = db_session.scalar(select(func.count()).select_from(Transaction))
    assert count == 0
