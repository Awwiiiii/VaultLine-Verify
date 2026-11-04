import { expect, test, type Page } from "@playwright/test";
import { resolve } from "node:path";

const fixtures = resolve(process.cwd(), "../../demo/synthetic");

async function createCase(page: Page, name: string) {
  await page.goto("/cases");
  await page.getByLabel("Counterparty name", { exact: true }).fill(name);
  await page.getByRole("button", { name: "New verification", exact: true }).click();
  const row = page.getByRole("row").filter({ hasText: name });
  await row.getByRole("link").click();
  await expect(page.getByRole("heading", { name, exact: true })).toBeVisible();
  return page.url();
}

async function uploadAndExtract(page: Page, scenario: string) {
  for (const kind of ["invoice", "purchase_order"]) {
    const name = `SYNTHETIC-${scenario}-${kind}.csv`;
    const area = page.getByRole("region", { name: kind === "invoice" ? "Invoice documents" : "Purchase order documents", exact: true });
    await area.getByLabel(kind === "invoice" ? "Invoice file" : "Purchase order file", { exact: true }).setInputFiles(resolve(fixtures, name));
    await area.getByRole("button", { name: kind === "invoice" ? "Upload invoice" : "Upload purchase order", exact: true }).click();
    await expect(area.getByText("Upload successful:", { exact: false })).toBeVisible();
    const doc = page.getByRole("listitem").filter({ has: page.getByRole("heading", { name, exact: true }) });
    await expect(doc).toBeVisible();
    await expect(doc).toContainText(kind === "invoice" ? "Invoice" : "Purchase order");
    await doc.getByRole("button", { name: "Extract financial fields" }).click();
    await expect(doc.getByRole("heading", { name: "Extraction: extracted", exact: true })).toBeVisible();
    await doc.getByText("Field provenance and original values", { exact: true }).click();
    await expect(doc.getByRole("table")).toContainText("csv_field_value_v1");
    await expect(doc.getByRole("table")).toContainText("row: 2");
  }
}

async function runVerification(page: Page, expected: string) {
  const panel = page.getByRole("region", { name: "Cross-document verification", exact: true });
  await panel.getByRole("button", { name: "Run verification", exact: true }).click();
  await expect(panel.getByText(expected, { exact: true }).first()).toBeVisible();
  return panel;
}

async function assessRisk(page: Page, expected: string) {
  const panel = page.getByRole("region", { name: "Evidence-based risk assessment", exact: true });
  await panel.getByRole("button", { name: "Assess recorded evidence", exact: true }).click();
  await expect(panel.getByRole("heading", { name: expected, exact: true })).toBeVisible();
  await expect(panel).toContainText("A human must review source evidence");
  await expect(panel).toContainText("External financing remains unknown");
  return panel;
}

async function recordClaim(page: Page, lender: string) {
  const panel = page.getByRole("region", { name: "Financing claims", exact: true });
  await panel.getByRole("combobox", { name: "Invoice", exact: true }).selectOption({ index: 1 });
  await panel.getByLabel("Claim reference", { exact: true }).fill(`SYNTHETIC-${lender}-claim`);
  await panel.getByLabel("Lender identifier/name", { exact: true }).fill(`SYNTHETIC Lender ${lender}`);
  await panel.getByLabel("Amount (exact decimal)", { exact: true }).fill("700.00");
  await panel.getByLabel("Currency (USD/EUR/GBP/INR/JPY/KWD)", { exact: true }).fill("USD");
  await panel.getByRole("combobox", { name: "Status", exact: true }).selectOption("active");
  await panel.getByRole("button", { name: "Record claim", exact: true }).click();
  await expect(panel.getByRole("listitem")).toContainText(`SYNTHETIC Lender ${lender}`);
  return panel;
}

test.beforeEach(async ({ context }) => {
  // A frontend regression cannot send evidence to a public service during this test.
  await context.route("**/*", route => {
    const host = new URL(route.request().url()).hostname;
    return ["127.0.0.1", "localhost"].includes(host) ? route.continue() : route.abort();
  });
});

