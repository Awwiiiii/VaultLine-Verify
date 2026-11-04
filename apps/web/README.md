# VaultLine Verify frontend

From apps/web, run `npm ci`, copy `.env.example` to `.env.local` only if the latter does not exist, then run `npm run dev`. Open http://localhost:3000.

Start the FastAPI backend separately on port 8000. The public API base URL contains no secrets; configure NEXT_PUBLIC_API_BASE_URL before building. Browser requests require the backend CORS origins to allow the frontend origin. The dashboard checks /health with a five-second timeout; connectivity is not database readiness.

Run `npm run lint` and `npm run build`; serve the build with `npm start`. Case creation and the case detail workflow are implemented; other navigation pages retain placeholder states. UI primitives follow shadcn/ui conventions with Radix Slot and Tailwind.

## Case workflow
Set NEXT_PUBLIC_API_BASE_URL=http://localhost:8001 in your existing .env.local when running the API on 8001. Run `npm run dev -- --hostname 127.0.0.1`; open http://localhost:3000/cases. Create a case using a counterparty name, open its reference, use the separate Invoice and Purchase order areas to upload PDF/CSV evidence. The case detail shows upload status, byte size, timestamp and SHA-256 checksum. An uploaded document has not been financially verified.

Authentication and authorization are not implemented. Use synthetic data locally. Evidence is stored privately by the API and has no public download URL.

On case details, choose **Extract financial fields** to process a supported document, or **View saved extraction** to retrieve its result. The panel displays normalized fields, validation findings, original observations and source references. Follow the backend EXTRACTION.md schema when preparing synthetic CSV or text PDF documents. Extraction uses neither OCR nor AI; extracted values are not verified claims. A separate AI Investigation adapter is implemented, with live inference currently unvalidated because of an external account billing restriction.

The case detail verification panel runs deterministic invoice/PO checks, displays compared values and provenance, and retrieves paginated historical runs. Extract supporting documents before verifying. Missing evidence stays visible; a document-check pass does not establish legal rights, delivery, acceptance, or absence of fraud. There are no risk percentages or lending decisions.

## Isolated demo and browser tests

See [DEMO.md](../../DEMO.md) for synthetic scenarios and launch steps. Use
`NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8101 VAULTLINE_NEXT_DIST_DIR=.next-demo npm run dev -- --hostname 127.0.0.1 --port 3100`
with the separate demo backend. No environment secret files need editing.

Run `npx playwright install chromium --no-shell`, then `npm run test:e2e` for real Chromium
journeys against a temporary PostgreSQL schema. Ports 8102/3101 must be free. The browser
server explicitly injects MockAIProvider for tests only; every mock report is labeled TEST ONLY.


## Release status

This is a synthetic-data hackathon prototype, not a production deployment. The Meta runtime adapter
is implemented; successful live Meta inference has not been demonstrated. No live requests are part
of release checks. The offline interactive demo disables them explicitly, and test mock reports are
labeled TEST ONLY. See the [root README](../../README.md) and [release preparation](../../RELEASE_PREPARATION.md).
The project license is undecided; `UNLICENSED` package metadata does not choose a license.


## Evidence-based risk assessment

Case details include a deterministic assessment of recorded checks and claim conflicts. Click
**Assess recorded evidence** after verification or input changes. The panel distinguishes discrepancies,
potential/duplicate assertions, insufficient or stale evidence, unperformed comparisons and unknown
external financing. Every indicator links its source finding/assertion and available provenance.
Human review is always required; no predictive score, financing approval/rejection or legal-rights
conclusion is made. This read-only view needs no Meta access. See [RISK.md](../api/RISK.md).

## Task 005A workspace polish

Overview reads one bounded case page (`limit=5`) and its backend total. Recently created cases
are explicitly scoped creation activity; no verification or conflict aggregates are inferred from
case workflow status. Documents, Investigations and Audit direct reviewers to existing case-scoped
workflows rather than claiming those collections are empty.

