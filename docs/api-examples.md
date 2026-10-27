# API Curl Examples

Runnable `curl` examples for every endpoint in the Transaction Ledger API.

## Base URL and Variables

Start the API first:

```bash
.venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Set the base URL and IDs used in the examples. Replace placeholder UUIDs with values returned by your own requests.

```bash
BASE_URL="http://127.0.0.1:8000"

ACCOUNT_ID="<account-uuid>"
SECOND_ACCOUNT_ID="<second-account-uuid>"
EMPTY_ACCOUNT_ID="<new-account-with-no-transactions>"
TRANSACTION_ID="<transaction-uuid>"
TRANSFER_ID="<transfer-uuid>"
```

The request examples use `-w "\nHTTP %{http_code}\n"` so the HTTP status is printed after the JSON body.

### Windows PowerShell note

PowerShell's `curl` alias is `Invoke-WebRequest`, not the curl executable. Use `curl.exe` and set variables with `$`:

```powershell
$BASE_URL = "http://127.0.0.1:8000"
$ACCOUNT_ID = "paste-account-uuid"
curl.exe -sS -w "`nHTTP %{http_code}`n" "$BASE_URL/health"
```

The commands below use Bash line continuation (`\`). Run them in Git Bash/WSL, or put each command on one line with `curl.exe` in PowerShell.

## Health

```bash
curl -sS -w "\nHTTP %{http_code}\n" "$BASE_URL/health"
```

Expected `200`:

```json
{"status":"ok","database":"ok"}
```

If PostgreSQL is unavailable, the API returns `503`:

```json
{"status":"degraded","database":"unavailable"}
```

## Accounts

### Create an account

```bash
curl -sS -w "\nHTTP %{http_code}\n" \
  -X POST "$BASE_URL/api/v1/accounts" \
  -H "Content-Type: application/json" \
  -d '{"name": "Rahul Sharma"}'
```

Expected `201`:

```json
{
  "success": true,
  "data": {
    "id": "4a3af89c-92ab-4502-b18c-38a6c08fce5a",
    "name": "Rahul Sharma",
    "balance": "0.00",
    "created_at": "2026-10-27T11:52:10.252200+05:30"
  }
}
```

Capture the account ID:

```bash
ACCOUNT_ID=$(curl -sS -X POST "$BASE_URL/api/v1/accounts" \
  -H "Content-Type: application/json" \
  -d '{"name": "Rahul Sharma"}' | jq -r '.data.id')

echo "$ACCOUNT_ID"
```

This example requires `jq`. It is optional; the API does not require `jq`.

### Create a second account

Use a second account for transfers and the same-reference example:

```bash
curl -sS -w "\nHTTP %{http_code}\n" \
  -X POST "$BASE_URL/api/v1/accounts" \
  -H "Content-Type: application/json" \
  -d '{"name": "Priya Sharma"}'
```

Copy the returned `id` into `SECOND_ACCOUNT_ID`.

### Retrieve an account

```bash
curl -sS -w "\nHTTP %{http_code}\n" "$BASE_URL/api/v1/accounts/$ACCOUNT_ID"
```

Expected `200`:

```json
{
  "success": true,
  "data": {
    "id": "4a3af89c-92ab-4502-b18c-38a6c08fce5a",
    "name": "Rahul Sharma",
    "balance": "0.00",
    "created_at": "2026-10-27T11:52:10.252200+05:30"
  }
}
```

### Retrieve an account balance

```bash
curl -sS -w "\nHTTP %{http_code}\n" "$BASE_URL/api/v1/accounts/$ACCOUNT_ID/balance"
```

Expected `200`:

```json
{
  "success": true,
  "data": {
    "account_id": "4a3af89c-92ab-4502-b18c-38a6c08fce5a",
    "balance": "0.00"
  }
}
```

### Unknown account

```bash
curl -sS -w "\nHTTP %{http_code}\n" \
  "$BASE_URL/api/v1/accounts/00000000-0000-0000-0000-000000000000"
