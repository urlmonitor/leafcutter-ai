/**
 * Drift-guard endpoint — UXP-554 parse-through check / UXP-609 hardening /
 * UXP-610 production route gating.
 *
 * Invokes the real Atlas loaders (getAtlas, getFlows, getMockData, getScreenTitles)
 * against whichever repo root isMockActive() resolves. When the server is started
 * with LEAFCUTTER_MOCK=1, every loader reads from leafcutter-web/fixtures/ via the
 * repoRoot() seam — exercising the same repoPath() → parse path the app uses.
 *
 * CI invokes this route after building with LEAFCUTTER_MOCK=1 and starting the
 * server; a non-200 response or a truthy `errors` array fails the build.
 *
 * UXP-609: this is a CI-only check that only means anything when it is
 * genuinely comparing fixtures. Two hard requirements, both enforced before
 * any drift is evaluated:
 *   1. Mock mode must genuinely be active (isMockActive() === true) — a
 *      mis-configured CI run (server started without LEAFCUTTER_MOCK=1, or a
 *      production lock/default-deny silently overriding it) must fail loudly
 *      by name, never report a false-green "no drift found". The drift
 *      loaders are never invoked when this gate fails.
 *   2. Every loader must return at least one fixture record for the view it
 *      checks — a loader returning zero records (e.g. an empty/renamed
 *      fixtures directory) is itself a failure, not a vacuous clean pass.
 *
 * UXP-610: this endpoint is CI-only and must not exist in a production
 * deployment. It uses isProductionRuntime() (lib/data/runtime.ts) — the SAME
 * server-side NODE_ENV signal isMockActive() itself gates on for the
 * production default-deny — so "present in CI" and "absent in production"
 * are two sides of the one decision and cannot drift apart. In production
 * the handler returns a bare not-found before running any of its real logic
 * — including before the loader modules are even imported — so it is
 * genuinely inert rather than a handler that runs and formats an error
 * response.
 *
 * Returns:
 *   404                                                     — production; endpoint does not exist
 *   503 { ok: false, errors: [...] }                        — mock mode not active; drift never evaluated
 *   200 { ok: true,  checks: { ... } }                       — all checks pass
 *   500 { ok: false, errors: string[], checks: { ... } }     — at least one check failed (incl. empty fixtures)
 */

import { NextResponse } from "next/server";
import { isMockActive, FIXTURE_ROOT } from "@/lib/data/mock";
import { isProductionRuntime } from "@/lib/data/runtime";

// MUST be dynamic. Without this Next.js statically prerenders the handler at
// BUILD time and serves that frozen response forever — so the production gate
// below was evaluated once during `next build` (where CI is unset, hence
// "production") and the resulting 404 was baked into the artifact. CI then got
// a 404 no matter what its runtime environment said, breaking the fixture
// parse-through check. This handler's answer depends on runtime env and
// request scope, so it can never be prerendered.
export const dynamic = "force-dynamic";

interface CheckResult {
  label: string;
  count: number;
  pass: boolean;
  error?: string;
}

