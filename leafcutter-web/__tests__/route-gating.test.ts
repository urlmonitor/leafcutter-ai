/**
 * Black-box integration tests for:
 *   (a) the mock-mode default-deny gate at the middleware.ts + lib/data/mock.ts
 *       seam, and
 *   (b) the CI-only endpoint production gating (app/api/drift-guard,
 *       app/api/mock-toggle-check),
 * derived exclusively from the acceptance criteria — NOT from reading the
 * implementation.
 *
 * ACs covered: UXP-608, UXP-608-1, UXP-608-3, UXP-610, UXP-610-1, UXP-610-2.
 *
 * Seam test (Source-of-Truth Discipline Rule 3 / cross-layer seam coverage):
 * pipes a real NextRequest (carrying the query param / cookie) into the real
 * middleware(), reads whatever it forwards downstream via Next.js's
 * documented request-header-rewrite mechanism
 * (x-middleware-override-headers / x-middleware-request-<name> — a public
 * Next.js framework behavior, not an implementation detail of this app), and
 * feeds that into the real isMockActive() to assert the FINAL resolved
 * decision — the thing the badge and every view actually consume. This
 * avoids assuming which of middleware.ts / mock.ts performs the gating (the
 * AC only requires the seam as a whole to gate correctly).
 */
import { describe, it, expect, afterEach, vi } from "vitest";
import { NextRequest } from "next/server";

// "CI" is managed here on purpose: a production DEPLOYMENT is NODE_ENV=production
// with CI unset, because CI itself runs the app as a production BUILD. applyEnv
// deletes every managed key a scenario does not set, so each case below states
// the full signal and never inherits the ambient CI variable — otherwise these
// tests would pass locally and fail inside CI (or vice versa).
const ENV_KEYS = [
  "NODE_ENV",
  "CI",
  "LEAFCUTTER_MOCK",
  "LEAFCUTTER_MOCK_LOCK",
  "LEAFCUTTER_MOCK_ALLOW_OVERRIDE",
] as const;
type EnvKey = (typeof ENV_KEYS)[number];

let savedEnv: Partial<Record<EnvKey, string | undefined>> = {};

function applyEnv(env: Partial<Record<EnvKey, string>>) {
  savedEnv = {};
  for (const k of ENV_KEYS) {
    savedEnv[k] = process.env[k];
    if (env[k] !== undefined) process.env[k] = env[k];
    else delete process.env[k];
  }
}

afterEach(() => {
  for (const k of ENV_KEYS) {
    if (savedEnv[k] === undefined) delete process.env[k];
    else process.env[k] = savedEnv[k];
  }
  vi.resetModules();
  vi.restoreAllMocks();
});

/**
 * Extracts the x-mock-active value middleware forwarded to the downstream
 * request scope, using Next.js's documented header-rewrite mechanism. Falls
 * back to reading the header directly off the response, in case the
 * implementation sets it there instead.
 */
function forwardedMockHeader(response: Response): string | null {
  const overrideNames = response.headers.get("x-middleware-override-headers");
  if (overrideNames) {
    const names = overrideNames.split(",").map((s) => s.trim().toLowerCase());
    if (names.includes("x-mock-active")) {
      return response.headers.get("x-middleware-request-x-mock-active");
    }
  }
  return response.headers.get("x-mock-active");
}

async function runMiddleware(url: string, headers?: Record<string, string>) {
  vi.resetModules();
  const { middleware } = await import("@/middleware");
  const request = new NextRequest(url, { headers });
  return middleware(request);
}

/**
 * Resolves isMockActive() against a simulated forwarded header, under
 * whatever env the calling test already applied via applyEnv().
 */
async function resolveWithForwardedHeader(forwardedHeader: string | null) {
  vi.resetModules();
  vi.doMock("next/headers", () => ({
    headers: () => ({
      get: (name: string) => (name === "x-mock-active" ? forwardedHeader : null),
    }),
  }));
  const mod = await import("@/lib/data/mock");
  return mod.isMockActive();
}

