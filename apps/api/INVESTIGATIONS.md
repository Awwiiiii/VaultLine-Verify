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

## Baseten-hosted Meta Muse Spark Open (Task 006A)

A separate `BasetenAIProvider` implements the unchanged `AIProvider` protocol. MetaAIProvider
remains the default and retains its endpoint/behavior. Set `AI_PROVIDER=baseten` explicitly in
the **backend process environment** to select Baseten. `AI_PROVIDER=meta` selects the original
adapter. Unknown provider/configuration values fail closed; no runtime mock or provider fallback
exists. Configuration is intentionally not loaded from dotenv by the provider selector.

Baseten uses `https://inference.baseten.co/v1/chat/completions`, Bearer `BASETEN_API_KEY`, the
fixed model **`meta-models/muse-spark-open`**, `reasoning_effort=low`, and nonstreaming responses.
The owner independently confirmed HTTP 200 / stop with a short basic inference request using
500 tokens. That is owner-reported evidence of basic inference, **not** successful VaultLine
schema-grounded investigation validation. The event-specific `meta-models/muse-spark-open-1026`
returned HTTP 404 in the owner's account; it is not used. Eligibility under an event-specific
identifier is not established by the working identifier. The original Meta Model API account
remains restricted. No live inference was executed during Task 006A.

### Setup and output compatibility

Inject `BASETEN_API_KEY` privately through your approved secret mechanism; never paste keys into
browser settings, command arguments or tracked files. In the backend shell, after approving
sharing of the intended evidence with Baseten:

```bash
export AI_PROVIDER=baseten
export AI_EVIDENCE_SHARING_APPROVED=true
export BASETEN_MAX_TOKENS=8192
export BASETEN_OUTPUT_MODE=json_schema
# Launch the backend normally from apps/api; BASETEN_API_KEY must already be privately injected.
```

`BASETEN_MAX_TOKENS` accepts 1024–32768 and covers reasoning plus final JSON. 8192 is a starting
budget, not a guarantee of completing large packages. Connect timeout is 10 seconds; response
inactivity timeout is 120 seconds. Responses are bounded to 1 MB including discarded reasoning,
and final JSON to 100 KB. No reasoning content is stored, logged or returned.

