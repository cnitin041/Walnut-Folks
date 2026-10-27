# Architecture

## Overview

The application is a synchronous FastAPI service backed by PostgreSQL. It exposes accounts, ledger transactions, transaction history, and atomic transfers. The design keeps money arithmetic in `Decimal`, keeps the ledger append-only at the API level, and treats the account balance as a cached aggregate.

The main correctness goals are:

- One ledger entry per successful credit or debit.
- The balance update and ledger insert commit together or not at all.
- Concurrent requests cannot overdraw an account or commit duplicate references.
- A transfer creates exactly one debit, one credit, and two balance updates in one transaction.
- Stored balances always match the ledger.

## Main Components

| Component | Responsibility |
| --- | --- |
| `app/main.py` | Creates the FastAPI app, includes routers, installs exception handlers, configures logging |
| `app/routers/` | HTTP boundary: path/query/body validation, status codes, response models |
| `app/dependencies.py` | Shared `SessionDep` dependency (`Annotated[Session, Depends(get_db)]`) |
| `app/schemas/` | Pydantic request/response contracts, money serializers, pagination metadata |
| `app/services/` | Business rules, row locking, transaction boundaries, duplicate handling |
| `app/models/` | SQLAlchemy ORM models and database constraints |
| `app/db/` | Declarative base, engine, session factory, request-scoped session dependency |
| `app/core/` | Environment-backed settings and logging setup |
| `app/exceptions.py` | Application error hierarchy and the shared error envelope |
| `migrations/` | Alembic environment and the initial schema revision |
| `tests/` | PostgreSQL-backed API, concurrency, rollback, and consistency tests |

## Request Lifecycle

1. Uvicorn receives an HTTP request.
2. FastAPI routes it through the matching router.
3. Pydantic validates the body, path UUIDs, and query parameters. Invalid input becomes a `RequestValidationError` and is converted to the shared `422` envelope.
4. FastAPI resolves `SessionDep`, which opens a SQLAlchemy session from the application engine.
5. The router calls a service function inside a `def` endpoint. FastAPI runs synchronous endpoints in its thread pool, so blocking database work does not block the event loop.
6. The service opens one explicit transaction with `session.begin()`, performs the business operation, and commits on success.
7. The router returns ORM objects or plain dictionaries. FastAPI serializes them through the declared response model, including the Decimal-to-string serializer.
8. `get_db` closes the session after the response is produced.
9. If an application error, validation error, integrity error, database error, or unexpected exception escapes, the matching handler returns the shared error envelope. Database details are logged, not exposed.

`expire_on_commit=False` keeps loaded attributes available after commit so response serialization does not need another query. Creation timestamps are populated from PostgreSQL defaults through SQLAlchemy's `RETURNING` support during flush.

## Database Tables and Relationships

```text
accounts
  id            UUID PK
  name          VARCHAR(255) NOT NULL, CHECK btrim(name) <> ''
  balance       NUMERIC(18,2) NOT NULL DEFAULT 0.00, CHECK balance >= 0
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()

transfers
  id                     UUID PK
  source_account_id      UUID NOT NULL -> accounts.id (ON DELETE RESTRICT)
  destination_account_id UUID NOT NULL -> accounts.id (ON DELETE RESTRICT)
  amount                 NUMERIC(18,2) NOT NULL, CHECK amount > 0
  reference_id           VARCHAR(255) NOT NULL, UNIQUE
  description            VARCHAR(1000) NOT NULL DEFAULT ''
  created_at             TIMESTAMPTZ NOT NULL DEFAULT now()
  CHECK source_account_id <> destination_account_id

transactions
  id            UUID PK
  account_id    UUID NOT NULL -> accounts.id (ON DELETE RESTRICT)
  transfer_id   UUID NULL -> transfers.id (ON DELETE RESTRICT)
  type          VARCHAR(10) NOT NULL, CHECK type IN ('credit', 'debit')
  amount        NUMERIC(18,2) NOT NULL, CHECK amount > 0
  reference_id  VARCHAR(255) NOT NULL
  description   VARCHAR(1000) NOT NULL DEFAULT ''
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
  UNIQUE (account_id, reference_id)
  UNIQUE (transfer_id, type)
```

Relationship summary:

- One account has many transactions.
- One transfer has zero or two transactions. Successful transfers have exactly one debit and one credit.
- A standalone credit/debit has `transfer_id = NULL`.
- Deleting accounts or transfers is restricted by foreign keys. The API exposes no delete operations.

Indexes support the history query shapes:

- `(account_id, created_at, id)` for unfiltered history and newest-first pagination.
- `(account_id, type, created_at, id)` for filtered history.
- `(transfer_id)` for transfer-to-ledger lookups.
- `(source_account_id, created_at, id)` and `(destination_account_id, created_at, id)` for transfer lookups.

The `UNIQUE(transfer_id, type)` constraint uses nullable `transfer_id`. PostgreSQL treats `NULL` values as distinct, so standalone transactions are not constrained by it.

## Money Representation

- Python: `decimal.Decimal`.
- PostgreSQL: `NUMERIC(18, 2)`.
- JSON input: decimal strings such as `"500.00"` or integers such as `500`; floats are rejected by a Pydantic `BeforeValidator`.
- JSON output: strings such as `"500.00"`, enforced by a Pydantic `PlainSerializer`.
- Constraints: amounts are `> 0` with at most 18 total digits and 2 decimal places; balances are `>= 0` and at most `9999999999999999.99`. Operations that would exceed the maximum balance return `400 BALANCE_LIMIT_EXCEEDED`.

Using `response_model` plus the serializer matters because FastAPI's default JSON encoder would otherwise convert `Decimal` to a JSON number, losing the explicit decimal-string contract.

## Credit and Debit Processing

Both types use the same algorithm:

1. Open one transaction with `session.begin()`.
2. Lock the account row with `SELECT ... FOR UPDATE`.
3. Return `404` if the account does not exist.
4. Query for an existing `(account_id, reference_id)` pair. Return `409` if found.
5. Compute the new balance:
   - Credit: `balance + amount`.
   - Debit: `balance - amount`.
6. For a debit, return `400 INSUFFICIENT_BALANCE` if the new balance would be negative. The transaction rolls back and the balance is untouched.
7. Insert the ledger entry and assign the new balance to the locked account.
8. Flush and commit. Any exception rolls back both the balance update and the ledger insert.
9. Return the created transaction.

The account lock is the key serialization point. Two concurrent debits against the same account cannot both read the same starting balance; the second request waits for the first to commit and then re-reads the committed balance.

## Atomicity Enforcement

- The balance update and ledger insert happen in the same SQLAlchemy transaction.
- The service uses `session.begin()`, so there is exactly one transaction boundary and no nested transaction.
- `flush()` surfaces database constraint violations before commit.
- On `IntegrityError`, the service calls `session.rollback()` before translating or re-raising the error. This releases locks and leaves the session usable.
- `accounts.balance >= 0`, `amount > 0`, type checks, and foreign keys provide database-level protection in addition to Pydantic validation.
- Tests simulate a ledger insert failure and a balance update failure and verify that neither the balance nor a ledger entry is committed.

## Duplicate Prevention

Three layers protect against duplicate transaction references:

1. The client-supplied `reference_id` is validated and stripped.
2. The account row is locked, then the service queries for the reference under that lock. This returns a clear `409` in the normal duplicate case.
3. `UNIQUE(account_id, reference_id)` in PostgreSQL is the final protection. If two requests somehow reach the database concurrently, one insert wins and the other raises `IntegrityError`. The service rolls back and maps the constraint name to `DUPLICATE_TRANSACTION`.

The same reference may be reused on a different account because the constraint includes `account_id`.

Transfer duplicates are protected by the globally unique `transfers.reference_id` plus a pre-insert lookup under the account locks. A concurrent duplicate either sees the committed transfer or loses the unique-constraint race; both cases return `409 DUPLICATE_TRANSFER` without moving money twice.

## Concurrency and Locking

- Isolation: PostgreSQL's default `READ COMMITTED`.
- Account updates: `SELECT ... FOR UPDATE` on the account row before validation and mutation.
- Transfer lock order: both account rows are locked one at a time in ascending UUID string order. Every transfer uses the same order, so opposite-direction transfers cannot form a lock cycle.
- Session lifecycle: one session per request; services own the transaction boundary; sessions are closed by the dependency after the response.
- Connection handling: the engine uses `pool_pre_ping=True`; sessions are not held across requests.
- Error handling: unique violations are the only expected integrity errors in normal operation. They are mapped to `409`. Other integrity errors and SQLAlchemy errors are logged and returned as generic errors without leaking internals.
- No application-level mutex is used. Database row locks are the source of serialization, which works across multiple application processes and hosts.