```

Expected `404`:

```json
{
  "success": false,
  "error": {
    "code": "ACCOUNT_NOT_FOUND",
    "message": "Account not found.",
    "details": {
      "account_id": "00000000-0000-0000-0000-000000000000"
    }
  }
}
```

### Invalid account UUID

```bash
curl -sS -w "\nHTTP %{http_code}\n" "$BASE_URL/api/v1/accounts/not-a-uuid"
```

Expected `422`:

```json
{
  "success": false,
  "error": {
    "code": "INVALID_ACCOUNT_ID",
    "message": "Request validation failed.",
    "details": {
      "errors": [
        {
          "field": "account_id",
          "message": "Input should be a valid UUID, invalid character: found `n` at 0",
          "type": "uuid_parsing"
        }
      ]
    }
  }
}
```

### Reject client-supplied initial balance

```bash
curl -sS -w "\nHTTP %{http_code}\n" \
  -X POST "$BASE_URL/api/v1/accounts" \
  -H "Content-Type: application/json" \
  -d '{"name": "Rahul Sharma", "balance": "100.00"}'
```

Expected `422`:

```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed.",
    "details": {
      "errors": [
        {
          "field": "balance",
          "message": "Extra inputs are not permitted",
          "type": "extra_forbidden"
        }
      ]
    }
  }
}
```

### Reject a missing or blank name

```bash
curl -sS -w "\nHTTP %{http_code}\n" \
  -X POST "$BASE_URL/api/v1/accounts" \
  -H "Content-Type: application/json" \
  -d '{}'
```

```bash
curl -sS -w "\nHTTP %{http_code}\n" \
  -X POST "$BASE_URL/api/v1/accounts" \
  -H "Content-Type: application/json" \
  -d '{"name": "   "}'
```

Both return `422 VALIDATION_ERROR`.

## Transactions

### Create a credit

```bash
curl -sS -w "\nHTTP %{http_code}\n" \
  -X POST "$BASE_URL/api/v1/accounts/$ACCOUNT_ID/transactions" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "credit",
    "amount": "500.00",
    "description": "Initial deposit",
    "reference_id": "REF-001"
  }'
```

Expected `201`:

```json
{
  "success": true,
  "data": {
    "id": "4f32d1bb-4f6f-4428-bc44-08f250a7a44d",
    "account_id": "4a3af89c-92ab-4502-b18c-38a6c08fce5a",
    "type": "credit",
    "amount": "500.00",
    "description": "Initial deposit",
    "reference_id": "REF-001",
    "created_at": "2026-10-27T11:54:49.252351+05:30"
  }
}
```

### Create a debit

```bash
curl -sS -w "\nHTTP %{http_code}\n" \
  -X POST "$BASE_URL/api/v1/accounts/$ACCOUNT_ID/transactions" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "debit",
    "amount": "200.00",
    "description": "ATM withdrawal",
    "reference_id": "REF-002"
  }'
```

Expected `201`. The account balance becomes `300.00`.

### Capture a transaction ID

```bash
TRANSACTION_ID=$(curl -sS -X POST "$BASE_URL/api/v1/accounts/$ACCOUNT_ID/transactions" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "credit",
    "amount": "10.00",
    "reference_id": "REF-CAPTURE"
  }' | jq -r '.data.id')

echo "$TRANSACTION_ID"
```

### Duplicate reference for the same account

Submit the same `reference_id` again:

```bash
curl -sS -w "\nHTTP %{http_code}\n" \
  -X POST "$BASE_URL/api/v1/accounts/$ACCOUNT_ID/transactions" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "credit",
    "amount": "100.00",
    "reference_id": "REF-001"
  }'
