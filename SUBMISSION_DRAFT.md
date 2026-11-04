# VaultLine Verify — submission draft

Prepared for the Meta Global AI Developer Hackathon 2026, Startup Track.
**Draft only: not submitted.** Video and repository links below are placeholders. No traction,
customer pilots are claimed. A completed Baseten-hosted Meta investigation was confirmed by the owner
and its saved output passed read-only local validation during Task 006G.

## Project name

VaultLine Verify

## One-sentence pitch

VaultLine Verify helps receivables-finance reviewers trace invoice discrepancies and potential
competing recorded claims to source evidence, with explainable indicators for human review.

## Problem statement

A financing reviewer may receive an invoice, a purchase order and supporting records that must be
reconciled before progressing an application. Inconsistent amounts, unresolved fields and potentially
repeated financing assertions require investigation. A useful system must preserve the evidence,
distinguish discrepancies from missing information, and avoid turning incomplete records into a
fraud allegation or an unsupported lending conclusion.

## Solution

The prototype ingests synthetic invoices and purchase orders, extracts and normalizes observed
fields, and runs deterministic cross-document comparisons. It records financing assertions and flags
potentially matching active claims within the VaultLine dataset. Findings retain document/claim/case
references and field provenance. A categorical assessment summarizes those findings, explicitly
retaining insufficient evidence and unknown external financing and requiring human review.

A separate provider-independent investigation service prepares minimized evidence packages for
Meta Muse Spark Open through Baseten and validates structured output and references before accepting
a report. A normal-application Baseten investigation completed with cited findings and mandatory
limitations; the saved evidence included a duplicate-invoice-number discrepancy. The original Meta
Model API account remains restricted. The isolated interactive demo still disables live requests.

## Target customers

Intended users are receivables-finance teams at lenders, banks, non-bank financial institutions,
factors and trade-finance operations. These are target customer segments, not existing customers.
No pilot, revenue, user-count or adoption claim is made in this draft.

## Technical architecture

- Modular monolith with clear API, extraction, verification, claim, risk and investigation boundaries.
- Next.js, TypeScript and Tailwind CSS frontend; Python 3.12, FastAPI and Pydantic v2 backend.
- PostgreSQL 16, SQLAlchemy and Alembic for cases, evidence metadata, provenance, assertions and
  immutable application-level verification/investigation history.
- Decimal financial arithmetic with documented currencies/rounding; exact decimal-string APIs.
- SHA-256 source checksums and evidence IDs/locations linking observations to findings.
- HTTPX Meta adapter behind `AIProvider`; explicit deterministic `MockAIProvider` for tests only.
- Local Docker Compose database, isolated transactional demo schemas, pytest integration tests
  and Chromium browser journeys. No distributed services or external lender registry.

## Meta model integration details and testing status

| Item | Implemented behavior / verified status |
| --- | --- |
| Default provider/model | Meta / `muse-spark-1.3` |
| Validated hosted provider/model | Baseten / `meta-models/muse-spark-open` |
| Validated hosted endpoint | `https://inference.baseten.co/v1/chat/completions` |
| Original Meta endpoint | `https://api.meta.ai/v1/chat/completions` (separate restricted account) |
| Authentication | Bearer key read only from backend process environment; never exposed to frontend |
| Request | System instructions plus minimized evidence; documented JSON-schema response format |
| Output | Executive summary, key findings, supporting references, unresolved questions, next verification steps and limitations |
| Validation | Bounded Pydantic schemas, exact factual-source matching, allowed interpretation language, reference rejection, explicit unknowns |
| Isolation | AI output does not change deterministic outcomes or make lending decisions |
| Automated evidence | Mocked Meta HTTP success/error tests and explicitly injected test-only MockAIProvider; no live key needed |
| Live hosted Meta investigation | **Completed through Baseten in the application; saved output revalidated read-only** |
| Event-specific model | `meta-models/muse-spark-open-1026` was unavailable and was not used |
| Recorded demonstration | Live requests disabled locally; no mock substitution or successful Meta inference is represented |

The integration follows the official Meta API documentation cited in
[INVESTIGATIONS.md](apps/api/INVESTIGATIONS.md). An HTTP adapter and passing offline contracts do not
prove real service access, schema acceptance or model quality. No account identifiers or billing
details belong in the submission.

## Features built during the hackathon

The prototype’s implementation extends the initial engineering-guidelines checkpoint. This list
summarizes the work prepared for the submission; the owner must confirm competition eligibility,
development dates and final submission requirements before submitting.

1. Document ingestion with explicit invoice/PO typing and checksum-preserved source files.
2. Deterministic financial-data normalization for documented CSV and text-PDF schemas.
3. Cross-document checks for PO reference, supplier/buyer text, currency, dates, totals and supported
   line quantities/prices.