test("synthetic main journey: extraction, checks, competing claims, mock investigation and history", async ({ page }) => {
  await createCase(page, "SYNTHETIC Browser matching");
  await uploadAndExtract(page, "matching");
  await assessRisk(page, "Insufficient evidence for complete recorded checks");
  const matching = await runVerification(page, "Passed document checks");
  await runVerification(page, "Passed document checks");
  await expect(matching).toContainText("2 saved runs");
  await matching.getByRole("combobox").selectOption({ index: 2 });
  await expect(matching).toContainText("Passed document checks");
  await assessRisk(page, "No discrepancy found in the recorded checks");

  await createCase(page, "SYNTHETIC Browser mismatch");
  await uploadAndExtract(page, "mismatch");
  const mismatch = await runVerification(page, "Discrepancy — investigate");
  const total = mismatch.getByRole("article").filter({ has: page.getByRole("heading", { name: "invoice total", exact: true }) });
  await expect(total).toContainText("Discrepancy — investigate");
  const discrepancyRisk = await assessRisk(page, "Findings require human review");
  const riskTotal = discrepancyRisk.getByRole("article").filter({ has: page.getByRole("heading", { name: "Recorded discrepancy: invoice_total", exact: true }) });
  await riskTotal.getByText("Supporting deterministic findings and provenance", { exact: true }).click();
  await expect(riskTotal).toContainText("source_document_id");

  const firstCase = await createCase(page, "SYNTHETIC Browser conflict Alpha");
  await uploadAndExtract(page, "conflict");
  await runVerification(page, "Passed document checks");
  await recordClaim(page, "Alpha");
  await createCase(page, "SYNTHETIC Browser conflict Beta");
  await uploadAndExtract(page, "conflict");
  await runVerification(page, "Discrepancy — investigate");
  const claims = await recordClaim(page, "Beta");
  await expect(claims.getByRole("heading", { name: "Potential competing claims — investigate", exact: true })).toBeVisible();
  await expect(claims).toContainText("Recorded active amounts exceed invoice total");
  await expect(claims).toContainText("Recorded claims do not prove actual financing");
  await claims.getByText("Supporting invoice evidence and provenance", { exact: true }).first().click();
  await expect(claims).toContainText("source_document_id");
  const conflictRisk = await assessRisk(page, "Findings require human review");
  await expect(conflictRisk.getByRole("heading", { name: "Potential competing recorded claims", exact: true })).toBeVisible();
  await expect(conflictRisk.getByRole("heading", { name: "Recorded active amounts exceed invoice total", exact: true })).toBeVisible();

  const ai = page.getByRole("region", { name: "AI Investigation", exact: true });
  await ai.getByRole("button", { name: "Start investigation", exact: true }).click();
  await expect(ai.getByRole("heading", { name: "Executive summary", exact: true })).toBeVisible();
  await expect(ai).toContainText("TEST ONLY — deterministic mock investigation; no Meta response.");
  await expect(ai).toContainText("AI-generated interpretation");
  await expect(ai).toContainText("External financing is unknown and unverified.");
  await expect(ai).toContainText("1 saved investigations");
  await page.reload();
  await ai.getByRole("button", { name: "Load history", exact: true }).click();
  await ai.getByRole("combobox", { name: "Saved investigation", exact: true }).selectOption({ index: 1 });
  await expect(ai.getByRole("heading", { name: "Executive summary", exact: true })).toBeVisible();
  await page.goto(firstCase);
  await ai.getByRole("button", { name: "Load history", exact: true }).click();
  await expect(ai).toContainText("0 saved investigations");
  await expect(ai.getByRole("heading", { name: "Executive summary", exact: true })).toHaveCount(0);
});

