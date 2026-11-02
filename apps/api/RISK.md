# Deterministic evidence-based risk assessment v1

Feature 8 is implemented as categorical **review indicators**, not a predictive numerical score.
No probability of default, calibrated credit-risk prediction, fraud determination, ownership assertion,
loan approval or rejection is produced. A recorded claim is an assertion, not proof of financing.
Every response requires human review, including one with no recorded discrepancy. No AI provider
is called; deterministic assessment works without Meta credentials or billing access.

## Read-only API

GET `/api/v1/cases/{case_id}/risk-assessment` returns:

- `rule_version`: `vaultline.risk-indicators.v1`.
- `assessment_status`: `review_findings_present`, `insufficient_evidence`, or `no_recorded_discrepancy`.
- `human_review_required: true`, review requirement and recorded-dataset scope.
- Ordered categorical indicators with explanations and nonempty `source_refs`.
- `sources`: referenced saved findings, recorded assertions, coverage checks and explicit limitations.
- `input_snapshot`: all inputs to the pure classification function, with the selected verification run.
- `assessed_at`: response collection time, not an input to classification.

Unknown cases return 404 and invalid UUIDs return 422. This is a derived current view: GET does not
create a verification run, investigation, risk-history record or financing decision. No migration
is needed. Existing histories remain untouched. Save a response externally if a particular assessment
must be retained; the API does not currently provide persisted assessment history or report signing.

## Sources reused

The latest saved deterministic verification is selected by created_at descending, then ID descending.
Its rule version, tolerances, outcomes, findings, compared fields/values, document IDs and field
provenance are retained. Verification is not silently rerun. Current claim-conflict findings come
from the existing pure conflict engine; active/proposed/released/cancelled handling and Decimal
aggregate comparisons are unchanged. Relevant claim snapshots include exact decimal-string amounts,
statuses, case/document IDs and lender strings, but omit free-form notes and external references.
No AI interpretation is used as deterministic risk evidence.

Stable source references are scoped to the response:

- `verification:<run-id>:finding:<position>` identifies an ordered immutable saved finding.
- `verification:<run-id>` identifies its summary, version, tolerances and timestamp.
- `claim_conflict:<position>` identifies a captured deterministic conflict result and its rule version,
  claim/case/document IDs, matched fields and supporting invoice provenance.
- `claim:<claim-id>` identifies the recorded assertion at assessment time.
- `verification_coverage` contains document-evidence fingerprints and freshness, not financial proof.
- `scope` explicitly records the dataset limitation supporting unknown external financing.

Every indicator reference must resolve locally. Original provenance IDs/locations/values are copied
from the existing finding or claim snapshot; no evidence is invented. The endpoint does not return
unrelated document payloads used solely to check coverage. Existing cross-case findings may contain
related evidence; case scoping is not user authorization, which remains unimplemented.

## Transparent rules

| Existing result or condition | Indicator | Summary effect |
| --- | --- | --- |
| Verification discrepancy | `discrepancy` | Human-review findings present |
| Potential competing claims | `potential_claim_conflict` | Human-review findings present |
| Aggregate recorded amounts above invoice total | `aggregate_claim_excess` | Human-review findings present |
| Confirmed duplicate registry assertions | `duplicate_assertions` | Human-review findings present; not confirmed financing |
| Missing run, changed evidence, insufficient check, mandatory not_applicable, absent supporting findings | `insufficient_evidence` | Insufficient evidence unless a review finding takes precedence |
| Inconclusive claim/proposed assertion | `insufficient_evidence` | Same, even if document verification passed |
| Optional not_applicable comparison | `unchecked_comparison` | Informational; never presented as a successful match |
| No recorded claim conflict | `no_recorded_claim_conflict` | Dataset-only informational result |
| No external financing data is verified | `unknown_external_financing` | Always shown; never converted into evidence of wrongdoing |

Precedence is review findings first, insufficient evidence second, otherwise no recorded discrepancy.
All indicators remain visible regardless of precedence. A passed verification can still have optional
inconclusive duplicate coverage; the assessment explicitly reports that gap. No recorded discrepancy
is a statement about captured checks only, not a low-risk rating, lending recommendation or claim
that external financing does not exist. The human-review requirement cannot be turned off.

## Freshness and reproducibility

A canonical SHA-256 digest of document/extraction/provenance inputs is compared with the saved
verification's input snapshot. The comparison uses the same dataset scope as verification: every
stored invoice (for duplicate checking), plus all documents in this case. New documents, extraction
changes or another invoice elsewhere can therefore make coverage stale. Stale saved findings are
still shown as historical findings and a rerun is required before current coverage can be claimed.
Claim changes are assessed from the current registry without rewriting the verification snapshot.

For identical `input_snapshot` values under the same rule version, `risk.engine.assess` returns
identical ordered output. The collection timestamp changes across GET requests and is deliberately
excluded from classification. Replay from `apps/api` using a previously saved JSON response:

```python
import json
from pathlib import Path
from vaultline_api.risk.contracts import RiskInputs
from vaultline_api.risk.engine import assess

saved = json.loads(Path("assessment.json").read_text())
replayed = assess(RiskInputs.model_validate(saved["input_snapshot"]))
assert replayed.model_dump(mode="json") == {
    key: value for key, value in saved.items() if key != "assessed_at"
}
```

Treat saved assessment JSON as sensitive financial output; keep it outside the repository.
The digests detect changed coverage but are not independent financial verification or signatures.
Collection uses ordinary database read-committed semantics; concurrent writes across its SQL reads
are not promised to be one atomic snapshot. Reassess after input changes. Historical claim snapshots
may be older than current document extractions; the existing conflict engine's limitations still apply.

## UI and tests

The case-detail **Evidence-based risk assessment** section has an explicit **Assess recorded evidence**
button, summary, human-review requirement, rule/timestamp/coverage information, categorized indicators
and expandable deterministic source/provenance payloads. It is a point-in-time view: refresh after
verification, document extraction or claim changes. Assessment does not alter adjacent investigation
or verification panels.

From `apps/api`:

```bash
uv run pytest tests/test_risk.py tests/test_demo_workflow.py -q
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
uv run alembic current
uv run alembic heads
uv run alembic check
```

The browser journey (`npm run test:e2e` from `apps/web`) checks missing, clean, discrepant and competing
claim indicators, human review, unknown external financing and field-provenance references. Backend
tests cover replay, stale extraction/dataset coverage, claim status changes, optional comparison gaps,
case isolation and existing history preservation. Fixtures are synthetic and PostgreSQL writes roll
back. The deterministic assessment has no provider dependency and never makes an external AI call.
