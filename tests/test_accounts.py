from datetime import datetime
from uuid import UUID

from fastapi.testclient import TestClient

from tests.helpers import assert_error, create_account


def test_create_account_initializes_zero_balance(client: TestClient) -> None:
    response = client.post("/api/v1/accounts", json={"name": "Rahul Sharma"})

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["success"] is True
    assert body["data"]["name"] == "Rahul Sharma"
    assert body["data"]["balance"] == "0.00"
    UUID(body["data"]["id"])
    datetime.fromisoformat(body["data"]["created_at"])


def test_account_ids_are_unique(client: TestClient) -> None:
    first = create_account(client, "First")
    second = create_account(client, "Second")

    assert first["id"] != second["id"]


def test_rejects_missing_name(client: TestClient) -> None:
    response = client.post("/api/v1/accounts", json={})

    assert_error(response, 422, "VALIDATION_ERROR")


def test_rejects_whitespace_only_name(client: TestClient) -> None:
    response = client.post("/api/v1/accounts", json={"name": "   "})

    assert_error(response, 422, "VALIDATION_ERROR")


def test_rejects_client_supplied_balance(client: TestClient) -> None:
    response = client.post(
        "/api/v1/accounts",
        json={"name": "Rahul Sharma", "balance": "100.00"},
    )

    body = assert_error(response, 422, "VALIDATION_ERROR")
    assert body["error"]["details"]["errors"][0]["field"] == "balance"


def test_get_account(client: TestClient) -> None:
    account = create_account(client, "Rahul Sharma")

    response = client.get(f"/api/v1/accounts/{account['id']}")

    assert response.status_code == 200, response.text
    assert response.json()["data"] == account


def test_get_unknown_account_returns_404(client: TestClient) -> None:
    response = client.get("/api/v1/accounts/00000000-0000-0000-0000-000000000000")

    body = assert_error(response, 404, "ACCOUNT_NOT_FOUND")
    assert "account_id" in body["error"]["details"]


def test_get_invalid_account_id_returns_422(client: TestClient) -> None:
    response = client.get("/api/v1/accounts/not-a-uuid")

    assert_error(response, 422, "INVALID_ACCOUNT_ID")


def test_get_balance(client: TestClient) -> None:
    account = create_account(client, "Rahul Sharma")

    response = client.get(f"/api/v1/accounts/{account['id']}/balance")

    assert response.status_code == 200, response.text
    assert response.json()["data"] == {
        "account_id": account["id"],
        "balance": "0.00",
    }


def test_get_balance_for_unknown_account_returns_404(client: TestClient) -> None:
    response = client.get("/api/v1/accounts/00000000-0000-0000-0000-000000000000/balance")

    assert_error(response, 404, "ACCOUNT_NOT_FOUND")


def test_health_check(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200, response.text
    assert response.json() == {"status": "ok", "database": "ok"}


def test_openapi_and_docs_are_available(client: TestClient) -> None:
    assert client.get("/docs").status_code == 200
    openapi = client.get("/openapi.json")
    assert openapi.status_code == 200
    paths = openapi.json()["paths"]
    assert "/api/v1/accounts" in paths
    assert "/api/v1/accounts/{account_id}/transactions" in paths
    assert "/api/v1/transfers" in paths