Baseten's [Chat Completions reference](https://docs.baseten.co/reference/inference-api/chat-completions)
and [OpenAPI schema](https://docs.baseten.co/reference/inference-api/llm-openapi-spec.json) document
`response_format` with strict `json_schema`, `max_tokens` and `reasoning_effort`. Full compatibility
of this model with VaultLine's exact schema remains **unvalidated live**. Default `json_schema`
sends that schema with strict=true. A 400/422 response fails safely as unsupported request/schema;
there is no automatic second paid call. If model-specific strict mode is unsupported, explicitly
select `BASETEN_OUTPUT_MODE=json_prompt` for a separate, manually initiated invocation. That mode
omits `response_format`, includes the same schema and allowed phrases in the system prompt, and
requires a bare JSON object. It does not repair JSON, strip markdown or coerce invalid fields.
Both modes run mandatory Pydantic schema, exact fact, allowed-language, evidence-index, uncertainty
and limitation validation. The service independently validates output again before persistence.

Safe error codes distinguish missing/invalid credentials, HTTP 402 billing restrictions, 404
unavailable model, 429 limits, 400/422 unsupported settings/schema, connect/read timeouts, empty
final content (including reasoning-only), exhausted output budget and malformed JSON. Other
access errors (including 403) are reported as credential/account-access failures without guessing
billing details from potentially sensitive response text. Bodies and authorization headers are
never included in saved errors. No automatic retries occur. Failed attempts retain provider/model
and minimized evidence snapshots; existing history is not rewritten.

Settings reports the actual selected adapter/model, local configuration, owner-reported Baseten
basic inference success, and untested VaultLine live validation separately. It never probes the
provider. Saved reports already display their actual provider/model. The interactive isolated demo
continues explicitly overriding selection with a live-disabled Meta adapter, even if
`AI_PROVIDER=baseten` is set. Browser tests explicitly use MockAIProvider, labeled TEST ONLY.

### One manually authorized synthetic smoke request

With dependencies installed and `BASETEN_API_KEY` privately injected into the backend process
environment, run from the repository root:

```bash
cd apps/api
AI_PROVIDER=baseten AI_EVIDENCE_SHARING_APPROVED=true BASETEN_MAX_TOKENS=8192 BASETEN_OUTPUT_MODE=json_schema uv run python scripts/baseten_smoke.py --authorize-live
```

This explicitly authorizes at most one potentially billable Baseten request with synthetic
missing-evidence observations only. It validates the actual returned JSON using the unchanged
VaultLine investigation schema and grounding rules, prints only a sanitized summary and exits
nonzero on failure. It neither connects to a database nor persists records. Without
`--authorize-live` it exits before reading credentials or calling the adapter. The script is not
part of routine tests/builds. Automated tests replace HTTP or the adapter; they do not authorize
real inference. If strict mode fails, review the sanitized error before separately authorizing a
`json_prompt` invocation. Do not run the original restricted Meta smoke script as a fallback.

## Baseten failure diagnosis (Task 006B)

The owner reports that the first authorized strict-schema VaultLine smoke returned `invalid_output`.
The original envelope/content was not supplied or retained by the smoke script. Its exact rejection
stage therefore cannot be conclusively determined without a separately authorized live retest.
Basic HTTP-200 inference success is not evidence of successful schema-grounded investigation.
No live AI request was made during diagnosis; no live investigation success is claimed.

### Old pipeline and the diagnostic ambiguity

The original Baseten `invalid_output` could mean any of:

- Envelope over 1 MB; malformed envelope JSON; missing/invalid choices or message containers.
- Returned model identifier differing from the requested model (including an unrecognized alias).
- Unexpected finish reason other than stop/length, refusal, or tool calls.
- Non-string final content or final content over 100 KB.
- Pydantic rejection: missing/extra fields, wrong types, list/string bounds or unsupported kind.
- Semantic rejection: foreign references, wrong source kind/text or multiple sources for a fact,
  unsupported unknown/interpretation phrases, inconsistent evidence index, missing exact mandatory
  limitation, or missing external-financing/insufficient-evidence uncertainty.

The old adapter already reported absent content as `baseten_no_content`, length finish as
`baseten_output_budget`, HTTP 400/422 as `baseten_unsupported_request`, and malformed final JSON as
`baseten_invalid_json`. Those are distinct from the reported generic code; the available result
alone does not establish truncation or unsupported schema. The service independently validates
returned JSON before persisting a completed report; its generic checks reject non-string/oversized
provider output, unclassified ValueError/TypeError, and unknown exceptions safely. Meta's separate
adapter and its existing generic codes are retained.

### Sanitized stage reporting

Baseten now reports fixed allowlisted codes and the smoke prints `stage=<stage>` alongside the code.
API history derives `error_stage` from the saved code, requiring no migration or old-record updates.
Historical generic codes remain generic; no stage is retrospectively invented.

| Stage | Fixed code(s) |
| --- | --- |
| response_envelope | baseten_envelope |
| response_identity | baseten_model_mismatch |
| response_size | baseten_response_limit |
| completion | baseten_completion_state, baseten_refusal, baseten_tool_calls, baseten_output_budget |
| assistant_content | baseten_no_content, baseten_content_type, baseten_content_limit |
| request_compatibility | baseten_unsupported_request |
| json_syntax | baseten_invalid_json |
| schema_validation | baseten_output_schema, baseten_statement_kind |
| mandatory_limitation | baseten_limitation |
| evidence_references | baseten_references, baseten_evidence_index |
| evidence_grounding | baseten_grounding |
| allowed_language | baseten_vocabulary |
| mandatory_uncertainty | baseten_uncertainty |

Pydantic errors are classified using types and known field locations only. Their messages, input
values, provider bodies, model reasoning, evidence and headers are never printed or persisted in
diagnostics. Multiple simultaneous errors report the first classified stage: invalid JSON, invalid
kind, missing/empty limitation, then other schema failures. Semantic checks retain their existing
order and acceptance rules. A missing limitation accompanied by other absent fields can therefore
be the first reported error; fixing it does not imply all other fields are valid. Malformed or
unsupported output remains rejected. No JSON repair, truncation repair, phrase substitution,
alias guessing, automatic retry or output-mode fallback is performed.

### Schema compatibility audit and recommended retest

`InvestigationOutput.model_json_schema()` produces one root object with six required properties;
`$defs.Statement` has three required fields (`kind`, `text`, `evidence_refs`). Both objects set
`additionalProperties=false`. Statement kind uses a four-value enum; five statement arrays refer
to the nested definition through `$ref`. The remaining array contains string evidence IDs. There
are list and text bounds, no optional output fields, no nullable output branches and no recursive
references. No obvious missing-required/additionalProperties defect was found. Baseten's published
OpenAPI accepts `json_schema` with `strict=true`, but does not establish model-specific support for
every schema keyword. Live model compatibility is still unknown.

Importantly, the structural schema permits general statement text and string references; it cannot
prove that the phrases, provenance, mandatory uncertainty or references are valid for a particular
package. Strict JSON-schema generation can succeed while local grounding correctly rejects it.
The prompt now explicitly requests exact phrases/punctuation, all six sections, the exact limitation
and supplied entry IDs, and an empty key_findings list for unknown-only evidence. These are generation
instructions, not transformations of returned output; validation requirements are not relaxed.

Recommend **json_schema for the next diagnostic retest**, retaining the same 8192-token budget to
avoid changing multiple variables without evidence. Use explicit `json_prompt` only if sanitized
request-compatibility diagnostics justify a separately authorized alternative; it cannot fix invalid
references or unsupported conclusions by bypassing local validation.

With BASETEN_API_KEY already privately injected, from the repository root:

```bash
cd apps/api
AI_PROVIDER=baseten AI_EVIDENCE_SHARING_APPROVED=true BASETEN_MAX_TOKENS=8192 BASETEN_OUTPUT_MODE=json_schema uv run python scripts/baseten_smoke.py --authorize-live
```

This remains a maximum of one live request per authorized invocation, synthetic-only, with no
persistence. Report only its sanitized code/stage on failure. Never enable raw-response/HTTP debug
logging to investigate production or sensitive evidence. Increasing the configurable token budget
is relevant only when exhaustion is observed; no automatic paid retry is added.


## Task 006C validation update

The owner confirms one real Baseten request using `meta-models/muse-spark-open` passed local
schema and evidence validation. The synthetic smoke created no database records. Earlier
006A/006B statements that this smoke validation was pending are historical and superseded by
this report; no new live inference was executed during release preparation. Normal application
live creation/persistence/retrieval remains separately unvalidated. Offline tests exercise the
configured Baseten adapter, HTTP envelope, real API routes, PostgreSQL save/retrieve, preserved
history and strict grounding with HTTP mocks. Browser tests validate report rendering and evidence
references using explicit test-only mock output; they are not live inference evidence.

Settings distinguishes owner-reported synthetic smoke success from configuration and unvalidated
normal application live persistence. Runtime readiness is not inferred from an earlier smoke.
The default remains Meta; Baseten requires explicit backend process selection. The original
Meta account restriction and unavailable event-specific `-1026` identifier remain separate limits.