4. Duplicate invoice-number flags and potential competing financing assertions in recorded data.
5. Deterministic discrepancy and incomplete/ambiguous-evidence findings.
6. Source-linked provenance relationships across documents, extracted fields, findings and claims;
   a dedicated interactive graph explorer is not implemented.
7. Provider-independent Meta investigation adapter, grounding validation and preserved reports/errors;
   a completed live Baseten application investigation is confirmed.
8. Explainable categorical risk indicators with freshness checks, replayable inputs and mandatory
   human review. No predictive credit score or automatic loan approval/rejection.

The eight feature areas are represented with these explicit limits; see [ROADMAP.md](ROADMAP.md)
for scoped statuses rather than interpreting the list as unrestricted feature completion.

## Technical challenges addressed

- Preserving user-selected document types: a mislabeled PO produces review/missing-evidence findings
  rather than being silently reclassified as valid PO evidence.
- Maintaining exact financial arithmetic and explicit currency boundaries without binary floating point.
- Matching conservatively across cases without treating an invoice number or similar company name
  as proof of receivable or legal-entity identity.
- Keeping missing/proposed claims distinct from active conflicts and preserving status history.
- Keeping every indicator tied to actual findings and provenance, including incomplete evidence.
- Detecting stale verification coverage when the underlying document/extraction dataset changes.
- Separating AI interpretation from deterministic checks and rejecting unsupported output/references.
- Exercising a complete synthetic journey without altering existing database records or calling AI.

## Validation evidence

Historical Task 004G validated 159 backend tests, two Chromium journeys and seven release-audit tests,
with Ruff, frontend lint/build and Alembic consistency passing. This includes a regression verifying
that the recording intake fixture matches without colliding with the five seeded cases. These are local
software tests, not customer validation, model-quality benchmarks or production-security certification.
The release checker is heuristic and cannot prove all secrets are absent.

The historical dependency audit recorded moderate development-toolchain advisories requiring review;
no forced upgrades or blanket security-clearance claim is made. Public release also awaits the owner’s
license decision; current package metadata remains `UNLICENSED`.

## Current limitations

- Original Meta Model API access is restricted. Baseten live success is limited to the observed
  application reports, not a guarantee of availability or model quality; offline/mock output is not live AI.
- Authentication, authorization, production retention/access controls and operational hardening are
  not implemented. Local demonstrations use synthetic data only.
- Supported field/value CSVs and labeled text PDFs only; no OCR or arbitrary-layout understanding.
- Matching relies on exact invoice evidence and conservative name equality, not verified legal identity.
- Recorded financing claims do not prove actual financing, ownership, enforceability or fraud.
- Dataset-only checks cannot establish absence of external financing; no global registry is queried.
- Provenance is source-linked but has no dedicated interactive graph exploration interface.
- Risk indicators are categorical, uncalibrated review support; no probability of default or automatic
  financing decision. Assessments are read-only views, without separate persisted assessment history.
- Checks are per invoice, not cumulative PO utilization. Dataset scans are intended for prototype scale.
- The temporary demo rolls back on exit; it demonstrates history across requests/reloads, not restart
  durability of the temporary session. Normal application records use persistent PostgreSQL storage.

## Future roadmap — not implemented claims

1. Confirm event-specific model eligibility and expand model-quality evaluation only with separately
   authorized synthetic requests; the working Baseten model does not establish -1026 eligibility.
2. Confirm the original feature acceptance criteria and expand provenance graph exploration if needed.
3. Add appropriately designed access controls, retention policies and deployment hardening before
   handling sensitive production evidence.
4. Review/remediate dependencies with compatible tested versions and choose/document the license.
5. Explore approved data integrations, persisted assessment reports and scalable indexing where
   justified. External financing coverage would require explicit scope, evidence and data agreements.
6. Seek customer discovery and evaluate practical review workflows; no existing pilots are implied.

## Demo video

**TODO — replace with the actual reviewed three-minute video URL.**

Script and recording checklist: [DEMO_SCRIPT.md](DEMO_SCRIPT.md).
The video must disclose the synthetic dataset and distinguish confirmed Baseten output from
restricted original Meta access and test-only mock output. Do not record private evidence.

## Public GitHub repository

Configured repository: https://github.com/Awwiiiii/VaultLine-Verify

Verify public visibility and manually publish the reviewed checkpoint before submitting.

Recommended repository name: `VaultLine-Verify`. No GitHub repository creation or push is performed
as part of preparing this draft. Verify the license, dependency review and redacted security checks
before publication; do not substitute an invented or private URL for the actual public link.


Task 006G release validation is recorded in RELEASE_PREPARATION.md. The current work includes
source-specific grounding, material-finding coverage, separated upload feedback and bounded Cases
loading. No new live inference, push or actual hackathon submission is part of this review.
