import type { NextConfig } from "next";
import { PHASE_DEVELOPMENT_SERVER } from "next/constants";

export default function config(phase: string): NextConfig {
  return {
    // A production build must not overwrite a running development server's chunks.
    // Explicit demo/e2e directories retain their existing behavior.
    distDir: process.env.VAULTLINE_NEXT_DIST_DIR ||
      (phase === PHASE_DEVELOPMENT_SERVER ? ".next-dev" : ".next"),
  };
}
