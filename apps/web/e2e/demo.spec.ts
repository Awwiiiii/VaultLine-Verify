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
    await page.getByRole("combobox", { name: "Document type", exact: true }).selectOption(kind);
    await page.getByLabel("Document", { exact: true }).setInputFiles(resolve(fixtures, name));
    await page.getByRole("button", { name: "Upload document", exact: true }).click();
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
