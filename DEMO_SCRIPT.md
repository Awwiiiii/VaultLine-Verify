# VaultLine Verify — three-minute hackathon recording script

**Planned recording, not a completed video.** All parties, lenders, documents and claims are SYNTHETIC.
Target length: exactly 3:00. The demo shows a local prototype, recorded-dataset checks and human review,
not production readiness, actual financing, fraud or legal ownership. Meta integration is implemented;
no successful live Meta request has been validated because billing is restricted.

## Launch and rehearse

Use the seeded, rollback-only demonstration documented in [DEMO.md](DEMO.md). Do not connect the
recording frontend to the normal API or existing user cases. Leave credentials and billing unchanged.

Terminal 1, from the repository root:

```bash
cd apps/api
uv run python scripts/demo.py
```

Terminal 2, from the repository root:

```bash
cd apps/web
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8101 VAULTLINE_NEXT_DIST_DIR=.next-demo npm run dev -- --hostname 127.0.0.1 --port 3100
```

Open `http://127.0.0.1:3100/cases`. The API terminal prints the generated `/cases/<UUID>` paths;
UUIDs change on every launch. Open the seeded **SYNTHETIC Invoice exceeds PO** and **SYNTHETIC
Potential conflict lender A/B** cases in separate tabs beforehand. In the conflict tabs, click
**Load claims and conflicts** so the two synthetic lender assertions and source details are ready.
Return the first tab to `/cases` before recording.

Prepare the file chooser at `<repository>/demo/synthetic/`. Use the dedicated **recording** files
for the new intake case. Do not upload the already-seeded matching invoice again: that would correctly
trigger duplicate-number checks instead of demonstrating a clean intake. Restart only this demo server
between complete takes; its outer transaction rolls back, and the next launch starts clean. Do not
reuse the recording invoice number in another case during the same take.

Creating the recording invoice changes the duplicate-check dataset. Rerun verification on a seeded
case before showing its risk assessment; old saved runs remain historical and may show stale coverage.
The timed sequence below includes that refresh for the conflict case.

## Timed script and screen actions

| Time | Spoken narration | Exact navigation/action | Expected screen state |
| --- | --- | --- | --- |
| 0:00–0:15 | “A lender reviewing a receivable needs to reconcile its invoice, purchase order and recorded financing claims. VaultLine Verify makes these checks traceable. Every record in this demonstration is synthetic.” | Show `/cases` and the five seeded SYNTHETIC case names. | Local verification workspace; no customer data or production claims. |
| 0:15–0:50 | “I create a case and explicitly identify each document type. The system preserves the uploaded evidence, extracts observed fields and normalizes amounts using Decimal. Extraction does not independently authenticate the documents.” | In **Counterparty name**, enter `SYNTHETIC Recording intake`; click **New verification**, then its `VL-…` reference. Select **Invoice**, choose `SYNTHETIC-recording-invoice.csv`, click **Upload document**, then **Extract financial fields** in that document. Repeat with type **Purchase order** and `SYNTHETIC-recording-purchase_order.csv`. | Both document types are correct; both show **Extraction: extracted**. No extraction validation findings. Invoice and PO each state USD 1,000.00. |
| 0:50–1:10 | “This pair agrees on its reference, parties, currency and supported line items. Every comparison retains its evidence. Here, the source row and original value explain exactly where the observation came from.” | Click **Run verification**. In either extracted document, open **Field provenance and original values**; briefly highlight a row location and original/normalized total. | **Passed document checks**; row/column source references and `csv_field_value_v1` provenance. Passed comparisons do not establish legal rights. |
| 1:10–1:35 | “This second invoice is twelve hundred dollars against a thousand-dollar purchase order. The deterministic engine flags the total and unit-price discrepancies, rather than asking AI to invent a financial conclusion.” | Switch to **SYNTHETIC Invoice exceeds PO**. Click **Run verification**. Find **invoice total** and open **Source documents and field provenance**. | **Discrepancy — investigate**. Invoice total `1200.00`, PO total `1000.00`; unit prices `600.00` versus `500.00`, with supporting document IDs. |
| 1:35–2:00 | “Two other cases record seven-hundred-dollar assertions from different synthetic lenders against matching invoice evidence. VaultLine flags potential competing claims and fourteen hundred dollars of recorded amounts against a thousand-dollar invoice. These assertions do not prove actual financing.” | Briefly show lender A’s recorded claim, switch to lender B, click **Run verification**, then **Load claims and conflicts**. Open **Supporting invoice evidence and provenance** under the competing-claims finding. | Alpha/Beta assertions are visible in their respective cases. B shows **Potential competing claims — investigate** and **Recorded active amounts exceed invoice total**; supporting IDs span two cases. |
| 2:00–2:25 | “Risk assessment summarizes the existing checks into explainable categories. These findings require human review. External financing remains unknown. This is neither a default probability nor an automatic lending decision, and every indicator points back to its source.” | In lender B’s case, click **Assess recorded evidence**. Open **Supporting deterministic findings and provenance** beneath **Potential competing recorded claims**. | **Findings require human review**; current verification coverage, rule version, claim/finding references, unknown external financing and mandatory human review. No score percentage. |
| 2:25–2:50 | “The separate investigation adapter targets Meta Muse Spark, using a bounded evidence package and strictly validated references. Live inference is not yet validated because billing is restricted. For this recording, requests are explicitly disabled, so no provider call is made. Offline mock tests are not live Meta inference.” | In the same case, click **Start investigation** in **AI Investigation**. Show the resulting provider/model/error record. Do not open credential or account settings. | Provider `meta`, model `muse-spark-1.3`, status `failed`; **Live Meta requests are disabled for this demo. No provider call was made.** No invented executive summary or successful Meta output. |
| 2:50–3:00 | “The result is a reproducible evidence trail for human review, with explicit discrepancies and unknowns. Our automated API and browser journeys exercise this synthetic workflow. VaultLine verifies recorded evidence; it does not certify ownership or approve financing.” | End on the risk assessment’s human-review requirement and external-financing limitation. | Honest dataset scope and review requirement remain visible. |

