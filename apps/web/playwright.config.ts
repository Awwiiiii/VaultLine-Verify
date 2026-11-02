import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 120000,
  expect: { timeout: 15000 },
  use: { channel: "chromium", baseURL: "http://127.0.0.1:3101", trace: "retain-on-failure" },
  webServer: [
    {
      command: ".venv/bin/python tests/browser_server.py",
      cwd: "../api",
      url: "http://127.0.0.1:8102/health",
      reuseExistingServer: false,
      timeout: 30000,
      gracefulShutdown: { signal: "SIGTERM", timeout: 10000 },
    },
    {
      command: "npm run dev -- --hostname 127.0.0.1 --port 3101",
      url: "http://127.0.0.1:3101/cases",
      env: { NEXT_PUBLIC_API_BASE_URL: "http://127.0.0.1:8102", VAULTLINE_NEXT_DIST_DIR: ".next-e2e" },
      reuseExistingServer: false,
      timeout: 90000,
      gracefulShutdown: { signal: "SIGTERM", timeout: 10000 },
    },
  ],
});
