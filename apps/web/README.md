# VaultLine Verify frontend

From apps/web, run `npm ci`, copy `.env.example` to `.env.local` only if the latter does not exist, then run `npm run dev`. Open http://localhost:3000.

Start the FastAPI backend separately on port 8000. The public API base URL contains no secrets; configure NEXT_PUBLIC_API_BASE_URL before building. Browser requests require the backend CORS origins to allow the frontend origin. The dashboard checks /health with a five-second timeout; connectivity is not database readiness.

Run `npm run lint` and `npm run build`; serve the build with `npm start`. Case creation and the case detail workflow are implemented; other navigation pages retain placeholder states. UI primitives follow shadcn/ui conventions with Radix Slot and Tailwind.

## Case workflow
Set NEXT_PUBLIC_API_BASE_URL=http://localhost:8001 in your existing .env.local when running the API on 8001. Run `npm run dev -- --hostname 127.0.0.1`; open http://localhost:3000/cases. Create a case using a counterparty name, open its reference, select invoice or purchase order and upload PDF/CSV evidence. The case detail shows upload status, byte size, timestamp and SHA-256 checksum. An uploaded document has not been financially verified.

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
