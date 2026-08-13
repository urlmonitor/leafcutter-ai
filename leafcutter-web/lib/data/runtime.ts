/**
 * Runtime-environment detection — UXP-608 / UXP-610.
 *
 * Deliberately its own tiny module (not folded into lib/data/mock.ts) so that
 * a test which replaces the ENTIRE "@/lib/data/mock" module via
 * vi.doMock(...) (providing only isMockActive/FIXTURE_ROOT, e.g.
 * app/api/drift-guard/__tests__/drift-guard.test.ts) does not also have to
 * know about — or accidentally break on — the production-runtime signal.
 *
 * isProductionRuntime() is the SINGLE source of truth for "is this a
 * production deployment": lib/data/mock.ts's isMockActive() calls it for the
 * production default-deny gate (UXP-608), and the CI-only route handlers
 * (app/api/drift-guard, app/api/mock-toggle-check) call the SAME function to
 * decide whether they are even present (UXP-610). Because both call sites
 * share one function, "present in CI" and "absent in production" can never
 * drift into two different decisions.
 */

/**
 * True when this process is a production runtime, per the server-side
 * NODE_ENV signal only. Never inferred from request input — an anonymous
 * visitor could forge a header or query param, but not this process's
 * own environment.
 */
export function isProductionRuntime(): boolean {
  return process.env.NODE_ENV === "production";
}