describe("UXP-608 — production default-deny ignores an untrusted runtime override", () => {
  it("production_default_deny_ignores_mock_query_param", async () => {
    // covers: UXP-608
    applyEnv({ NODE_ENV: "production" });
    const response = await runMiddleware("http://localhost/roadmap?mock=1");
    const forwarded = forwardedMockHeader(response);
    const resolved = await resolveWithForwardedHeader(forwarded);
    // Default-deny: an anonymous visitor's override must be ignored — live.
    expect(resolved).toBe(false);
  });

  it("production_default_deny_ignores_mock_cookie", async () => {
    // covers: UXP-608
    applyEnv({ NODE_ENV: "production" });
    const response = await runMiddleware("http://localhost/roadmap", {
      cookie: "mock=1",
    });
    const forwarded = forwardedMockHeader(response);
    const resolved = await resolveWithForwardedHeader(forwarded);
    expect(resolved).toBe(false);
  });
});

describe("UXP-608-1 — an explicit production opt-in honors the runtime override", () => {
  it("production_opt_in_honors_mock_override", async () => {
    // covers: UXP-608-1
    applyEnv({ NODE_ENV: "production", LEAFCUTTER_MOCK_ALLOW_OVERRIDE: "1" });
    const response = await runMiddleware("http://localhost/roadmap?mock=1");
    const forwarded = forwardedMockHeader(response);
    const resolved = await resolveWithForwardedHeader(forwarded);
    expect(resolved).toBe(true);
  });
});

describe("UXP-608-3 — outside production, overrides are honored without an opt-in", () => {
  it("dev_preview_honors_override_without_opt_in", async () => {
    // covers: UXP-608-3
    applyEnv({ NODE_ENV: "development" });
    const response = await runMiddleware("http://localhost/roadmap?mock=1");
    const forwarded = forwardedMockHeader(response);
    const resolved = await resolveWithForwardedHeader(forwarded);
    expect(resolved).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// UXP-610 family — CI-only endpoints never ship live in production.
//
// ASSUMPTION (documented per the black-box mandate, since next.config.mjs is
// off-limits to read): "not compiled into the production build" is primarily
// a next.config.mjs / webpack build-time concern that a vitest unit test
// cannot observe (vitest never runs the Next.js bundler). The part of this AC
// family that IS observable at this layer is the route handler's OWN runtime
// response when NODE_ENV is production — per it_requirements, the not-found
// "must result from the endpoint being absent … not from a handler that runs
// and formats an error", which is only a meaningful constraint if route.ts
// ALSO refuses at runtime as defense in depth. If production exclusion turns
// out to live solely in next.config.mjs with zero runtime guard in route.ts,
// this test will fail for a legitimate reason (no runtime enforcement exists
// to observe here) rather than an infrastructure error — flagged in the
// completion report.
// ---------------------------------------------------------------------------

async function callDriftGuardRoute(url: string) {
  vi.resetModules();
  const mod = await import("@/app/api/drift-guard/route");
  const request = new NextRequest(url);
  return mod.GET(request);
}

async function callMockToggleCheckRoute(url: string) {
  vi.resetModules();
  const mod = await import("@/app/api/mock-toggle-check/route");
  const request = new NextRequest(url);
  return mod.GET(request);
}

describe("UXP-610 / UXP-610-1 — CI-only endpoints return a clean not-found in production", () => {
  it("prod_probe_returns_clean_not_found", async () => {
    // covers: UXP-610
    // covers: UXP-610-1
    applyEnv({ NODE_ENV: "production" });
    const driftResponse = await callDriftGuardRoute("http://localhost/api/drift-guard");
    const toggleResponse = await callMockToggleCheckRoute(
      "http://localhost/api/mock-toggle-check?mock=1"
    );

    expect(driftResponse.status).toBe(404);
    expect(toggleResponse.status).toBe(404);

    const driftBody = await driftResponse.text();
    const toggleBody = await toggleResponse.text();
    // No filesystem paths, stack traces, or handler-specific detail leaked.
    const leaks = /\/home\/|\.ts:\d|at\s+\w+\s+\(|Error:|stack|drift|fixture/i;
    expect(driftBody).not.toMatch(leaks);
    expect(toggleBody).not.toMatch(leaks);
  });
});

describe("UXP-610-2 — CI-only endpoints remain present outside production", () => {
  it("ci_build_includes_ci_endpoints", async () => {
    // covers: UXP-610-2
    applyEnv({ NODE_ENV: "test", LEAFCUTTER_MOCK: "1" });
    const driftResponse = await callDriftGuardRoute("http://localhost/api/drift-guard");
    const toggleResponse = await callMockToggleCheckRoute(
      "http://localhost/api/mock-toggle-check?mock=1"
    );
    // Present and responding — never the production not-found.
    expect(driftResponse.status).not.toBe(404);
    expect(toggleResponse.status).not.toBe(404);
  });
});
