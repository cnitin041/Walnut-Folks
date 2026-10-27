from fastapi.testclient import TestClient


def assert_error(response, status_code: int, code: str) -> dict:
    assert response.status_code == status_code, response.text
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == code
    assert isinstance(body["error"]["message"], str)
    return body


def create_account(client: TestClient, name: str = "Test Account") -> dict:
    response = client.post("/api/v1/accounts", json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()["data"]


def create_transaction(
    client: TestClient,
    account_id: str,
    *,
    type_: str = "credit",
    amount: str = "100.00",
    reference_id: str,
    description: str = "",
) -> dict:
    response = client.post(
        f"/api/v1/accounts/{account_id}/transactions",
        json={
            "type": type_,
            "amount": amount,
            "reference_id": reference_id,
            "description": description,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


def get_balance(client: TestClient, account_id: str) -> str:
    response = client.get(f"/api/v1/accounts/{account_id}/balance")
    assert response.status_code == 200, response.text
    return response.json()["data"]["balance"]
