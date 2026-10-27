from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.main import app
from app.models import Transaction, Transfer
from tests.helpers import assert_error, create_account, create_transaction, get_balance


def run_parallel(
    requests: list[Callable[[TestClient], object]],
) -> list:
    barrier = Barrier(len(requests))

    def worker(request: Callable[[TestClient], object]):
        with TestClient(app, raise_server_exceptions=False) as client:
            barrier.wait()
            return request(client)

    with ThreadPoolExecutor(max_workers=len(requests)) as executor:
        return list(executor.map(worker, requests))


def test_concurrent_duplicate_transactions_only_commit_once(
    client: TestClient,
    db_session: Session,
) -> None:
    account = create_account(client, "Alice")
    url = f"/api/v1/accounts/{account['id']}/transactions"
    payload = {"type": "credit", "amount": "100.00", "reference_id": "REF-1"}

    responses = run_parallel(
        [lambda test_client: test_client.post(url, json=payload) for _ in range(5)]
    )

    statuses = sorted(response.status_code for response in responses)
    assert statuses == [201, 409, 409, 409, 409]
    assert get_balance(client, account["id"]) == "100.00"
    assert db_session.scalar(select(func.count()).select_from(Transaction)) == 1


def test_concurrent_debits_cannot_overdraw_account(
    client: TestClient,
    db_session: Session,
) -> None:
    account = create_account(client, "Alice")
    create_transaction(client, account["id"], amount="100.00", reference_id="REF-1")
    url = f"/api/v1/accounts/{account['id']}/transactions"

    responses = run_parallel(
        [
            lambda test_client: test_client.post(
                url,
                json={"type": "debit", "amount": "80.00", "reference_id": "DEBIT-1"},
            ),
            lambda test_client: test_client.post(
                url,
                json={"type": "debit", "amount": "70.00", "reference_id": "DEBIT-2"},
            ),
        ]
    )

    statuses = sorted(response.status_code for response in responses)
    assert statuses == [201, 400]
    assert get_balance(client, account["id"]) in {"20.00", "30.00"}
    debit_count = db_session.scalar(
        select(func.count()).select_from(Transaction).where(Transaction.type == "debit")
    )
    assert debit_count == 1
    rejected = next(response for response in responses if response.status_code == 400)
    assert_error(rejected, 400, "INSUFFICIENT_BALANCE")


def test_concurrent_opposite_transfers_do_not_deadlock(
    client: TestClient,
    db_session: Session,
) -> None:
    first = create_account(client, "First")
    second = create_account(client, "Second")
    create_transaction(client, first["id"], amount="100.00", reference_id="REF-1")
    create_transaction(client, second["id"], amount="100.00", reference_id="REF-2")

    def transfer(test_client: TestClient, source: str, destination: str, reference: str):
        return test_client.post(
            "/api/v1/transfers",
            json={
                "source_account_id": source,
                "destination_account_id": destination,
                "amount": "30.00" if source == first["id"] else "40.00",
                "reference_id": reference,
            },
        )

    responses = run_parallel(
        [
            lambda test_client: transfer(
                test_client,
                first["id"],
                second["id"],
                "TRANSFER-1",
            ),
            lambda test_client: transfer(
                test_client,
                second["id"],
                first["id"],
                "TRANSFER-2",
            ),
        ]
    )

    assert [response.status_code for response in responses] == [201, 201]
    assert get_balance(client, first["id"]) == "110.00"
    assert get_balance(client, second["id"]) == "90.00"
    assert db_session.scalar(select(func.count()).select_from(Transfer)) == 2
    assert (
        db_session.scalar(
            select(func.count())
            .select_from(Transaction)
            .where(Transaction.transfer_id.is_not(None))
        )
        == 4
    )


def test_concurrent_duplicate_transfers_move_money_once(
    client: TestClient,
    db_session: Session,
) -> None:
    source = create_account(client, "Source")
    destination = create_account(client, "Destination")
    create_transaction(client, source["id"], amount="200.00", reference_id="REF-1")
    payload = {
        "source_account_id": source["id"],
        "destination_account_id": destination["id"],
        "amount": "50.00",
        "reference_id": "TRANSFER-1",
    }

    responses = run_parallel(
        [lambda test_client: test_client.post("/api/v1/transfers", json=payload) for _ in range(2)]
    )

    statuses = sorted(response.status_code for response in responses)
    assert statuses == [201, 409]
    assert get_balance(client, source["id"]) == "150.00"
    assert get_balance(client, destination["id"]) == "50.00"
    assert db_session.scalar(select(func.count()).select_from(Transfer)) == 1
    assert (
        db_session.scalar(
            select(func.count())
            .select_from(Transaction)
            .where(Transaction.transfer_id.is_not(None))
        )
        == 2
    )
