# VaultLine Verify

VaultLine Verify is a financial-evidence verification prototype prepared for the **Meta Global AI
Developer Hackathon — Startup Track**. It helps reviewers compare invoices with purchase orders,
trace discrepancies to source evidence, and investigate potentially competing recorded financing
claims. Use the supplied synthetic data for local demonstrations.

**Status: hackathon prototype, not production-ready.** Authentication and authorization are not
implemented. Document-check outcomes do not establish legal identity, ownership, enforceability,
actual financing or fraud. No financing decision is made. This is a registry of assertions recorded
in VaultLine, not a global financing registry; no detected conflict is not proof of no external financing.

## Implemented hackathon work

The implementation in this working tree extends the initial engineering-guidelines checkpoint
(`34e9db1`). The following features were built for this hackathon prototype; this is a capability
inventory, not independent confirmation of competition eligibility or development dates.

| Capability | Implemented behavior |
| --- | --- |
| Case management and ingestion | Case-scoped invoice/PO uploads, checksums, persisted document types |
| Deterministic extraction | Field/value CSV and labeled text PDF schemas; Decimal amounts and source provenance |
| Cross-document verification | PO reference, supplier/buyer/currency, dates, totals and supported line checks |
| Duplicate invoice detection | Exact invoice-number flags within stored VaultLine data, not receivable identity proof |
| Financing claim registry | Persistent proposed/active/released/cancelled assertions, status history and evidence snapshots |
| Potential claim conflicts | Conservative cross-case invoice-evidence matching and aggregate active-amount checks |
| Investigation orchestration | Minimized evidence packages, strict schema/reference validation, persisted reports/errors |
| Meta provider adapter | `muse-spark-1.3` via Meta Model API, separate from provider-independent orchestration |
| Demonstration and tests | Clearly labeled synthetic cases, rollback-only demo, offline mock-provider tests and Chromium journeys |

Risk scoring, AI-based extraction, OCR, external lender lookup and automated loan decisions are
not implemented. Navigation placeholders are not completed product modules.

## Meta integration: implementation versus live testing

The Meta adapter uses `https://api.meta.ai/v1/chat/completions`, bearer authentication and JSON-schema
output. The runtime default remains Meta; failed calls never silently become mock output. It reads
`MODEL_API_KEY` only from the backend process environment. Never put keys in `NEXT_PUBLIC_*` settings.

**Successful live Meta inference has not been validated.** A current account billing restriction is
an external testing blocker. No account identifiers or billing details are needed for this repository.
No live Meta request was executed during release preparation. Do not run the opt-in smoke script
while this blocker remains. Adapter tests use HTTPX MockTransport; successful mock investigation
output does not demonstrate real model quality, access or availability.

The interactive synthetic demo explicitly disables live requests before credentials are read.
Only test applications explicitly inject `MockAIProvider`; browser reports carry a TEST ONLY label.
See [investigation contracts and configuration](apps/api/INVESTIGATIONS.md).

## Architecture

A modular monolith: Next.js/TypeScript/Tailwind frontend; Python 3.12/FastAPI/Pydantic v2 backend;
PostgreSQL 16/SQLAlchemy/Alembic persistence. Provider-specific HTTP code is separate from
investigation orchestration and deterministic financial rules. Local infrastructure uses Docker Compose.
Money uses Decimal and decimal-string API values, with explicit supported currencies and rounding rules.

## Local setup

Prerequisites: Python 3.12, uv, Node.js >=20.9, npm, Docker and Docker Compose v2. The commands
below assume a repository checkout and an intended local development database. Do not overwrite
existing environment files, reset an existing database, or remove volumes.

For a **fresh** configuration, copy examples only when their destination does not exist:

```bash
test -e .env || cp .env.example .env
test -e apps/api/.env || cp apps/api/.env.example apps/api/.env
```

Privately set a unique local PostgreSQL password in both files, keeping database host/port/name/user
consistent. Example values are placeholders, not usable release credentials. The API reads
`apps/api/.env` when launched from that directory; Compose reads the root `.env`. No Meta key is
needed for deterministic checks, the offline demo or automated tests.

