# Deterministic verification v1

Rule set: `vaultline.cross-document.v1.1`. This engine compares extracted observations and has no AI dependency. Results do not establish receivable ownership, enforceability, delivery, acceptance, or absence of fraud. No lending decision or fraud classification is made. Version 1.1 changes duplicate-check coverage handling; saved v1 runs retain their original version, findings and outcomes.

## Inputs and matching

Each run takes one consistent SQL snapshot of persisted documents, extraction fields, validation findings and field provenance. It does not re-extract documents or independently authenticate issuers. Every usable field must have exactly one matching source-provenance row with validation status `valid` and the same normalized value. Rounded, ambiguous, missing, unsupported and unproven values require review. An unextracted or needs_review document generates mandatory insufficient evidence even when some independent comparisons can be performed.

PO references are trimmed and compared exactly (case-sensitive). A reference must identify exactly one PO within the current case. No nearest or alternative PO is selected. An explicit nonmatching reference is a discrepancy only when available PO numbers are known; missing/ambiguous PO numbers prevent establishing a match.

Supplier and buyer text comparisons collapse whitespace and casefold. Punctuation, legal suffixes and substantive characters remain intact. Equality is solely a text check, not a legal-entity identification. Similar-looking names are never fuzzy-matched.

Supported currency codes must match exactly; there is no currency conversion. The engine uses the extraction currency subset USD/EUR/GBP/INR/JPY/KWD. Dates must be valid ISO dates. Invoice date must be on or after PO issue date; the PO has no delivery/expiry date, so no upper date bound is inferred.

## Rules and outcomes

- `required_evidence`: invoice/PO presence and clean required extracted fields/provenance.
- `po_reference`: invoice purchase_order_reference exactly matches a unique po_number.
- `supplier_match`, `buyer_match`: conservative name equality.
- `currency_match`: exact supported currency equality.
- `invoice_total`: invoice total <= referenced PO total plus configured absolute amount tolerance.
- `invoice_date`: invoice date >= referenced PO issue date.
- `line_quantity`: invoice quantity <= supported PO quantity plus absolute quantity tolerance.
- `line_unit_price`: absolute price difference <= configured tolerance, in the same supported currency.
- `duplicate_invoice_number`: exact, trimmed invoice-number duplicates across all currently stored invoice documents, including other cases, require investigation. Purchase orders are excluded, including at the rule boundary. No supplier scoping is assumed. A known duplicate always produces an overall discrepancy. Missing/unproven numbers elsewhere keep this finding `insufficient_evidence`, with contributing case/document IDs, but make it conditional so unrelated evidence cannot block this case's mandatory checks. The current invoice's unresolved number remains mandatory insufficient evidence. An overall pass with a conditional insufficient duplicate finding does **not** establish dataset-wide absence of duplicates. Inspect all findings. The dataset snapshot retains the inputs and uncertainty.

Line items are matched only by unique case/whitespace-normalized descriptions on both sides with valid source provenance. Source indices do not establish identity. Duplicate descriptions, missing descriptions/prices/quantities or missing supporting lines give insufficient evidence. If no invoice lines were extracted, both line rules are explicitly optional/not_applicable; this never means they matched. When lines exist, those checks are mandatory. The extraction schema has no SKU or unit-of-measure: no product identifier, packaging or unit conversion is inferred. Comparisons are of numeric quantities for unique matching described lines. Mixed/ambiguous units require analyst review outside these checks. Comparisons are per invoice, not cumulative utilization of one PO by multiple invoices.

Individual outcomes: passed, discrepancy, insufficient_evidence, not_applicable. Overall discrepancy takes precedence; otherwise a missing mandatory check yields insufficient_evidence. Overall passed requires mandatory checks to pass. Analysts must inspect optional not_applicable checks and limitations; passed is not an automatic financing recommendation.

## Exact arithmetic and configuration

Decimal arithmetic only. Inputs are bounded nonnegative decimal strings; nonfinite/exponent/separator values are not accepted. Configure absolute tolerances as decimal strings:

- VERIFICATION_AMOUNT_TOLERANCE (currency units)
- VERIFICATION_PRICE_TOLERANCE (currency units per item)
- VERIFICATION_QUANTITY_TOLERANCE (numeric quantity units)