```

Expected `409`:

```json
{
  "success": false,
  "error": {
    "code": "DUPLICATE_TRANSACTION",
    "message": "A transaction with this reference_id already exists for the account.",
    "details": {
      "account_id": "4a3af89c-92ab-4502-b18c-38a6c08fce5a",
      "reference_id": "REF-001"
    }
  }
}
```

### Same reference on a different account is allowed

```bash
curl -sS -w "\nHTTP %{http_code}\n" \
  -X POST "$BASE_URL/api/v1/accounts/$SECOND_ACCOUNT_ID/transactions" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "credit",
    "amount": "100.00",
    "reference_id": "REF-001"
  }'
```

Expected `201`. References are unique per account, not globally.

### Insufficient balance

```bash
curl -sS -w "\nHTTP %{http_code}\n" \
  -X POST "$BASE_URL/api/v1/accounts/$ACCOUNT_ID/transactions" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "debit",
    "amount": "9999.00",
    "reference_id": "REF-INSUFFICIENT"
  }'
```

Expected `400`:

```json
{
  "success": false,
  "error": {
    "code": "INSUFFICIENT_BALANCE",
    "message": "Insufficient balance for this debit transaction.",
    "details": {
      "account_id": "4a3af89c-92ab-4502-b18c-38a6c08fce5a",
      "balance": "300.00",
      "requested_amount": "9999.00"
    }
  }
}
```

The balance is unchanged and no ledger entry is created.

### Invalid amount: zero

```bash
curl -sS -w "\nHTTP %{http_code}\n" \
  -X POST "$BASE_URL/api/v1/accounts/$ACCOUNT_ID/transactions" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "credit",
    "amount": "0.00",
    "reference_id": "REF-ZERO"
  }'
```

Expected `422 INVALID_AMOUNT`.

### Invalid amount: negative

```bash
curl -sS -w "\nHTTP %{http_code}\n" \
  -X POST "$BASE_URL/api/v1/accounts/$ACCOUNT_ID/transactions" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "credit",
    "amount": "-1.00",
    "reference_id": "REF-NEGATIVE"
  }'
```

Expected `422 INVALID_AMOUNT`.

### Invalid amount: too many decimal places

```bash
curl -sS -w "\nHTTP %{http_code}\n" \
  -X POST "$BASE_URL/api/v1/accounts/$ACCOUNT_ID/transactions" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "credit",
    "amount": "10.001",
    "reference_id": "REF-PRECISION"
  }'
```

Expected `422 INVALID_AMOUNT`.

### Invalid amount: JSON float

```bash
curl -sS -w "\nHTTP %{http_code}\n" \
  -X POST "$BASE_URL/api/v1/accounts/$ACCOUNT_ID/transactions" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "credit",
    "amount": 10.5,
    "reference_id": "REF-FLOAT"
  }'
```

Expected `422 INVALID_AMOUNT`. Send money as a decimal string, for example `"10.50"`.

### Invalid transaction type

```bash
curl -sS -w "\nHTTP %{http_code}\n" \
  -X POST "$BASE_URL/api/v1/accounts/$ACCOUNT_ID/transactions" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "hold",
    "amount": "10.00",
    "reference_id": "REF-BAD-TYPE"
  }'
```

Expected `422 INVALID_TRANSACTION_TYPE`.

### Missing or blank reference_id

```bash
curl -sS -w "\nHTTP %{http_code}\n" \
  -X POST "$BASE_URL/api/v1/accounts/$ACCOUNT_ID/transactions" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "credit",
    "amount": "10.00"
  }'
```

```bash
curl -sS -w "\nHTTP %{http_code}\n" \
  -X POST "$BASE_URL/api/v1/accounts/$ACCOUNT_ID/transactions" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "credit",
    "amount": "10.00",
    "reference_id": "   "
  }'
```

Both return `422 INVALID_REFERENCE_ID`.

### Unexpected field

```bash
curl -sS -w "\nHTTP %{http_code}\n" \
  -X POST "$BASE_URL/api/v1/accounts/$ACCOUNT_ID/transactions" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "credit",
    "amount": "10.00",
    "reference_id": "REF-EXTRA",
    "balance": "1000.00"
  }'