// Signature keeps an (unused) NextRequest param for compatibility with
// callers that pass one — this route needs no field off it, since
// isMockActive() reads next/headers() directly.
// eslint-disable-next-line @typescript-eslint/no-unused-vars
// Declared with NO parameter: Next.js validates the route-handler signature at
// build time and rejects an optional first argument ("NextRequest | undefined"
// is not assignable to "NextRequest | Request"), which fails `next build`. The
// request object is unused here, and a zero-arg handler is valid for both
// Next.js and the tests, which invoke GET() directly.
export async function GET(): Promise<NextResponse> {
  // UXP-610: CI-only endpoint — genuinely absent in production. Short-circuit
  // before any real logic runs, and before the loader modules below are even
  // imported (they are loaded lazily, on demand, past this point).
  if (isProductionRuntime()) {
    return new NextResponse(null, { status: 404 });
  }

  const mockActive = isMockActive();

  // UXP-609: assert mock mode is genuinely active BEFORE evaluating drift.
  // A misconfigured CI run must fail loudly, by name — never silently report
  // "no drift found" while actually comparing nothing.
  if (!mockActive) {
    return NextResponse.json(
      {
        ok: false,
        mockActive,
        errors: [
          "drift-guard: mock mode is not active (isMockActive() resolved to false) — " +
            "refusing to evaluate drift. The CI workflow must start the server with " +
            "LEAFCUTTER_MOCK=1 so drift-guard is genuinely comparing against fixtures.",
        ],
        checks: [],
      },
      { status: 503 },
    );
  }

  const errors: string[] = [];
  const checks: CheckResult[] = [];

  // ── 1. getAtlas() — exercises ac-store, tickets, components, roadmap, agents loaders ──
  // Loader modules are imported lazily (dynamic import), reached only past the
  // production-gate and mock-active-gate above, so they are never loaded at
  // all in a production process.
  try {
    const { getAtlas } = await import("@/lib/data/atlas");
    const atlas = getAtlas();

    checks.push({
      label: "atlas.acs",
      count: atlas.acs.length,
      pass: atlas.acs.length > 0,
    });
    if (atlas.acs.length === 0) errors.push("getAtlas(): acs is empty — no ACs parsed from fixtures");

    checks.push({
      label: "atlas.tickets",
      count: atlas.tickets.length,
      pass: atlas.tickets.length > 0,
    });
    if (atlas.tickets.length === 0) errors.push("getAtlas(): tickets is empty — no markdown tickets parsed from fixtures");

    checks.push({
      label: "atlas.agents",
      count: atlas.agents.length,
      pass: atlas.agents.length > 0,
    });
    if (atlas.agents.length === 0) errors.push("getAtlas(): agents is empty — config/agent_registry.json not parsed from fixtures");

    checks.push({
      label: "atlas.roadmap.phases",
      count: atlas.roadmap.phases.length,
      pass: atlas.roadmap.phases.length > 0,
    });
    if (atlas.roadmap.phases.length === 0) errors.push("getAtlas(): roadmap.phases is empty — docs/roadmap.json not parsed from fixtures");

    checks.push({
      label: "atlas.components",
      count: atlas.components.length,
      pass: atlas.components.length > 0,
    });
    if (atlas.components.length === 0) errors.push("getAtlas(): components is empty — docs/components.json not parsed from fixtures");

    checks.push({
      label: "atlas.acComponents",
      count: atlas.acComponents.length,
      pass: atlas.acComponents.length > 0,
    });
    if (atlas.acComponents.length === 0) errors.push("getAtlas(): acComponents is empty — docs/acceptance-criteria/index.yaml not parsed from fixtures");
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    errors.push(`getAtlas() threw: ${msg}`);
    checks.push({ label: "getAtlas()", count: 0, pass: false, error: msg });
  }

  // ── 2. getFlows() — exercises flows.ts loader ──
  try {
    const { getFlows } = await import("@/lib/data/flows");
    const flows = getFlows();
    checks.push({
      label: "flows",
      count: flows.length,
      pass: flows.length > 0,
    });
    if (flows.length === 0) errors.push("getFlows(): no flows parsed — docs/product-truth/flows/** not parsed from fixtures");
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    errors.push(`getFlows() threw: ${msg}`);
    checks.push({ label: "getFlows()", count: 0, pass: false, error: msg });
  }

  // ── 3. getMockData() — exercises mock-data loader ──
  try {
    const { getMockData } = await import("@/lib/data/flows");
    const mocks = getMockData();
    checks.push({
      label: "mock-data",
      count: mocks.length,
      pass: mocks.length > 0,
    });
    if (mocks.length === 0) errors.push("getMockData(): no mock datasets parsed — docs/product-truth/mock-data/** not parsed from fixtures");
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    errors.push(`getMockData() threw: ${msg}`);
    checks.push({ label: "getMockData()", count: 0, pass: false, error: msg });
  }

  // ── 4. getScreenTitles() — exercises mockup loader ──
  try {
    const { getScreenTitles } = await import("@/lib/data/flows");
    const titles = getScreenTitles();
    const count = Object.keys(titles).length;
    checks.push({
      label: "screen-titles",
      count,
      pass: count > 0,
    });
    if (count === 0) errors.push("getScreenTitles(): no screen titles found — docs/product-truth/mockups/** not parsed from fixtures");
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    errors.push(`getScreenTitles() threw: ${msg}`);
    checks.push({ label: "getScreenTitles()", count: 0, pass: false, error: msg });
  }

  const payload = {
    ok: errors.length === 0,
    mockActive,
    fixtureRoot: mockActive ? FIXTURE_ROOT : null,
    errors,
    checks,
  };

  return NextResponse.json(payload, {
    status: errors.length === 0 ? 200 : 500,
  });
}