Read at a measured pace and rehearse with the file chooser prepared. UI actions happen during narration.
If uploads exceed their time slot, trim pauses or use an honestly edited recording of the same executed
workflow; do not simulate API results or relabel test output as a live provider response.

## Synthetic data reference sheet

| Purpose | Files/cases | Expected evidence |
| --- | --- | --- |
| New recorded intake | `demo/synthetic/SYNTHETIC-recording-invoice.csv` and `SYNTHETIC-recording-purchase_order.csv` | Unique `SYNTHETIC-RECORDING-INV` / `SYNTHETIC-RECORDING-PO`; USD 1,000.00 each; two units at USD 500.00 |
| Seeded clean fallback | `SYNTHETIC-matching-*.csv`; **SYNTHETIC Matching invoice and PO** | Matching fields/lines; rerun verification before assessment if new invoices have been added |
| Deliberate discrepancy | `SYNTHETIC-mismatch-*.csv`; **SYNTHETIC Invoice exceeds PO** | USD 1,200.00 invoice / USD 1,000.00 PO; different unit prices |
| Potential conflict | `SYNTHETIC-conflict-*.csv`; **SYNTHETIC Potential conflict lender A/B** | Matching invoice evidence, two active USD 700.00 recorded assertions; SYNTHETIC Lender Alpha/Beta |
| Optional rehearsal of unknowns | **SYNTHETIC Missing evidence** | Missing invoice/PO, insufficient evidence; never proof of fraud |

`demo/synthetic/manifest.json` defines the five seeded cases. The recording pair is deliberately not
seeded, so a new intake can be uploaded on camera without colliding with the seeded clean invoice.
All these amounts and names are constructed fixtures, not customer or lender records.

## Recording checklist

- Start only the isolated demo processes above; confirm ports 8101/3100 and the SYNTHETIC case list.
- Rehearse once, stop only the demo processes, then relaunch for a clean final take.
- Prepare file chooser and tabs; keep the app readable at a consistent zoom and resolution.
- Keep terminal env files, secret managers, account/billing pages, personal notifications and private
  browser tabs out of the capture. Never display API keys, real uploaded evidence or user cases.
- Keep SYNTHETIC names visible. Describe claims as recorded assertions, conflicts as potential,
  source observations as unverified, and risk categories as human-review indicators.
- Show the actual locally disabled Meta error. Do not claim a request was sent to Meta in this take.
- If showing any test report, label it OFFLINE TEST / MOCK where applicable; do not present a mock
  investigation as a successful Meta response or a measure of model quality.
- Verify the final export is approximately 3:00, narration is audible, text is legible and no frame
  leaks private information. Keep video exports outside the source tree.
- Replace submission video/repository placeholders only with actual published URLs, after approval.

## Billing-restricted fallback

The primary script is already the honest billing-restricted fallback: demonstrate all deterministic
features and show the investigation integration’s explicit local-disabled state. Billing restriction
is reported from the project’s known status, not inferred from this local error. Do not enable live
requests, run `meta_smoke.py`, alter billing/credentials, inject a runtime mock, or fabricate output.

If a UI/recording issue occurs, use a clearly labeled prerecorded take of the same synthetic workflow
or show the saved deterministic runs and provenance while explaining what is prerecorded. Successful
structured investigation generation can be evidenced by the existing **test-only** mock/adapter tests,
but must remain separate from the live application demonstration. Public submission must retain the
live-Meta limitation until a separately authorized successful real request is actually validated.