All default to zero. Negative and nonfinite tolerances fail configuration validation. The actual tolerances are persisted as decimal strings for every run. No percentage or FX tolerance is implied.

## API and history

POST `/api/v1/cases/{case_id}/verify` returns 201 with a new run every time, even if inputs are unchanged. GET `/api/v1/cases/{case_id}/verifications?limit=20&offset=0` lists summaries. GET `/api/v1/cases/{case_id}/verifications/{run_id}` returns its saved findings. Unknown cases/runs return 404; invalid UUIDs/pagination return 422.

Runs store version, timestamp, outcome, configured tolerances and input snapshots. Findings store compared fields, actual/supporting values, source evidence including provenance IDs and original observations, document IDs, case ID and explanation. API actions never update or delete earlier runs/findings. Provenance is snapshotted, so later extraction changes do not rewrite history. The application database is not a tamper-proof external audit ledger.

Migration `0004_verification_runs` adds history tables without changing existing case/evidence data. Downgrade removes these history tables and their contents; back up valuable history before any downgrade. Tests run the round trip in an isolated transactional schema.

No authentication/authorization exists. Duplicate checks include evidence from other cases; restrict this local build to synthetic data. Dataset-wide snapshots and synchronous execution are intended for hackathon-sized datasets; retention and scalable duplicate indexing are future work.

## Automated synthetic workflow and clean demonstrations

From the repository root, using installed dependencies and the existing API database configuration:

```bash
cd apps/api
uv run pytest tests/test_invoice_po_workflow.py -q
```

The suite calls real FastAPI endpoints against PostgreSQL. Each test creates a UUID-named
transactional schema with no public-schema fallback, binds request sessions to savepoints,
and rolls back the entire schema and all records afterward. Uploads use pytest temporary
directories. It never resets the database, changes existing document types, or commits demo
records. The configured database must be migrated and the test role must have CREATE SCHEMA
permission. Before/after hashes check that every existing application row is unchanged;
avoid concurrent application writes during this assertion. No existing financial values are
printed. Existing migration tests separately exercise actual Alembic upgrade/downgrade paths
inside rollback-only schemas.

Coverage: matching CSV and text-PDF invoice/PO pairs, case separation, mislabeled PO,
excess invoice total, supplier/buyer/currency/reference mismatches, missing PO, repeated runs
and immutable saved results after new evidence, cross-case invoice duplicates, unrelated
unresolved invoice numbers, purchase-order exclusion, invalid/missing fields, upload type
validation, field provenance and unchanged pre-existing records (scenarios A–M).

For a clean synthetic demonstration with no permanent records, execute only the happy path:

```bash
uv run pytest tests/test_invoice_po_workflow.py -k test_a_matching_and_j_saved_history -v
```

This demonstrates create → upload both types → extract → verify → inspect provenance →
retrieve historical results, then rolls back. For an interactive browser demonstration,
run a separate API instance and frontend against a **dedicated disposable database** and
separate evidence directory, using environment overrides rather than editing `.env`.
Apply migrations only to that dedicated database. Use the conspicuously SYNTHETIC fields
in the workflow test, upload each with its correct type, extract both, then verify.
Avoid browser demonstrations against the user's database when no permanent records are wanted.

Full validation from the repository root:

```bash
(cd apps/api && uv run pytest -q && uv run ruff check src tests && uv run ruff format --check src tests)
(cd apps/api && uv run alembic current && uv run alembic heads && uv run alembic check)
(cd apps/web && npm run lint && npm run build)
```

These are API/database workflow tests; they do not automate browser interactions. PDF
coverage uses supported label/value text PDFs, with real page provenance, not OCR or arbitrary
invoice layouts. History persistence is checked across independent HTTP requests in the same
rollback-only outer transaction; no process-restart durability claim is made by these tests.

Task 003A-FIX validation found the database at `0004_verification_runs` (head), with no new
migration needed. Task 003A-DB resolves the metadata mismatch by registering the existing `schema_foundation`
table from migration 0001 in ORM metadata. No table was removed and no migration was needed.
The migration round-trip test also compares the full migrated schema against metadata.
