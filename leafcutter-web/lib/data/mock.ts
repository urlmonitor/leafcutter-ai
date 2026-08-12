/**
 * Mock-mode decision module — UXP-553 / UXP-553-1.
 *
 * This module is intentionally NOT marked "server-only" so that CI scripts and
 * the drift guard can import it outside the Next.js request scope. When called
 * outside a request (no cookies/headers context), it degrades to the env default
 * and NEVER throws.
 *
 * Resolution order (highest priority first):
 *   1. LEAFCUTTER_MOCK_LOCK=real  — production lock; forces real data, ignores all overrides
 *   2. x-mock-active request header — set by middleware from ?mock query-param + cookie;
 *      "1" = mock on, "0" = mock off
 *   3. LEAFCUTTER_MOCK=1          — server env default
 *
 * The x-mock-active header is the runtime override mechanism that covers both the
 * ?mock query-param and the "mock" cookie (middleware normalises both into this header
 * on every request so isMockActive() sees the resolved value in the same request).
 */

import path from "node:path";

/**
 * Absolute path to the bundled fixture repo root.
 * At Next.js runtime, process.cwd() is the app root (leafcutter-web/).
 */
export const FIXTURE_ROOT: string = path.join(process.cwd(), "fixtures");

/**
 * Try to read the x-mock-active header set by the middleware for the current request.
 *
 * Returns:
 *   true  — header is "1"
 *   false — header is "0"
 *   null  — header absent, OR called outside a Next.js request scope
 *
 * Uses dynamic require() so that a Node.js script that imports this module does NOT
 * fail at import time when next/headers is unavailable; the error is caught at call
 * time and treated as "no override".
 */
function tryReadRequestOverride(): boolean | null {
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const nh = require("next/headers") as {
      headers: () => { get(name: string): string | null };
    };
    const h = nh.headers();
    const v = h.get("x-mock-active");
    if (v === "1") return true;
    if (v === "0") return false;
    return null;
  } catch {
    // Throws when called outside a Next.js request scope (Node scripts, CI drift guard).
    // Fall through to env default.
    return null;
  }
}

/**
 * Returns true when mock mode is active for the current request.
 *
 * Safe to call in any context — outside a Next.js request scope it falls back
 * to the env default and never throws.
 */
export function isMockActive(): boolean {
  // 1. Production lock — highest priority; cannot be overridden.
  if (process.env.LEAFCUTTER_MOCK_LOCK === "real") return false;

  // 2. Runtime override from middleware-forwarded header.
  //    Middleware resolves ?mock query-param + "mock" cookie into x-mock-active,
  //    so a single headers() call covers both runtime override mechanisms.
  const override = tryReadRequestOverride();
  if (override !== null) return override;

  // 3. Env default — LEAFCUTTER_MOCK=1 means mock on; unset or 0 means real.
  return process.env.LEAFCUTTER_MOCK === "1";
}