test("creating a case from a later list page returns to the new case", async ({ page, request }) => {
  // All requests target the isolated test server, never the user's running API.
  for (let i = 0; i < 21; i++) {
    const result = await request.post("http://127.0.0.1:8102/api/v1/cases", { data: { counterparty_name: `SYNTHETIC pagination ${i}` } });
    expect(result.status()).toBe(201);
  }
  await page.goto("/cases");
  await page.getByRole("button", { name: "Next", exact: true }).click();
  await expect(page.getByRole("button", { name: "Previous", exact: true })).toBeEnabled();
  await page.getByLabel("Counterparty name", { exact: true }).fill("SYNTHETIC newest on page one");
  await page.getByRole("button", { name: "New verification", exact: true }).click();
  await expect(page.getByRole("row").filter({ hasText: "SYNTHETIC newest on page one" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Previous", exact: true })).toBeDisabled();
});

test("local preferences persist and dashboard uses bounded backend data", async ({ page }) => {
  await page.goto("/settings");
  await page.getByLabel("Theme", { exact: true }).selectOption("dark");
  await page.getByLabel("Default case-list page size").selectOption("10");
  await page.getByLabel("Date display").selectOption("iso");
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await expect(page.getByLabel("Default case-list page size")).toHaveValue("10");
  await expect(page.getByLabel("Date display")).toHaveValue("iso");
  await expect(page.getByText("test_only", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("Live Meta inference: untested.", { exact: false })).toBeVisible();
  const casesRequest = page.waitForRequest(r => r.url().includes("/api/v1/cases?limit=10&offset=0"));
  await page.getByRole("link", { name: "Verification cases", exact: true }).click();
  await casesRequest;
  await page.route("**/api/v1/cases?limit=5&offset=0", route => route.fulfill({ json: { total: 37, limit: 5, offset: 0, items: [{ id: "synthetic-case", case_reference: "SYNTHETIC-reference", counterparty_name: "SYNTHETIC Dashboard fixture", status: "open", created_at: "2026-01-02T12:00:00Z", updated_at: "2026-01-02T12:00:00Z" }] } }));
  await page.goto("/dashboard");
  await expect(page.getByText("37", { exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "SYNTHETIC Dashboard fixture" })).toHaveAttribute("href", "/cases/synthetic-case");
  await expect(page.getByText("Created 2026-01-02 12:00:00 UTC", { exact: false })).toBeVisible();
});

test("dashboard failure and malformed local preferences remain usable", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("vaultline-preferences", "null"));
  await page.route("**/api/v1/cases?limit=5&offset=0", route => route.fulfill({ status: 503, json: {} }));
  await page.goto("/dashboard");
  await expect(page.getByRole("alert").filter({hasText:"Unable to load overview"})).toBeVisible();
  await page.getByRole("link", { name: "Open Settings" }).click();
  await expect(page.getByLabel("Theme", { exact: true })).toHaveValue("light");
});

test("settings and case navigation fit a narrow viewport", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/settings");
  await page.getByLabel("Theme", { exact: true }).selectOption("dark");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.getByLabel("Theme", { exact: true }).selectOption("light");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
  await page.getByRole("link", { name: "Audit trail", exact: true }).click();
  await page.getByRole("link", { name: "Browse verification cases" }).click();
  await expect(page.getByRole("heading", { name: "Verification cases", exact: true })).toBeVisible();
});

test("Baseten diagnostics distinguish historical application success from availability", async ({ page }) => {
  await page.route("**/system/provider", route => route.fulfill({ json: {
    provider: "baseten", model: "meta-models/muse-spark-open", configuration: "configured",
    availability: "untested", live_validation: "owner_reported_application_success", basic_inference: "owner_reported_success",
  } }));
  await page.goto("/settings");
  await expect(page.getByText("baseten · meta-models/muse-spark-open", { exact: true })).toBeVisible();
  await expect(page.getByText("Baseten-hosted Meta basic inference: owner-reported success.", { exact: false })).toBeVisible();
  await expect(page.getByText("Normal application investigation: owner-confirmed completed with evidence references and mandatory limitations.", { exact: false })).toBeVisible();
});

test("separate uploads confirm persistence, prevent repeat submissions and keep one case", async ({ page, request }) => {
  const url = await createCase(page, "SYNTHETIC separate upload feedback");
  const id = url.split("/").pop();
  const invoice = page.getByRole("region", { name: "Invoice documents", exact: true });
  const po = page.getByRole("region", { name: "Purchase order documents", exact: true });
  await expect(invoice.getByText("No file selected", { exact: true })).toBeVisible();
  await expect(invoice.getByRole("button", { name: "Upload invoice", exact: true })).toBeDisabled();
  await invoice.getByLabel("Invoice file", { exact: true }).setInputFiles(resolve(fixtures, "SYNTHETIC-recording-invoice.csv"));
  await expect(invoice.getByText("File selected:", { exact: false })).toContainText("bytes");
  let posts = 0;
  let release!: () => void;
  const gate = new Promise<void>(resolve => { release = resolve; });
  await page.route(`**/cases/${id}/documents`, async route => {
    if (route.request().method() === "POST") { posts++; await gate; }
    await route.continue();
  });
  await invoice.getByRole("button", { name: "Upload invoice", exact: true }).evaluate(button => { (button as HTMLButtonElement).click(); (button as HTMLButtonElement).click(); });
  await expect(invoice.getByRole("button", { name: "Uploading invoice…", exact: true })).toBeDisabled();
  await expect(invoice.getByRole("progressbar")).toBeVisible();
  await expect(invoice.getByText("Upload successful:", { exact: false })).toHaveCount(0);
  release();
  await expect(invoice.getByText("Upload successful:", { exact: false })).toBeVisible();
  expect(posts).toBe(1);
  await expect(invoice.getByRole("button", { name: "Upload invoice", exact: true })).toBeDisabled();
  await expect(invoice).toContainText("Uploaded — not extracted");
  await po.getByLabel("Purchase order file", { exact: true }).setInputFiles(resolve(fixtures, "SYNTHETIC-recording-purchase_order.csv"));
  await po.getByRole("button", { name: "Upload purchase order", exact: true }).click();
  await expect(po.getByText("Upload successful:", { exact: false })).toBeVisible();
  const response = await request.get(`http://127.0.0.1:8102/api/v1/cases/${id}/documents`);
  const docs = await response.json();
  expect(docs).toHaveLength(2);
  expect(docs.map((d: { document_type: string }) => d.document_type).sort()).toEqual(["invoice", "purchase_order"]);
  await invoice.getByRole("button", { name: "Extract financial fields", exact: true }).click();
  await expect(invoice).toContainText("Extracted successfully");
  await page.reload();
  await expect(invoice).toContainText("Extracted successfully");
  await expect(po).toContainText("Uploaded — not extracted");
  await page.setViewportSize({ width: 390, height: 844 });
  const overflow = await page.evaluate(() => [...document.querySelectorAll("main *")].filter(e => e.getBoundingClientRect().right > innerWidth + 1).map(e => ({ tag: e.tagName, classes: e.className, width: e.getBoundingClientRect().width })).slice(0, 8));
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), JSON.stringify(overflow)).toBeTruthy();
});

