# Recorded financing claims

This registry contains assertions recorded in VaultLine only. It is not a global registry,
proof of legal identity or absence of external financing, and never approves financing.

POST `/api/v1/cases/{case_id}/claims` requires invoice_document_id, claim_reference,
lender, amount (decimal string), currency, and optional status (default proposed),
external_reference and notes. References are unique within a case; duplicates return 409.
GET the same path supports limit (1–100) and offset. GET `/api/v1/claims/{claim_id}`
returns the saved assertion and invoice evidence snapshot.
PATCH `/api/v1/claims/{claim_id}/status` accepts proposed → active/cancelled and
active → released/cancelled. Terminal records cannot reopen; every transition appends
its timestamp to status_history. Original assertion fields and evidence are immutable.

GET `/api/v1/cases/{case_id}/claim-conflicts` compares active recorded assertions across
cases. Same-document claims are grouped regardless of extraction completeness. Cross-document
matching requires valid source provenance for exact trimmed invoice number, currency,
Decimal invoice total and case/whitespace-normalized supplier and buyer names. No fuzzy
matching or legal-entity equivalence is inferred. Different totals remain distinct evidence;
this conservative rule may miss altered invoice copies. Evidence is frozen at claim creation;
extract before recording, or unresolved evidence will remain unresolved in that assertion.

Categories: confirmed_duplicate_records means repeated lender/document/amount/currency
assertions, not confirmed double financing. Other multiple active assertions sharing a document
or full matching identity are potential_competing_claims. Aggregate active amounts above a
supported invoice total produce aggregate_exceeds_invoice; currencies are never converted.
Incomplete identity or claim/invoice currency mismatch yields insufficient_evidence.
Proposed claims generate a review finding and do not contribute active amounts. Released
and cancelled claims are excluded. No_conflict_found describes only recorded coverage.
Findings contain rule version, claim/case/document IDs and snapshotted evidence/provenance.
Conflict responses are computed views; prior claim evidence and verification runs are preserved.

Amounts persist as NUMERIC(26,8); APIs return decimal strings at currency minor units.
Input beyond supported currency precision is rejected without rounding. Supported currencies
are USD, EUR, GBP, INR, JPY and KWD. Zero is allowed; negatives/nonfinite/float inputs are rejected.
Lender identifiers are exact user-supplied strings and are not externally authenticated.

Migration 0005 adds financing_claims only. Downgrade removes that new table and its records;
only test downgrade in disposable transactional schemas. Existing evidence tables are unchanged.
Run `uv run pytest tests/test_claims.py tests/test_verification_migration.py -q` from apps/api.
Tests use synthetic uploads, isolated PostgreSQL schemas and rollback, without permanent claims.

No authentication currently exists. Dataset-wide conflict responses expose cross-case evidence;
this local build remains suitable for synthetic data only. Queries are synchronous and scan
recorded claims; large-dataset indexing and access controls remain future work.
