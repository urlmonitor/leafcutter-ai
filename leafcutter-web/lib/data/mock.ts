/**
 * Mock-mode decision module — UXP-553 / UXP-553-1 / UXP-607 / UXP-608.
 *
 * This module is intentionally NOT marked "server-only" so that CI scripts and
 * the drift guard can import it outside the Next.js request scope. When called
 * outside a request (no cookies/headers context), it degrades to the env default
 * and NEVER throws.
 *
 * isMockActive() is the SINGLE source of truth for the resolved mock/live
 * decision: the mock/live badge (components/shell/sidebar.tsx) and every data
 * loader (via lib/data/repo.ts → repoRoot()) both call this same function, so
 * they can never diverge.
 *
 * Resolution order (highest priority first):
 *   1. LEAFCUTTER_MOCK_LOCK=real        — production lock; forces real data,
 *      beats everything else, including the opt-in below.
 *   2. Production default-deny          — when NODE_ENV=production and
 *      LEAFCUTTER_MOCK_ALLOW_OVERRIDE is NOT "1", any runtime override is
 *      IGNORED and resolution falls straight through to the env default (3).
 *      Non-production (dev/preview) is never default-deny: overrides are
 *      honored with no opt-in required.
 *   3. x-mock-active request header     — the runtime override, set by
 *      middleware.ts from the ?mock query-param + "mock" cookie; "1" = mock
 *      on, "0" = mock off. Only reached when step 2 does not short-circuit.
 *   4. LEAFCUTTER_MOCK=1                — server env default.
 *
 * The x-mock-active header is the runtime override mechanism that covers both the
 * ?mock query-param and the "mock" cookie (middleware normalises both into this header
 * on every request so isMockActive() sees the resolved value in the same request).
 *
 * Production detection is evaluated SERVER-SIDE ONLY (process.env.NODE_ENV) —
 * never inferred from request input, which an anonymous visitor could forge.
 * The detection itself lives in ./runtime (isProductionRuntime()) — the same
 * function the CI-only route handlers (app/api/drift-guard,
 * app/api/mock-toggle-check) call to decide whether they exist at all
 * (UXP-610), so the two decisions can never drift apart.
 */

import path from "node:path";
import { headers } from "next/headers";
import { isProductionRuntime } from "./runtime";

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
 * headers() is imported statically (not via require()) so the module is
 * mockable via vi.doMock("next/headers", ...) in tests — a runtime
 * require() call is NOT intercepted by the ESM mock graph. Every real
 * caller of this module (Server Components, Route Handlers, and CI's
 * next-start-based drift-guard/mock-toggle-check checks) runs inside
 * Next.js's own bundler, so the static import always resolves; the
 * try/catch below exists because headers() itself THROWS when called
 * outside an active request scope (e.g. during static generation), not
 * because the import can fail.
 */
function tryReadRequestOverride(): boolean | null {
  try {
    const h = headers();
    const v = h.get("x-mock-active");
    if (v === "1") return true;
    if (v === "0") return false;
    return null;
  } catch {
    // Throws when called outside a Next.js request scope (e.g. static
    // generation). Fall through to env default.
    return null;
  }
}

function envDefault(): boolean {
  // LEAFCUTTER_MOCK=1 means mock on; unset or any other value means real.
  return process.env.LEAFCUTTER_MOCK === "1";
}

/**
 * Returns true when mock mode is active for the current request.
 *
 * Safe to call in any context — outside a Next.js request scope it falls back
 * to the env default and never throws.
 */
export function isMockActive(): boolean {
  // 1. Production lock — highest priority; beats everything, including the
  //    explicit opt-in below.
  if (process.env.LEAFCUTTER_MOCK_LOCK === "real") return false;

  // 2. Production default-deny: outside of an explicit opt-in, a production
  //    deployment must never honor an anonymous visitor's runtime override —
  //    fall straight through to the env default. Non-production is NOT
  //    default-deny (UXP-608-3): dev/preview honor overrides unconditionally.
  const allowOverrideInProduction = process.env.LEAFCUTTER_MOCK_ALLOW_OVERRIDE === "1";
  if (isProductionRuntime() && !allowOverrideInProduction) {
    return envDefault();
  }

  // 3. Runtime override from middleware-forwarded header.
  //    Middleware resolves ?mock query-param + "mock" cookie into x-mock-active,
  //    so a single headers() call covers both runtime override mechanisms.
  const override = tryReadRequestOverride();
  if (override !== null) return override;

  // 4. Env default.
  return envDefault();
}