test("upload failure and invalid selection give actionable feedback without false success", async ({ page }) => {
  const url = await createCase(page, "SYNTHETIC upload failures");
  const id = url.split("/").pop();
  const area = page.getByRole("region", { name: "Invoice documents", exact: true });
  await area.getByLabel("Invoice file", { exact: true }).setInputFiles({ name: "SYNTHETIC-invalid.txt", mimeType: "text/plain", buffer: Buffer.from("SYNTHETIC") });
  await area.getByRole("button", { name: "Upload invoice", exact: true }).click();
  await expect(area.getByRole("alert")).toContainText("non-empty PDF or CSV");
  await area.getByLabel("Invoice file", { exact: true }).setInputFiles(resolve(fixtures, "SYNTHETIC-recording-invoice.csv"));
  await page.route(`**/cases/${id}/documents`, route => route.request().method() === "POST" ? route.fulfill({ status: 503, json: { detail: "Upload service unavailable" } }) : route.continue());
  await area.getByRole("button", { name: "Upload invoice", exact: true }).click();
  await expect(area.getByRole("alert")).toContainText("Refresh documents before retrying");
  await expect(area.getByText("Upload successful:", { exact: false })).toHaveCount(0);
  await expect(area.getByRole("button", { name: "Upload invoice", exact: true })).toBeEnabled();
  await page.unroute(`**/cases/${id}/documents`);
  await area.getByRole("button", { name: "Upload invoice", exact: true }).click();
  await expect(area.getByText("Upload successful:", { exact: false })).toBeVisible();
});

