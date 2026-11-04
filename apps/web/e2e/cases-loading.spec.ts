import { expect, test } from "@playwright/test";

test.beforeEach(async ({ context }) => {
  await context.route("**/*", route => ["127.0.0.1", "localhost"].includes(new URL(route.request().url()).hostname) ? route.continue() : route.abort());
});

test("five saved synthetic cases load and navigate without console errors", async ({ page, request }) => {
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.name));
  for (let index = 0; index < 5; index++) {
    expect((await request.post("http://127.0.0.1:8102/api/v1/cases", { data: { counterparty_name: `SYNTHETIC loading case ${index}` } })).status()).toBe(201);
  }
  await page.goto("/cases");
  await expect(page.locator("tbody tr")).toHaveCount(5);
  await expect(page.getByText("Loading cases…", { exact: true })).toHaveCount(0);
  await expect(page.getByText("5 cases", { exact: true })).toBeVisible();
  await page.getByRole("row").filter({ hasText: "SYNTHETIC loading case 4" }).getByRole("link").click();
  await expect(page.getByRole("heading", { name: "SYNTHETIC loading case 4", exact: true })).toBeVisible();
  expect(errors).toEqual([]);
});

test("case failure ends loading and Retry recovers without polling", async ({ page }) => {
  let failing = true; let calls = 0;
  await page.route("**/api/v1/cases?*", route => { calls++; return failing ? route.fulfill({ status: 503, json: {} }) : route.continue(); });
  await page.goto("/cases");
  const error = page.locator("main [role=alert]");
  await expect(error).toContainText("Unable to load cases");
  await expect(error).toContainText("http://127.0.0.1:8102");
  await expect(page.getByText("Loading cases…", { exact: true })).toHaveCount(0);
  const before = calls; failing = false;
  await page.getByRole("button", { name: "Retry loading cases", exact: true }).click();
  await expect(page.locator("tbody tr")).toHaveCount(5);
  expect(calls).toBe(before + 1);
  await expect(error).toHaveCount(0);
});

test("empty cases show a useful empty state", async ({ page }) => {
  await page.route("**/api/v1/cases?*", route => route.fulfill({ json: { items: [], total: 0, limit: 20, offset: 0 } }));
  await page.goto("/cases");
  await expect(page.getByText("No cases found. Create a verification case to add synthetic evidence.", { exact: true })).toBeVisible();
  await expect(page.getByText("Loading cases…", { exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Next", exact: true })).toBeDisabled();
});

test("null response cannot leave perpetual loading", async ({ page }) => {
  await page.route("**/api/v1/cases?*", route => route.fulfill({ contentType: "application/json", body: "null" }));
  await page.goto("/cases");
  await expect(page.locator("main [role=alert]")).toContainText("Unable to load cases");
  await expect(page.getByText("Loading cases…", { exact: true })).toHaveCount(0);
});

test("hung request times out and Retry succeeds", async ({ page }) => {
  let release!: () => void;
  const gate = new Promise<void>(resolve => { release = resolve; });
  await page.route("**/api/v1/cases?*", async route => { await gate; await route.abort().catch(() => {}); });
  await page.goto("/cases");
  await expect(page.locator("main [role=alert]")).toContainText("Unable to load cases", { timeout: 15000 });
  await expect(page.getByText("Loading cases…", { exact: true })).toHaveCount(0);
  release(); await page.unroute("**/api/v1/cases?*");
  await page.getByRole("button", { name: "Retry loading cases", exact: true }).click();
  await expect(page.locator("tbody tr")).toHaveCount(5);
});

test("navigation cancels a pending fetch and blocked storage uses defaults", async ({ page }) => {
  await page.addInitScript(() => { Object.defineProperty(window, "localStorage", { get() { throw new DOMException("Storage disabled", "SecurityError"); } }); });
  let release!: () => void;
  const gate = new Promise<void>(resolve => { release = resolve; });
  const seen = page.waitForRequest(request => request.url().includes("/api/v1/cases?limit=20&offset=0"));
  await page.route("**/api/v1/cases?*", async route => { await gate; await route.abort().catch(() => {}); });
  await page.goto("/cases"); await seen;
  await page.getByRole("link", { name: "Settings", exact: true }).click();
  release(); await page.unroute("**/api/v1/cases?*");
  await expect(page.getByRole("heading", { name: "Settings", exact: true })).toBeVisible();
  await page.getByRole("link", { name: "Verification cases", exact: true }).click();
  await expect(page.locator("tbody tr")).toHaveCount(5);
});
