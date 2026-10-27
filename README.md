# Transaction Ledger API

A production-minded ledger API built with FastAPI, PostgreSQL, SQLAlchemy 2, Pydantic 2, and Alembic. It supports accounts, atomic credit/debit transactions, filtered and paginated transaction history, duplicate-reference protection, and atomic money transfers.

The account balance is a cached aggregate. The immutable transaction ledger is the source of truth.

## Features

- Create accounts with a server-generated UUID, zero balance, and server timestamp.
- Retrieve an account and its latest committed balance.
- Create credit and debit ledger entries atomically with the account balance update.
- Reject overdrafts, duplicate references, invalid amounts, and malformed requests.
- List transaction history with type filtering, page/limit pagination, newest-first sorting, and deterministic ordering.
- Transfer money between accounts in a single database transaction.
- Lock account rows with `SELECT ... FOR UPDATE` and lock transfer accounts in deterministic UUID order.
- Enforce critical integrity rules in PostgreSQL with checks, foreign keys, and unique constraints.
- Return a consistent JSON error envelope and use FastAPI's Swagger UI at `/docs`.
- Test against a real PostgreSQL test database, including concurrency and rollback scenarios.

## Technology Stack

- Python 3.12
- FastAPI 0.162
- PostgreSQL 18
- SQLAlchemy 2.1 (synchronous sessions)
- Pydantic 2.14 / pydantic-settings
- Alembic
- Psycopg 3
- Pytest + HTTPX
- Ruff

## Project Structure

```text
.
├── app/
│   ├── core/             # settings and logging
│   ├── db/               # declarative base, engine, session factory
│   ├── models/           # Account, Transaction, Transfer ORM models
│   ├── routers/          # health, accounts, transactions, transfers
│   ├── schemas/          # request/response models and money serialization
│   ├── services/         # business logic and transaction/locking rules
│   ├── dependencies.py   # shared FastAPI dependencies
│   ├── exceptions.py     # application errors and error envelope
│   └── main.py           # app factory setup and exception handlers
├── docs/
│   ├── api-examples.md
│   ├── architecture.md
│   └── assumptions.md
├── migrations/           # Alembic environment and versions
├── scripts/
│   ├── db.ps1            # local PostgreSQL cluster helper for Windows
│   └── docker-init.sql   # creates ledger_test for Docker
├── tests/                # account, transaction, history, transfer, concurrency, consistency
├── alembic.ini
├── docker-compose.yml
├── requirements.txt
└── pyproject.toml
```

## Prerequisites

- Python 3.12
- PostgreSQL 18 client/server tools, or Docker with Compose
- PowerShell 5.1+ on Windows for `scripts/db.ps1`

Docker is optional. The repository includes a local-cluster path and a Docker Compose path; use whichever is available.

### If PostgreSQL is not installed (Windows)

Install PostgreSQL 18 with `winget`:

```powershell
winget install --id PostgreSQL.PostgreSQL.18 -e
```

Or download the EDB installer with `wget` and run it:

```powershell
wget "https://get.enterprisedb.com/postgresql/postgresql-18.6-5-windows-x64.exe" -OutFile "$env:TEMP\postgresql-18-installer.exe"
Start-Process "$env:TEMP\postgresql-18-installer.exe" -Wait
```