```

Expected `422 VALIDATION_ERROR`.

### Transaction for an unknown account

```bash
curl -sS -w "\nHTTP %{http_code}\n" \
  -X POST "$BASE_URL/api/v1/accounts/00000000-0000-0000-0000-000000000000/transactions" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "credit",
    "amount": "10.00",
    "reference_id": "REF-UNKNOWN"
  }'
```

Expected `404 ACCOUNT_NOT_FOUND`.

### Balance limit exceeded

The maximum balance is `9999999999999999.99`. A credit or transfer that would exceed it returns `400 BALANCE_LIMIT_EXCEEDED`. Run this sequence on a fresh account.

```bash
curl -sS -w "\nHTTP %{http_code}\n" \
  -X POST "$BASE_URL/api/v1/accounts/$ACCOUNT_ID/transactions" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "credit",
    "amount": "9999999999999999.99",
    "reference_id": "REF-MAX"
  }'

curl -sS -w "\nHTTP %{http_code}\n" \
  -X POST "$BASE_URL/api/v1/accounts/$ACCOUNT_ID/transactions" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "credit",
    "amount": "0.01",
    "reference_id": "REF-OVERFLOW"
  }'
```

The second request returns `400 BALANCE_LIMIT_EXCEEDED`.

### Attempt to modify or delete a transaction

There are no update or delete endpoints.

```bash
curl -sS -w "\nHTTP %{http_code}\n" \
  -X PUT "$BASE_URL/api/v1/accounts/$ACCOUNT_ID/transactions" \
  -H "Content-Type: application/json" \
  -d '{}'
```

```bash
curl -sS -w "\nHTTP %{http_code}\n" \
  -X DELETE "$BASE_URL/api/v1/accounts/$ACCOUNT_ID/transactions"
```

Both return `405 METHOD_NOT_ALLOWED`.

```bash
curl -sS -w "\nHTTP %{http_code}\n" \
  -X DELETE "$BASE_URL/api/v1/accounts/$ACCOUNT_ID/transactions/$TRANSACTION_ID"
```

Expected `404 NOT_FOUND` because that route does not exist.

## Transaction History

### Get all transactions

```bash
curl -sS -w "\nHTTP %{http_code}\n" \
  "$BASE_URL/api/v1/accounts/$ACCOUNT_ID/transactions"