Settings stores validated light/dark, 10/20/50 case-page size and local/UTC timestamp preferences
under `vaultline-preferences` in browser storage. Storage failure leaves session controls usable.
`/health`, `/ready` and `/system/provider` are fetched independently with five-second timeouts.
Provider diagnostics use the same injected adapter as investigations, expose only name/model and
categorical local status, and make no provider request. Configured credentials are not proof of
availability. Live validation remains untested. No credentials can be entered in the browser.

Baseten selection occurs only in backend process configuration. Settings displays the actual
provider/model and separates owner-reported successful basic Baseten inference from untested
VaultLine live schema validation. Saved investigations retain their own provider/model identifiers.
No browser credentials or live diagnostic probes are added. See the API investigation guide.


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


Task 006D groups upload controls and all saved documents by type within the same case. Selected
filename/size, indeterminate progress, backend-confirmed success and actionable failures are shown.
Synchronous submission guards prevent double-click requests; success clears the file selection.
There is no server-side idempotency or duplicate-content rejection. Refresh documents after lost
confirmation before retrying. Extraction labels map uploaded/processing/extracted/needs_review/failed
without changing backend semantics, and refresh saved document details. Provenance and findings
remain available. No deletion controls are added. Browser tests cover upload/extraction failure,
repeat-click prevention, same-case types, persistence and narrow layouts.

## Task 006F: cases loading and development-runtime recovery

The reported port-3000 failure was reproduced read-only: five records were returned by the configured
API, with the correct Access-Control-Allow-Origin, but the frontend made no cases request. Settings
was also unhydrated. Development HMR WebSocket handshakes failed (including an HTTP parser error).
A separate dev instance hydrated, and a full restart of the original frontend restored all five
records with no page errors. The exact trigger of the broken runtime was not conclusively recovered;
stale/shared development artifacts are a risk, not a proven explanation for the handshake bytes.
No backend/CORS/credential changes were needed.

Default dev output now uses `.next-dev`; build/start use `.next`. Explicit demo/e2e output-directory
overrides remain supported. This prevents normal production builds overwriting a running dev
server's chunks. Existing generated TypeScript configuration entries are preserved; Next adds its
new dev-type entries automatically. Do not delete build directories while their server is running.

Cases now has explicit loading/success/error states, response-shape validation, a ten-second list
request deadline, cancellation on unmount or query changes, and Retry loading cases. It starts with
safe default pagination while local preferences hydrate, then aborts/replaces the request if needed.
No polling or automatic retry is added. Error feedback identifies the compiled public API base URL;
NEXT_PUBLIC_API_BASE_URL changes require restarting dev or rebuilding production. Creation errors
are separate from list errors. Pagination parameters and backend sorting are unchanged. JavaScript
must hydrate before client controls work; a broken dev runtime cannot be fixed by an API Retry.

If port 3000 is already running, stop only that frontend with Ctrl-C in its terminal. Do not start a
second server on the same port. From the repository root, in separate terminals:

```bash
cd apps/api
CORS_ALLOWED_ORIGINS='["http://127.0.0.1:3000"]' uv run uvicorn vaultline_api.main:app --host 127.0.0.1 --port 8001
```

```bash
cd apps/web
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8001 npm run dev -- --hostname 127.0.0.1 --port 3000
```

Keep an already healthy API running instead of starting another. No database migrations, resets,
provider calls or data creation are required. Open http://127.0.0.1:3000/cases and reload once after
a restart; confirm five saved rows and the existing case named testing. Click an existing case
reference to verify navigation. On a network failure expect an error after at most ten seconds and
use Retry after service recovery. Direct API navigation alone does not test browser CORS.

## Current release status — Task 006G

The owner confirmed a completed **normal-application** Baseten investigation using
**`meta-models/muse-spark-open`**. During release review, the local API's saved completed Baseten
reports were retrieved read-only and their outputs passed the current schema and evidence validator.
The saved evidence includes the deterministic duplicate-invoice-number discrepancy, cited evidence,
unresolved questions, next steps and mandatory limitations. This is distinct from the earlier
no-persistence smoke and from test-only mock reports. No new inference was made during this review.
The unavailable hackathon-specific `meta-models/muse-spark-open-1026` was **not** used. Historical
006A–006F statements that normal-application validation was pending are superseded by this update.
Past success is not a guarantee of current access, availability, model quality or financing validity.