```bash
docker compose up -d --wait postgres
(cd apps/api && uv sync --dev)
(cd apps/web && npm ci)
```

PostgreSQL is bound to loopback port 5433 by default. For a persistent local development instance,
apply migrations only to your intended development database (back up valuable existing data first):

```bash
cd apps/api
uv run alembic upgrade head
CORS_ALLOWED_ORIGINS='["http://127.0.0.1:3000"]' uv run uvicorn vaultline_api.main:app --host 127.0.0.1 --port 8001
```

In another terminal, from the repository root:

```bash
cd apps/web
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8001 npm run dev -- --hostname 127.0.0.1 --port 3000
```

Open `http://127.0.0.1:3000/cases`; API docs are at `http://127.0.0.1:8001/docs`.
Use synthetic data only. Uploaded bytes go to ignored `.local/evidence` by default; configured
storage outside that path also needs private handling and must never be staged. `/health` is
process health; `/ready` checks PostgreSQL connectivity. Neither is a production-security assessment.

## Reproducible demonstration

See [DEMO.md](DEMO.md) for a seeded, rollback-only PostgreSQL schema and temporary evidence storage
that leave existing cases and migration history unchanged. With dependencies installed and PostgreSQL
reachable, use two terminals:

```bash
# Terminal 1, from the repository root
cd apps/api
uv run python scripts/demo.py
```

```bash
# Terminal 2, from the repository root
cd apps/web
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8101 VAULTLINE_NEXT_DIST_DIR=.next-demo npm run dev -- --hostname 127.0.0.1 --port 3100
```

Open `http://127.0.0.1:3100/cases`. The five synthetic cases show matching documents, deliberate
amount/price discrepancies, two lenders with potential competing claims, and missing evidence.
Stop those two demo processes with Ctrl-C to end the session; the demo schema is rolled back.

## Validation

From the repository root, with PostgreSQL reachable and the development database migrated:

```bash
python3 scripts/release_check.py
python3 -m unittest discover -s scripts -p 'test_release_check.py'
(cd apps/api && uv run pytest -q)
(cd apps/api && uv run ruff check src tests scripts && uv run ruff format --check src tests scripts)
(cd apps/api && uv run alembic current && uv run alembic heads && uv run alembic check)
(cd apps/web && npm run lint && npm run build)
(cd apps/web && npx playwright install chromium --no-shell && npm run test:e2e)
```

The release scan is offline and redacts findings; it scans worktree candidates, staged blobs and
reachable commit file history, but is heuristic and cannot prove secret absence. Automated tests
use synthetic fixtures and rollback-based PostgreSQL isolation. Routine pytest blocks live HTTP;
browser tests use their own isolated API/frontend on 8102/3101 and abort external requests.
No live Meta request is part of these checks. See [release preparation](RELEASE_PREPARATION.md)
for the recorded validation results, complete Git inventory and checkpoint instructions.

## Documentation and limits

- [Synthetic demo walkthrough](DEMO.md)
- [Backend setup](apps/api/README.md) and [frontend setup](apps/web/README.md)
- [Extraction schemas and provenance](apps/api/EXTRACTION.md)
- [Deterministic verification rules](apps/api/VERIFICATION.md)
- [Recorded financing claims](apps/api/CLAIMS.md)
- [Evidence-grounded investigations](apps/api/INVESTIGATIONS.md)

Source observations and recorded claims remain unverified assertions. Matching is conservative
text/evidence comparison, not legal-entity identification. Arbitrary/scanned PDFs, currency conversion,
cumulative PO utilization and external financing coverage are unsupported. AI reports use bounded
language and source references. Access controls, operational hardening, large-dataset scaling,
retention policies and production deployment are outside this prototype.

## License decision pending

No repository-level license has been selected or added. Package metadata is marked `UNLICENSED`
to remove an unsupported scaffold ISC declaration; this does not select a project license. The owner
must decide and document the license and verify dependency/asset obligations before public release.
Do not describe this repository as permissively licensed or open source until that decision is made.