```

Expected `200`:

```json
{
  "success": true,
  "data": [
    {
      "id": "b774896a-9a63-401e-9b3c-cf1e6451cb05",
      "account_id": "4a3af89c-92ab-4502-b18c-38a6c08fce5a",
      "type": "debit",
      "amount": "200.00",
      "description": "ATM withdrawal",
      "reference_id": "REF-002",
      "created_at": "2026-10-27T11:54:49.308438+05:30"
    },
    {
      "id": "4f32d1bb-4f6f-4428-bc44-08f250a7a44d",
      "account_id": "4a3af89c-92ab-4502-b18c-38a6c08fce5a",
      "type": "credit",
      "amount": "500.00",
      "description": "Initial deposit",
      "reference_id": "REF-001",
      "created_at": "2026-10-27T11:54:49.252351+05:30"
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 10,
    "total_records": 2,
    "total_pages": 1
  }
}
```

Results are sorted by `created_at DESC, id DESC`.

### Filter by credit

```bash
curl -sS -w "\nHTTP %{http_code}\n" \
  "$BASE_URL/api/v1/accounts/$ACCOUNT_ID/transactions?type=credit"
```

### Filter by debit

```bash
curl -sS -w "\nHTTP %{http_code}\n" \
  "$BASE_URL/api/v1/accounts/$ACCOUNT_ID/transactions?type=debit"
```

### Paginate

```bash
curl -sS -w "\nHTTP %{http_code}\n" \
  "$BASE_URL/api/v1/accounts/$ACCOUNT_ID/transactions?page=1&limit=2"
```

```bash
curl -sS -w "\nHTTP %{http_code}\n" \
  "$BASE_URL/api/v1/accounts/$ACCOUNT_ID/transactions?page=2&limit=2"
```

Defaults: `page=1`, `limit=10`. Maximum `limit` is `100`.

### Empty history

```bash
curl -sS -w "\nHTTP %{http_code}\n" \
  "$BASE_URL/api/v1/accounts/$SECOND_ACCOUNT_ID/transactions?page=99"
```

A page past the end returns an empty `data` array and the real totals. A new account with no transactions:

```bash
curl -sS -w "\nHTTP %{http_code}\n" \
  "$BASE_URL/api/v1/accounts/$EMPTY_ACCOUNT_ID/transactions"
```

returns:

```json
{
  "success": true,
  "data": [],
  "pagination": {
    "page": 1,
    "limit": 10,
    "total_records": 0,
    "total_pages": 0
  }
}
```

### Invalid filter type

```bash
curl -sS -w "\nHTTP %{http_code}\n" \
  "$BASE_URL/api/v1/accounts/$ACCOUNT_ID/transactions?type=hold"
```

Expected `422 INVALID_TRANSACTION_TYPE`.

### Invalid pagination

```bash
curl -sS -w "\nHTTP %{http_code}\n" \
  "$BASE_URL/api/v1/accounts/$ACCOUNT_ID/transactions?page=0"
```

```bash
curl -sS -w "\nHTTP %{http_code}\n" \
  "$BASE_URL/api/v1/accounts/$ACCOUNT_ID/transactions?limit=101"
```

Both return `422 INVALID_PAGINATION`.

### History for an unknown account

```bash
curl -sS -w "\nHTTP %{http_code}\n" \
  "$BASE_URL/api/v1/accounts/00000000-0000-0000-0000-000000000000/transactions"
```

Expected `404 ACCOUNT_NOT_FOUND`.

## Transfers

### Create a transfer

The source account must have enough balance.

```bash
curl -sS -w "\nHTTP %{http_code}\n" \
  -X POST "$BASE_URL/api/v1/transfers" \
  -H "Content-Type: application/json" \
  -d '{
    "source_account_id": "'"$ACCOUNT_ID"'",
    "destination_account_id": "'"$SECOND_ACCOUNT_ID"'",
    "amount": "100.00",
    "reference_id": "TRANSFER-001",
    "description": "Payment"
  }'
```

Expected `201`:

```json
{
  "success": true,
  "data": {
    "id": "e8f7698c-fde7-4add-ab60-c4833e9b633b",
    "source_account_id": "4a3af89c-92ab-4502-b18c-38a6c08fce5a",
    "destination_account_id": "1088e15a-1173-4014-9312-ae73a6355a85",
    "amount": "100.00",
    "description": "Payment",
    "reference_id": "TRANSFER-001",
    "created_at": "2026-10-27T11:54:49.427121+05:30",
    "debit_transaction_id": "8dadb9b0-cdb9-44ab-90a1-06cc24bf5651",
    "credit_transaction_id": "24dd299e-9920-471f-9d6a-3ae038cfb6e3"
  }
}
```

The source balance decreases by `100.00`, the destination balance increases by `100.00`, and two immutable ledger entries are created.

### Duplicate transfer reference

Repeat the transfer with the same `reference_id`:

```bash
curl -sS -w "\nHTTP %{http_code}\n" \
  -X POST "$BASE_URL/api/v1/transfers" \
  -H "Content-Type: application/json" \
  -d '{
    "source_account_id": "'"$ACCOUNT_ID"'",
    "destination_account_id": "'"$SECOND_ACCOUNT_ID"'",
    "amount": "100.00",
    "reference_id": "TRANSFER-001"
  }'