test("extraction loading, failure and needs-review statuses preserve document evidence", async ({ page }) => {
  await createCase(page, "SYNTHETIC extraction feedback");
  const area = page.getByRole("region", { name: "Invoice documents", exact: true });
  await area.getByLabel("Invoice file", { exact: true }).setInputFiles({ name: "SYNTHETIC-incomplete.csv", mimeType: "text/csv", buffer: Buffer.from("field,value\ninvoice_number,SYNTHETIC-INCOMPLETE\n") });
  await area.getByRole("button", { name: "Upload invoice", exact: true }).click();
  await expect(area.getByText("Upload successful:", { exact: false })).toBeVisible();
  let release!: () => void;
  const gate = new Promise<void>(resolve => { release = resolve; });
  await page.route("**/documents/*/extract", async route => { await gate; await route.fulfill({ status: 503, json: { detail: "Extraction unavailable. Try again later." } }); });
  await area.getByRole("button", { name: "Extract financial fields", exact: true }).click();
  await expect(area.getByText("Reading and normalizing document fields…")).toBeVisible();
  await expect(area.getByRole("button", { name: "Processing…", exact: true })).toBeDisabled();
  release();
  await expect(area.getByRole("alert")).toContainText("Extraction unavailable");
  await page.unroute("**/documents/*/extract");
  await area.getByRole("button", { name: "Extract financial fields", exact: true }).click();
  await expect(area).toContainText("Extraction incomplete — review validation findings");
  await expect(area.getByRole("heading", { name: "Validation findings", exact: true })).toBeVisible();
  await area.getByText("Field provenance and original values", { exact: true }).click();
  await expect(area.getByRole("table")).toContainText("SYNTHETIC-INCOMPLETE");
});


test("saved extraction failure remains visible without hiding earlier documents", async ({ page }) => {
  await createCase(page, "SYNTHETIC saved extraction failure");
  const area = page.getByRole("region", { name: "Invoice documents", exact: true });
  await area.getByLabel("Invoice file", { exact: true }).setInputFiles({ name: "SYNTHETIC-extraction-row-limit.csv", mimeType: "text/csv", buffer: Buffer.from("field,value\n" + "note,SYNTHETIC\n".repeat(10002)) });
  await area.getByRole("button", { name: "Upload invoice", exact: true }).click();
  await expect(area.getByText("Upload successful:", { exact: false })).toBeVisible();
  await area.getByRole("button", { name: "Extract financial fields", exact: true }).click();
  await expect(area).toContainText("Extraction failed — inspect saved findings or retry");
  await expect(area.getByRole("button", { name: "Retry extraction", exact: true })).toBeEnabled();
  await page.reload();
  await expect(area).toContainText("Extraction failed — inspect saved findings or retry");
  await area.getByRole("button", { name: "View saved extraction", exact: true }).click();
  await expect(area.getByRole("heading", { name: "Extraction: failed", exact: true })).toBeVisible();
  await runVerification(page, "Insufficient evidence");
});
