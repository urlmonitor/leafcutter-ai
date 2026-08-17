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
 * True when this process is a production DEPLOYMENT.
 *
 * Two server-side signals, never request input — an anonymous visitor can
 * forge a header or a query param, but not this process's own environment.
 *
 * NODE_ENV alone is NOT sufficient, and assuming it was shipped a real
 * regression: CI runs the app as a PRODUCTION BUILD (`next start` sets
 * NODE_ENV=production) in order to exercise the real loaders, so gating on
 * NODE_ENV alone removed /api/drift-guard in CI and broke the very
 * fixture-parse-through check that depends on it — the exact failure
 * UXP-610-2 exists to prevent ("gating the endpoints out of production must
 * not disable the CI checks that depend on them"). A production build is not
 * a production deployment.
 *
 * `CI` is set to a non-empty value by GitHub Actions and effectively every
 * other CI provider, so a CI run is never treated as production. A real
 * production deployment does not set it. The default remains fail-safe: with
 * neither signal present (a plain `next start` on a server), NODE_ENV is
 * production and CI is unset, so this correctly returns true.
 */
export function isProductionRuntime(): boolean {
  if (process.env.CI) return false;
  return process.env.NODE_ENV === "production";
}