PowerShell 5.1 aliases `wget` to `Invoke-WebRequest`, so the command above works without installing `wget`. In PowerShell 7, use `Invoke-WebRequest -Uri <url> -OutFile <path>`; in Git Bash with native `wget`, use `wget -O postgresql-18-installer.exe <url>`. Replace `18.6-5` with the current 18.x build from the [EDB download page](https://www.enterprisedb.com/downloads/postgres-postgresql-downloads).

Verify the installation and set `PG_BIN` if you installed to a non-default location:

```powershell
& "C:\Program Files\PostgreSQL\18\bin\psql.exe" --version
$env:PG_BIN = "C:\Program Files\PostgreSQL\18\bin"
```

If you cannot install PostgreSQL locally, use the [Docker PostgreSQL](#quick-start-docker-postgresql) path instead.

## Quick Start (Windows, local PostgreSQL)

1. Create and activate a virtual environment:

   ```powershell
   py -3.12 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

   If the `py` launcher is unavailable, use `python` instead:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

   If PowerShell blocks the activation script, bypass the execution policy for that command:

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\.venv\Scripts\Activate.ps1
   ```

   Or allow scripts for the current shell session only:

   ```powershell
   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
   .\.venv\Scripts\Activate.ps1
   ```

   On `cmd.exe`, use `.\.venv\Scripts\activate.bat`. In Git Bash, use `source .venv/Scripts/activate`.

2. Install dependencies:

   ```powershell
   .\.venv\Scripts\python.exe -m pip install --upgrade pip
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

   After activation, every `.\.venv\Scripts\<tool>.exe` command below can be replaced with `python -m <tool>` (for example, `python -m pytest`, `python -m alembic`, `python -m uvicorn`, or `python -m ruff`).

3. Create the environment file:

   ```powershell
   Copy-Item .env.example .env
   ```

4. Initialize and start the project-local PostgreSQL cluster on port `55432`, then create the development and test databases:

   ```powershell
   .\scripts\db.ps1 init
   ```

   If PowerShell blocks the script, run it with an execution-policy bypass:

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\scripts\db.ps1 init
   ```

   If the cluster already exists:

   ```powershell
   .\scripts\db.ps1 start
   .\scripts\db.ps1 create
   ```

   The script uses `C:\Program Files\PostgreSQL\18\bin` by default. Set `PG_BIN` if PostgreSQL is installed elsewhere. It uses trust authentication bound to localhost and is intended for local development only.

   Useful commands:

   ```powershell
   .\scripts\db.ps1 status
   .\scripts\db.ps1 stop
   .\scripts\db.ps1 reset   # destructive: removes .pgdata and recreates databases
   ```

5. Apply database migrations:

   ```powershell
   .\.venv\Scripts\alembic.exe upgrade head
   ```

   Apply them to the test database before running tests manually:

   ```powershell
   $env:DATABASE_URL = "postgresql+psycopg://postgres@127.0.0.1:55432/ledger_test"
   .\.venv\Scripts\alembic.exe upgrade head
   Remove-Item Env:\DATABASE_URL
   ```

   The test suite also runs `alembic upgrade head` against `TEST_DATABASE_URL` automatically.

6. Start the API:

   ```powershell
   .\.venv\Scripts\uvicorn.exe app.main:app --reload --host 127.0.0.1 --port 8000
   ```

   Or, with the virtual environment activated:

   ```powershell
   python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
   ```

7. Open Swagger UI at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) or ReDoc at [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc).

## Quick Start (Docker PostgreSQL)

Docker is an alternative to the local cluster. Stop the local cluster first if it is using port `55432`.

```powershell
docker compose up -d
docker compose ps
.\.venv\Scripts\alembic.exe upgrade head
```

The Compose service uses trust authentication, exposes PostgreSQL only on `127.0.0.1:55432`, creates the `ledger` database, and creates `ledger_test` through `scripts/docker-init.sql` on first initialization.

Reset the Docker database and its volume with:

```powershell
docker compose down -v
```

## Environment Variables

Copy `.env.example` to `.env` and adjust as needed.

| Variable | Required | Default | Purpose |
| --- | --- | --- | --- |
| `APP_NAME` | No | `Transaction Ledger API` | OpenAPI application title |
| `APP_ENV` | No | `development` | Environment label |
| `LOG_LEVEL` | No | `INFO` | Application log level |
| `DATABASE_URL` | Yes | local URL | SQLAlchemy URL for the application database |
| `TEST_DATABASE_URL` | Tests | local test URL | SQLAlchemy URL for the isolated test database |

Default URLs:

```text
postgresql+psycopg://postgres@127.0.0.1:55432/ledger
postgresql+psycopg://postgres@127.0.0.1:55432/ledger_test
```

Never commit `.env` or real credentials. `.env` and `.pgdata/` are ignored by Git.

## Database Migrations

```powershell
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\alembic.exe current
.\.venv\Scripts\alembic.exe downgrade -1
```

With the virtual environment activated, the same commands are:

```powershell
python -m alembic upgrade head
python -m alembic current
python -m alembic downgrade -1
```

The initial migration creates `accounts`, `transfers`, and `transactions` with checks, foreign keys, indexes, and unique constraints. `create_all()` is not used as the schema strategy.

## Running Tests

The test suite requires PostgreSQL and uses `TEST_DATABASE_URL`. It applies migrations automatically and truncates only the test tables between tests.

```powershell
.\.venv\Scripts\pytest.exe
```

Or, with the virtual environment activated:

```powershell
python -m pytest
```

Run lint and formatting checks:

```powershell
.\.venv\Scripts\ruff.exe check app tests migrations
.\.venv\Scripts\ruff.exe format --check app tests migrations
```

Or, with the virtual environment activated:

```powershell
python -m ruff check app tests migrations
python -m ruff format --check app tests migrations
```

The tests cover accounts, credits, debits, overdrafts, validation, duplicate references, history filtering/pagination/sorting, rollback on simulated failures, concurrent duplicate submissions, concurrent overdrafts, concurrent transfers, duplicate transfers, and balance/ledger consistency.

## Interactive API Documentation

Once the application is running, FastAPI serves interactive API documentation:

| Interface | URL |
| --- | --- |
| Swagger UI | [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) |
| ReDoc | [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc) |
| OpenAPI JSON | [http://127.0.0.1:8000/openapi.json](http://127.0.0.1:8000/openapi.json) |

Swagger UI supports trying requests directly from the browser. The OpenAPI schema includes request bodies, response models, status codes, error responses, and examples.

## API Endpoints

All business endpoints are under `/api/v1`.

| Method | Path | Description | Success |
| --- | --- | --- | --- |
| GET | `/health` | Application and database health | 200 |
| POST | `/api/v1/accounts` | Create an account | 201 |
| GET | `/api/v1/accounts/{account_id}` | Retrieve an account | 200 |
| GET | `/api/v1/accounts/{account_id}/balance` | Retrieve the latest balance | 200 |
| POST | `/api/v1/accounts/{account_id}/transactions` | Create a credit or debit entry | 201 |
| GET | `/api/v1/accounts/{account_id}/transactions` | List transaction history | 200 |
| POST | `/api/v1/transfers` | Transfer funds atomically | 201 |

### History query parameters

| Parameter | Default | Validation |
| --- | --- | --- |
| `type` | none | `credit` or `debit` |
| `page` | `1` | integer >= 1 |
| `limit` | `10` | integer from 1 to 100 |

History is sorted by `created_at DESC, id DESC`. `total_pages` is `0` when there are no matching records. A page past the end returns an empty `data` array with the real total counts.

## Example Requests

### Create an account

```http
POST /api/v1/accounts
Content-Type: application/json

{"name": "Rahul Sharma"}
```

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

### Credit an account

```http
POST /api/v1/accounts/4a3af89c-92ab-4502-b18c-38a6c08fce5a/transactions
Content-Type: application/json

{
  "type": "credit",
  "amount": "500.00",
  "description": "Initial deposit",
  "reference_id": "REF-001"
}
```

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

### Transfer funds

```http
POST /api/v1/transfers
Content-Type: application/json

{
  "source_account_id": "4a3af89c-92ab-4502-b18c-38a6c08fce5a",
  "destination_account_id": "1088e15a-1173-4014-9312-ae73a6355a85",
  "amount": "100.00",
  "reference_id": "TRANSFER-001",
  "description": "Payment"
}
```

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

### Transaction history

```http
GET /api/v1/accounts/4a3af89c-92ab-4502-b18c-38a6c08fce5a/transactions?type=debit&page=1&limit=20
```

```json
{
  "success": true,
  "data": [
    {
      "id": "b774896a-9a63-401e-9b3c-cf1e6451cb05",
      "account_id": "4a3af89c-92ab-4502-b18c-38a6c08fce5a",
      "type": "debit",
      "amount": "200.00",
      "description": "",
      "reference_id": "REF-002",
      "created_at": "2026-10-27T11:54:49.308438+05:30"
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total_records": 1,
    "total_pages": 1
  }
}
```

## Error Response Format

All application errors use the same envelope:

```json
{
  "success": false,
  "error": {
    "code": "INSUFFICIENT_BALANCE",
    "message": "Insufficient balance for this debit transaction.",
    "details": {
      "account_id": "4a3af89c-92ab-4502-b18c-38a6c08fce5a",
      "balance": "50.00",
      "requested_amount": "60.00"
    }
  }
}
```

Validation errors include field-level details:

```json
{
  "success": false,
  "error": {
    "code": "INVALID_AMOUNT",
    "message": "Request validation failed.",
    "details": {
      "errors": [
        {
          "field": "amount",
          "message": "must be provided as a decimal string or integer",
          "type": "value_error"
        }
      ]
    }
  }
}
```

### Status-code conventions

| Status | Meaning |
| --- | --- |
| 200 | Successful retrieval |
| 201 | Resource created |
| 400 | Business-rule violation: insufficient funds, balance limit, same-account transfer |
| 404 | Account or route not found |
| 405 | Method not allowed |
| 409 | Duplicate transaction/transfer reference or conflicting database state |
| 422 | Request validation failure |
| 500 | Unexpected server failure |
| 503 | Health check reports the database unavailable |

Error codes include `VALIDATION_ERROR`, `INVALID_AMOUNT`, `INVALID_TRANSACTION_TYPE`, `INVALID_REFERENCE_ID`, `INVALID_ACCOUNT_ID`, `INVALID_PAGINATION`, `ACCOUNT_NOT_FOUND`, `INSUFFICIENT_BALANCE`, `BALANCE_LIMIT_EXCEEDED`, `DUPLICATE_TRANSACTION`, `DUPLICATE_TRANSFER`, `SAME_ACCOUNT_TRANSFER`, `CONFLICT`, `METHOD_NOT_ALLOWED`, `NOT_FOUND`, `DATABASE_ERROR`, and `INTERNAL_ERROR`.

Database errors are logged server-side; credentials, SQL, and stack traces are never returned to clients.

## Important Design Decisions

- **Money:** `NUMERIC(18,2)` in PostgreSQL and `Decimal` in Python. JSON amounts are strings such as `"125.50"`; JSON floats are rejected. Money never uses binary floating point. Credits and transfers that would push a balance beyond `9999999999999999.99` are rejected with `400 BALANCE_LIMIT_EXCEEDED`.
- **Balance model:** `accounts.balance` is a cached aggregate. `transactions` is the immutable ledger and the source of truth. Every balance change commits with exactly one ledger entry.
- **Atomic transactions:** Each credit/debit runs in one database transaction. The account row is locked with `SELECT ... FOR UPDATE`; the balance is checked and updated, and the ledger entry is inserted before commit. Any failure rolls back both changes.
- **Concurrency:** Account row locks serialize concurrent changes to the same account. Transfers lock both accounts in ascending UUID order to avoid deadlocks. Unique constraints are the final protection against concurrent duplicate requests.
- **Duplicate references:** `UNIQUE(account_id, reference_id)` prevents duplicate transaction references per account while allowing the same reference on different accounts. A duplicate returns `409`.
- **Transfers:** A dedicated `transfers` row has a globally unique `reference_id`. Its debit and credit ledger entries share `transfer_id`, use `transfer:<transfer_id>:debit` and `transfer:<transfer_id>:credit` as their references, and are constrained by `UNIQUE(transfer_id, type)`. All changes commit together in one database transaction.
- **Timestamps and IDs:** UUID primary keys are generated by the application. Creation timestamps are generated by PostgreSQL (`now()`) with timezone.
- **Pagination:** Default page size 10, maximum 100. `total_pages` is zero for empty result sets.

See [docs/assumptions.md](docs/assumptions.md) and [docs/architecture.md](docs/architecture.md) for the full rationale. Copy-paste `curl` commands for every endpoint are in [docs/api-examples.md](docs/api-examples.md).

## Limitations and Assumptions

- Authentication and authorization are intentionally out of scope.
- The ledger is single-currency; no currency field or FX conversion is modeled.
- Transfer creation is supported; transfer retrieval/listing is not part of the assessment.
- History filtering supports only `type`; date-range filtering is not implemented.
- Duplicate reference submissions return `409` rather than replaying the original successful response. This is duplicate prevention, not full idempotent replay.
- Transactions cannot be changed or deleted through the API. A database-level immutability trigger is documented as a possible hardening step but is not included.
- The local PostgreSQL setup and Docker Compose use trust authentication restricted to localhost for development convenience.
- The consistency check is an automated test, not a runtime background reconciler.
- Concurrency is verified with PostgreSQL-backed HTTP tests; no production load test is included.

For production reconciliation and repair guidance, see [docs/assumptions.md](docs/assumptions.md).