The concurrency tests exercise:

- Five simultaneous duplicate credits: exactly one commits, the rest return `409`.
- Two simultaneous debits of 80.00 and 70.00 against a 100.00 balance: exactly one succeeds; the balance becomes 20.00 or 30.00 and never negative.
- Opposite-direction transfers between the same two accounts: both succeed without deadlock because of consistent lock ordering.
- Simultaneous duplicate transfers: one commits, one returns `409`, and money moves once.

## Transfer Processing

A transfer performs the following in one database transaction:

1. Reject identical source and destination IDs with `400 SAME_ACCOUNT_TRANSFER`.
2. Lock both accounts in ascending UUID order with `SELECT ... FOR UPDATE`.
3. Return `404` if either account is missing.
4. Query for an existing transfer reference. Return `409` if found.
5. Check the source balance. Return `400 INSUFFICIENT_BALANCE` if insufficient.
6. Insert the `transfers` row and flush it to obtain its generated UUID.
7. Insert one debit transaction on the source and one credit transaction on the destination:
   - `reference_id = transfer:<transfer_id>:debit`
   - `reference_id = transfer:<transfer_id>:credit`
   - both share `transfer_id`
8. Apply both cached balance changes.
9. Flush and commit. Any failure rolls back the transfer row, both ledger entries, and both balance changes.
10. Return the transfer plus both ledger entry IDs.

Because both ledger entries and both balance updates are committed with the transfer row, a successful transfer cannot leave the ledger unbalanced. Tests verify the two ledger entries, their account IDs, types, amounts, derived references, and both resulting balances.

## Error Handling

| Handler | Result |
| --- | --- |
| `AppError` subclasses | Mapped status and code, for example `404 ACCOUNT_NOT_FOUND`, `400 INSUFFICIENT_BALANCE`, `409 DUPLICATE_TRANSACTION` |
| `RequestValidationError` | `422` with field-level details and a specific code when detectable (`INVALID_AMOUNT`, `INVALID_TRANSACTION_TYPE`, `INVALID_REFERENCE_ID`, `INVALID_ACCOUNT_ID`, `INVALID_PAGINATION`) |
| `StarletteHTTPException` | `404 NOT_FOUND`, `405 METHOD_NOT_ALLOWED`, or generic HTTP error |
| `IntegrityError` | Rolls back at the service layer where it occurs; fallback handler returns `409 CONFLICT` without database details |
| `SQLAlchemyError` | Logged; returns `500 DATABASE_ERROR` |
| Unexpected `Exception` | Logged; returns `500 INTERNAL_ERROR` |

The response envelope is always:

```json
{
  "success": false,
  "error": {
    "code": "CODE",
    "message": "Human-readable message",
    "details": {}
  }
}
```

## Balance Consistency and Reconciliation

The ledger is the source of truth; `accounts.balance` is a cache. The automated consistency test recomputes each account balance from every ledger entry and compares it with the stored balance. It also verifies that transfer debit and credit totals are equal.

In production, a reconciliation process would:

1. Recompute balances from the ledger using a consistent database snapshot.
2. Compare them with cached balances and record mismatches with account ID, expected value, stored value, and timestamp.
3. Alert operators and investigate the root cause.
4. Correct discrepancies by appending compensating ledger entries with unique references, never by editing or deleting history.
5. Rebuild caches from the ledger only as a controlled maintenance operation after the ledger is verified.

This keeps the audit trail append-only and makes corrections traceable.

## Testing Strategy

- Real PostgreSQL only, because SQLite does not reproduce row-level locking, `SELECT FOR UPDATE`, or PostgreSQL constraint behavior.
- A separate test database is configured through `TEST_DATABASE_URL`.
- The test session applies Alembic migrations automatically and truncates `accounts`, `transfers`, and `transactions` between tests.
- HTTP behavior is tested through FastAPI's HTTPX-based test client with `get_db` overridden to the test session factory.
- Concurrency tests use a barrier and separate clients in a thread pool so requests overlap in the database.
- Rollback tests use SQLAlchemy `before_flush` listeners to simulate a failed ledger insert and a failed balance constraint check.
- The consistency test uses SQL aggregates over the ledger and compares them with every stored account balance.
