# VaultLine Verify API

Python 3.12/FastAPI backend with case management, deterministic extraction and verification,
financing claim assertions/conflicts, source provenance, evidence-grounded investigations and
deterministic categorical risk indicators.
See the [root README](../../README.md) for setup, hackathon capabilities and release limitations.

## Configuration and startup

For a fresh checkout only, create missing root/API `.env` files from their `.env.example` files.
Privately configure a unique PostgreSQL password in both; never overwrite an existing environment
file or put real secrets in examples. Compose reads the root configuration; API settings load
`.env` relative to the working directory, so launch from `apps/api`. JSON-array CORS origins must
match the frontend origin. The PostgreSQL Compose service binds to loopback port 5433 by default.

```bash
# From the repository root, after local configuration
docker compose up -d --wait postgres
cd apps/api
uv sync --dev
# Only against the intended local development database; never reset it.
uv run alembic upgrade head
CORS_ALLOWED_ORIGINS='["http://127.0.0.1:3000"]' uv run uvicorn vaultline_api.main:app --host 127.0.0.1 --port 8001
```

API docs: `http://127.0.0.1:8001/docs`. `/health` checks the process; `/ready` queries PostgreSQL.
No authentication/authorization exists. Bind to localhost and use synthetic data only. Evidence
is private local storage with checksums, not a public file download service. Configure
`EVIDENCE_STORAGE_DIR` deliberately; its default is ignored repository `.local/evidence`.
Never commit documents, extraction output, local database dumps or secrets.

## Implemented modules

- [EXTRACTION.md](EXTRACTION.md): field/value CSV and labeled text-PDF schemas, Decimal amounts,
  validation and source provenance. Extraction is deterministic; OCR is unsupported.
- [VERIFICATION.md](VERIFICATION.md): case-scoped invoice/PO comparisons and exact-number duplicate
  flags. Saved runs/findings remain historical; checks do not establish legal rights or fraud.
- [CLAIMS.md](CLAIMS.md): persistent financing assertions, status history and deterministic potential
  conflicts within recorded VaultLine data. Recorded claims do not prove actual financing.
- [INVESTIGATIONS.md](INVESTIGATIONS.md): provider-independent orchestration, strict grounding,
  saved evidence/report/error records and the Meta adapter.

- [RISK.md](RISK.md): read-only categorical indicators with exact evidence references, freshness
  checks, reproducible inputs and mandatory human review. No predictive score or loan decision.

The Meta API integration is implemented, but successful live inference remains unvalidated because
of an external account billing restriction. Do not run the live smoke script during this restriction.
Keys are read only from the backend process environment; no key is needed for automated tests.
There is no silent mock fallback. The normal runtime provider remains Meta.

## Tests and demo

From `apps/api`, with the existing development database at migration head:

```bash
uv run pytest -q
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
uv run alembic current
uv run alembic heads
uv run alembic check
```

Tests use synthetic fixtures and PostgreSQL rollback/savepoint isolation; migration round trips run
only in isolated schemas. They require database connectivity and CREATE SCHEMA permission. No test
requires a live model key; normal pytest blocks external HTTP. The database must not be reset.

[DEMO.md](../../DEMO.md) documents the reproducible `uv run python scripts/demo.py` walkthrough,
shared synthetic files and browser tests. The demo uses temporary storage and a rollback-only
schema, with live Meta requests explicitly disabled. MockAIProvider success is tested only inside
explicit test applications. No financing approval, ownership verification or fraud determination exists.

### Read-only provider diagnostics

`GET /system/provider` reports provider/model, local configuration, prerequisite-based availability
and `live_validation: untested`. It uses the investigation provider dependency (including explicit
isolated demo/test overrides), never calls `generate`, and never returns credential values. Meta
is `configured` only when its process key is present; missing keys, missing sharing approval or
disabled requests yield unavailable inference. Meeting prerequisites yields `untested`, never
operational/available. Explicit non-Meta test adapters are labeled `test_only`.
