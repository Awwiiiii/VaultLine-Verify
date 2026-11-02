# Evidence-grounded investigations

AI-assisted review is separate from deterministic financial verification and claim rules.
It never approves/rejects financing, declares fraud or establishes legal identity, receivable
ownership, enforceability or absence of external financing. No AI output changes those rules,
source documents, claims or earlier results.

## Current live-testing status

The Meta adapter is implemented and exercised with mocked HTTP responses, but successful live
Meta inference is not validated. An external account billing restriction blocks that testing.
No account identifiers, billing details or credentials belong in this repository. Do not execute
the opt-in smoke script while that restriction remains. The synthetic interactive demo disables
live requests explicitly; successful MockAIProvider generation is confined to tests.

## Provider integration

`AIProvider` is a provider-independent protocol. `MetaAIProvider` is the runtime default;
`MockAIProvider` is explicitly injected only in tests, never a fallback. Default model is
`muse-spark-1.3`, base URL `https://api.meta.ai/v1`. The adapter uses HTTPX with bounded timeout,
no redirects, no automatic retries, no tools and no proxy environment inheritance.

Official documentation checked for task 004A:
- https://dev.meta.ai/docs/models
- https://dev.meta.ai/docs/api-reference
- https://dev.meta.ai/docs/structured-output
- https://dev.meta.ai/docs/api-reference/chat-completions/schemas

POST `/chat/completions` uses Bearer authentication, `model`, system/user `messages`,
`response_format` with `type: json_schema`, `json_schema.name/schema/strict`,
`max_completion_tokens: 6000` and `store: false`. The non-streaming response is parsed from
`choices[0].message.content` only after a `stop` finish reason and no refusal/tool calls.
Output is bounded to 100,000 bytes, independently schema-validated, and checked locally.
No live call has been made as part of automated validation. Mocked HTTP tests confirm the
adapter contract; actual service/model access and schema acceptance require the opt-in test.

## Grounding and safety boundaries

Each report includes executive summary, key findings, supporting evidence references,
unresolved questions, next verification steps and limitations. Every statement has an explicit
kind: observed_fact, deterministic_finding, ai_interpretation or unknown. Every statement cites
IDs from its saved evidence package. Foreign document/claim fields are rejected as extra
schema properties; references resolve only to server-built entries with document/claim/case IDs.

Fact text must match a single cited entry exactly and have the same kind. AI interpretations,
unknowns and recommendations must use the bounded phrases in `investigations/contracts.py`.
The model selects, organizes and prioritizes cited evidence; it cannot invent free-form facts,
financial calculations or lending conclusions. This intentionally limits narrative flexibility
in exchange for enforceable grounding. Valid references alone are not treated as semantic proof.
Source observations remain unverified statements in source evidence, even when accurately copied.
Unknown external financing and the AI/no-decision limitation must always be present. Inconclusive
or missing verification coverage requires an explicit insufficient-evidence statement.

Evidence is untrusted data, never policy or executable instructions. Packages include the latest
saved verification run and its timestamp, current deterministic claim conflicts, relevant recorded
claim amounts/statuses, normalized field observations and source provenance where available.
Cross-case evidence is included only when existing findings identify it as relevant. Raw files,
original-value strings, free-form notes, external references, storage paths, case names, credentials
and unrelated records are omitted. Source values and normalized financial evidence may still be
sensitive: this is minimization, not anonymization. Package limit: 500 entries / 120,000 UTF-8 bytes;
oversized packages fail explicitly instead of silently dropping evidence.

## API and history

- POST `/api/v1/cases/{case_id}/investigations`: start a new synchronous investigation; 201 returns
  the saved record, including failed attempts. Provider errors are safe error_code/error values;
  invalid provider text is never retained or returned.
- GET the same path: summaries with limit (1–100) / offset pagination.
- GET `/api/v1/cases/{case_id}/investigations/{investigation_id}`: full saved report and evidence;
  foreign-case IDs return 404. Unknown cases are 404, invalid UUIDs/pagination are 422.

Inputs are persisted as pending before calling the provider. Completed/failed reports are never
reused or overwritten by another start request. A process interruption can leave pending records;
reload history before retrying. No background recovery job exists. Verification findings reflect
the latest **saved** run, which may predate current documents; claim conflicts reflect collection
time. Both are timestamped and kept separate. No automatic re-verification occurs.

Migration `0006_investigations` adds one table/index. Its downgrade removes only that new table
and its reports; test downgrade only in a disposable transactional schema. Existing history is
preserved by upgrade. The frontend displays provider/model, timestamp, safe errors, all output
sections, evidence references and provenance, and paginated history.

## Secure configuration (backend only)

1. Create a Meta Model API key in the official developer dashboard with appropriate project access.
2. Inject `MODEL_API_KEY` through your backend secret manager or process environment. It is read
   directly from `os.environ`; putting it only in a dotenv file does not load it for this adapter.
   Never use `NEXT_PUBLIC_` variables or put the key in frontend configuration.
3. Set `AI_EVIDENCE_SHARING_APPROVED=true` in the backend process environment only after approving
   the intended data handling with Meta. Default is disabled; no key means no HTTP request either.
4. Restart the backend process with those environment variables. Run deterministic verification,
   then start an investigation from the case detail page. Inspect failed records for actionable errors.

For a local shell without echoing the key or putting it into shell history:

```bash
read -rs -p 'Meta API key: ' MODEL_API_KEY; echo
export MODEL_API_KEY
export AI_EVIDENCE_SHARING_APPROVED=true
# Launch the backend in this shell using your normal command.
# After stopping the backend:
unset MODEL_API_KEY AI_EVIDENCE_SHARING_APPROVED
```

No credentials need to be edited in tracked files. Do not log HTTP headers/payloads or enable
verbose client tracing with sensitive evidence. Missing credentials, sharing approval, 401/403,
429, timeouts, transport/provider failures, refusals, truncated output and invalid grounding have
distinct safe handling. There is no silent switch to mock or another provider.

## Tests and optional real smoke test

From `apps/api`:

```bash
uv run pytest -q
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
uv run alembic current
uv run alembic heads
uv run alembic check
```

Routine pytest blocks live HTTP transports globally, uses synthetic evidence and rollback-only
PostgreSQL schemas/transactions, and needs no API key. Provider adapters use the same validated
contract, with HTTPX MockTransport for Meta success/error/timeout tests.

Only after explicit authorization for one potentially billable real request, configure the two
backend environment variables above and run:

```bash
uv run python scripts/meta_smoke.py --authorize-live
```

This script is outside pytest collection, sends one synthetic no-evidence package, validates the
real response, writes no database records, prints no key/evidence/provider body, and never retries.
Without `--authorize-live` it makes no request. This authorization is separate from routine tests.

## Remaining operational limits

The application currently lacks authentication/authorization and production access controls;
case scoping is enforced by routes but is not user authorization. Provider calls are synchronous.
Package collection uses database read-committed semantics; it is an auditable collection, not
an atomic snapshot across all concurrent writers. Cross-case evidence still needs approved access
and retention controls before sensitive production use. `store: false` is the documented request
option, not an independent guarantee about Meta's complete data retention policies. The strict
phrase vocabulary, unsupported arbitrary document layouts and frozen claim snapshots remain
explicit limits. No live Meta compatibility or quality claim is made without the opt-in smoke test.
