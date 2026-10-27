from datetime import UTC, datetime
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models import Transaction
from tests.helpers import (
    assert_error,
    create_account,
    create_transaction,
)


def test_history_returns_all_transactions_newest_first(client: TestClient) -> None:
    account = create_account(client, "Alice")
    create_transaction(client, account["id"], amount="10.00", reference_id="REF-1")
    create_transaction(client, account["id"], amount="20.00", reference_id="REF-2")
    create_transaction(
        client,
        account["id"],
        type_="debit",
        amount="5.00",
        reference_id="REF-3",
    )

    response = client.get(f"/api/v1/accounts/{account['id']}/transactions")

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert [item["reference_id"] for item in data] == ["REF-3", "REF-2", "REF-1"]
    assert response.json()["pagination"] == {
        "page": 1,
        "limit": 10,
        "total_records": 3,
        "total_pages": 1,
    }


def test_history_uses_id_as_deterministic_secondary_sort(
    client: TestClient,
    db_session: Session,
) -> None:
    account = create_account(client, "Alice")
    for index in range(3):
        create_transaction(
            client,
            account["id"],
            amount="10.00",
            reference_id=f"REF-{index}",
        )

    fixed_time = datetime(2026, 1, 1, tzinfo=UTC)
    db_session.execute(update(Transaction).values(created_at=fixed_time))
    db_session.commit()

    response = client.get(f"/api/v1/accounts/{account['id']}/transactions")

    assert response.status_code == 200, response.text
    ids = [UUID(item["id"]) for item in response.json()["data"]]
    assert ids == sorted(ids, reverse=True)


def test_history_filters_credit_and_debit_transactions(client: TestClient) -> None:
    account = create_account(client, "Alice")
    create_transaction(client, account["id"], amount="10.00", reference_id="REF-1")
    create_transaction(
        client,
        account["id"],
        type_="debit",
        amount="5.00",
        reference_id="REF-2",
    )

    credits = client.get(
        f"/api/v1/accounts/{account['id']}/transactions",
        params={"type": "credit"},
    )
    debits = client.get(
        f"/api/v1/accounts/{account['id']}/transactions",
        params={"type": "debit"},
    )

    assert [item["reference_id"] for item in credits.json()["data"]] == ["REF-1"]
    assert [item["reference_id"] for item in debits.json()["data"]] == ["REF-2"]
    assert credits.json()["pagination"]["total_records"] == 1
    assert debits.json()["pagination"]["total_records"] == 1


def test_history_paginates_in_the_database(client: TestClient) -> None:
    account = create_account(client, "Alice")
    for index in range(5):
        create_transaction(
            client,
            account["id"],
            amount="10.00",
            reference_id=f"REF-{index}",
        )

    first_page = client.get(
        f"/api/v1/accounts/{account['id']}/transactions",
        params={"page": 1, "limit": 2},
    )
    last_page = client.get(
        f"/api/v1/accounts/{account['id']}/transactions",
        params={"page": 3, "limit": 2},
    )

    assert first_page.status_code == 200, first_page.text
    assert first_page.json()["pagination"] == {
        "page": 1,
        "limit": 2,
        "total_records": 5,
        "total_pages": 3,
    }
    assert len(first_page.json()["data"]) == 2
    assert len(last_page.json()["data"]) == 1


def test_history_handles_empty_result(client: TestClient) -> None:
    account = create_account(client, "Alice")

    response = client.get(f"/api/v1/accounts/{account['id']}/transactions")

    assert response.status_code == 200, response.text
    assert response.json()["data"] == []
    assert response.json()["pagination"] == {
        "page": 1,
        "limit": 10,
        "total_records": 0,
        "total_pages": 0,
    }


def test_history_page_past_the_end_returns_empty_data(client: TestClient) -> None:
    account = create_account(client, "Alice")
    create_transaction(client, account["id"], amount="10.00", reference_id="REF-1")

    response = client.get(
        f"/api/v1/accounts/{account['id']}/transactions",
        params={"page": 5},
    )

    assert response.status_code == 200, response.text
    assert response.json()["data"] == []
    assert response.json()["pagination"]["total_records"] == 1
    assert response.json()["pagination"]["total_pages"] == 1


def test_history_rejects_invalid_filter(client: TestClient) -> None:
    account = create_account(client, "Alice")

    response = client.get(
        f"/api/v1/accounts/{account['id']}/transactions",
        params={"type": "hold"},
    )

    assert_error(response, 422, "INVALID_TRANSACTION_TYPE")


def test_history_rejects_invalid_pagination(client: TestClient) -> None:
    account = create_account(client, "Alice")

    assert_error(
        client.get(
            f"/api/v1/accounts/{account['id']}/transactions",
            params={"page": 0},
        ),
        422,
        "INVALID_PAGINATION",
    )
    assert_error(
        client.get(
            f"/api/v1/accounts/{account['id']}/transactions",
            params={"limit": 101},
        ),
        422,
        "INVALID_PAGINATION",
    )


def test_history_for_unknown_account_returns_404(client: TestClient) -> None:
    response = client.get("/api/v1/accounts/00000000-0000-0000-0000-000000000000/transactions")

    assert_error(response, 404, "ACCOUNT_NOT_FOUND")