```

Expected `409`:

```json
{
  "success": false,
  "error": {
    "code": "DUPLICATE_TRANSFER",
    "message": "A transfer with this reference_id already exists.",
    "details": {
      "reference_id": "TRANSFER-001"
    }
  }
}
```

Money does not move twice.

### Same source and destination

```bash
curl -sS -w "\nHTTP %{http_code}\n" \
  -X POST "$BASE_URL/api/v1/transfers" \
  -H "Content-Type: application/json" \
  -d '{
    "source_account_id": "'"$ACCOUNT_ID"'",
    "destination_account_id": "'"$ACCOUNT_ID"'",
    "amount": "10.00",
    "reference_id": "TRANSFER-SAME"
  }'
```

Expected `400 SAME_ACCOUNT_TRANSFER`.

### Insufficient source balance

```bash
curl -sS -w "\nHTTP %{http_code}\n" \
  -X POST "$BASE_URL/api/v1/transfers" \
  -H "Content-Type: application/json" \
  -d '{
    "source_account_id": "'"$ACCOUNT_ID"'",
    "destination_account_id": "'"$SECOND_ACCOUNT_ID"'",
    "amount": "999999.00",
    "reference_id": "TRANSFER-INSUFFICIENT"
  }'
```

Expected `400 INSUFFICIENT_BALANCE`. Neither balance changes and no ledger entries are created.

### Nonexistent source or destination

```bash
curl -sS -w "\nHTTP %{http_code}\n" \
  -X POST "$BASE_URL/api/v1/transfers" \
  -H "Content-Type: application/json" \
  -d '{
    "source_account_id": "00000000-0000-0000-0000-000000000000",
    "destination_account_id": "'"$SECOND_ACCOUNT_ID"'",
    "amount": "10.00",
    "reference_id": "TRANSFER-MISSING"
  }'
```

Expected `404 ACCOUNT_NOT_FOUND`.

### Invalid transfer amount

```bash
curl -sS -w "\nHTTP %{http_code}\n" \
  -X POST "$BASE_URL/api/v1/transfers" \
  -H "Content-Type: application/json" \
  -d '{
    "source_account_id": "'"$ACCOUNT_ID"'",
    "destination_account_id": "'"$SECOND_ACCOUNT_ID"'",
    "amount": "0.00",
    "reference_id": "TRANSFER-ZERO"
  }'
```

Expected `422 INVALID_AMOUNT`.

### Invalid transfer UUID

```bash
curl -sS -w "\nHTTP %{http_code}\n" \
  -X POST "$BASE_URL/api/v1/transfers" \
  -H "Content-Type: application/json" \
  -d '{
    "source_account_id": "not-a-uuid",
    "destination_account_id": "'"$SECOND_ACCOUNT_ID"'",
    "amount": "10.00",
    "reference_id": "TRANSFER-BAD-UUID"
  }'
```

Expected `422 INVALID_ACCOUNT_ID`.

### Missing reference_id

```bash
curl -sS -w "\nHTTP %{http_code}\n" \
  -X POST "$BASE_URL/api/v1/transfers" \
  -H "Content-Type: application/json" \
  -d '{
    "source_account_id": "'"$ACCOUNT_ID"'",
    "destination_account_id": "'"$SECOND_ACCOUNT_ID"'",
    "amount": "10.00"
  }'
```

Expected `422 INVALID_REFERENCE_ID`.

### Unexpected field

```bash
curl -sS -w "\nHTTP %{http_code}\n" \
  -X POST "$BASE_URL/api/v1/transfers" \
  -H "Content-Type: application/json" \
  -d '{
    "source_account_id": "'"$ACCOUNT_ID"'",
    "destination_account_id": "'"$SECOND_ACCOUNT_ID"'",
    "amount": "10.00",
    "reference_id": "TRANSFER-EXTRA",
    "balance": "100.00"
  }'
