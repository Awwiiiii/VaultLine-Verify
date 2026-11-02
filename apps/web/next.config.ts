import type { NextConfig } from "next";

const config: NextConfig = {
  // Keep browser/demo artifacts separate from an existing local development server.
  distDir: process.env.VAULTLINE_NEXT_DIST_DIR || ".next",
};
export default config;