```

Expected `422 VALIDATION_ERROR`.

## Generic Errors

### Unknown route

```bash
curl -sS -w "\nHTTP %{http_code}\n" "$BASE_URL/api/v1/does-not-exist"
```

Expected `404`:

```json
{
  "success": false,
  "error": {
    "code": "NOT_FOUND",
    "message": "Not Found"
  }
}
```

### Unsupported method

```bash
curl -sS -w "\nHTTP %{http_code}\n" \
  -X PATCH "$BASE_URL/api/v1/accounts" \
  -H "Content-Type: application/json" \
  -d '{}'
```

Expected `405 METHOD_NOT_ALLOWED`.

## Optional End-to-End Flow

Requires `bash` and `jq`.

```bash
#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"

json() {
  local method="$1"
  local url="$2"
  local body="${3:-}"

  if [[ -n "$body" ]]; then
    curl -sS -X "$method" "$url" -H "Content-Type: application/json" -d "$body"
  else
    curl -sS -X "$method" "$url"
  fi
}

ALICE=$(json POST "$BASE_URL/api/v1/accounts" '{"name":"Alice"}' | jq -r '.data.id')
BOB=$(json POST "$BASE_URL/api/v1/accounts" '{"name":"Bob"}' | jq -r '.data.id')

json POST "$BASE_URL/api/v1/accounts/$ALICE/transactions" '{
  "type": "credit",
  "amount": "500.00",
  "reference_id": "REF-001"
}' | jq

json POST "$BASE_URL/api/v1/transfers" "{
  \"source_account_id\": \"$ALICE\",
  \"destination_account_id\": \"$BOB\",
  \"amount\": \"100.00\",
  \"reference_id\": \"TRANSFER-001\"
}" | jq

echo "Alice"
json GET "$BASE_URL/api/v1/accounts/$ALICE/balance" | jq

echo "Bob"
json GET "$BASE_URL/api/v1/accounts/$BOB/balance" | jq

echo "Alice history"
json GET "$BASE_URL/api/v1/accounts/$ALICE/transactions?limit=100" | jq
```

Expected final balances:

```text
Alice: 400.00
Bob:   100.00
```

## Status Codes

| Status | Meaning |
| --- | --- |
| 200 | Successful retrieval |
| 201 | Account, transaction, or transfer created |
| 400 | Insufficient balance, balance limit exceeded, or same-account transfer |
| 404 | Account or route not found |
| 405 | Method not allowed |
| 409 | Duplicate reference or conflicting database state |
| 422 | Request validation failure |
| 500 | Unexpected server failure |
| 503 | Health check reports the database unavailable |

## Error Codes

| Code | Meaning |
| --- | --- |
| `VALIDATION_ERROR` | Generic request validation failure |
| `INVALID_AMOUNT` | Amount is zero, negative, a float, too precise, or too large |
| `INVALID_TRANSACTION_TYPE` | Type is not `credit` or `debit` |
| `INVALID_REFERENCE_ID` | Reference is missing, blank, or too long |
| `INVALID_ACCOUNT_ID` | Account UUID is malformed |
| `INVALID_PAGINATION` | `page` or `limit` is outside the allowed range |
| `ACCOUNT_NOT_FOUND` | Account does not exist |
| `INSUFFICIENT_BALANCE` | Debit or transfer exceeds available funds |
| `BALANCE_LIMIT_EXCEEDED` | Resulting balance exceeds `9999999999999999.99` |
| `DUPLICATE_TRANSACTION` | Reference already used on this account |
| `DUPLICATE_TRANSFER` | Transfer reference already used |
| `SAME_ACCOUNT_TRANSFER` | Source and destination are identical |
| `CONFLICT` | Generic database conflict |
| `METHOD_NOT_ALLOWED` | Unsupported HTTP method |
| `NOT_FOUND` | Route not found |
| `DATABASE_ERROR` | Database failure |
| `INTERNAL_ERROR` | Unexpected server failure |
