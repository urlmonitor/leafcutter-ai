/**
 * Mock-mode toggle regression guard — UXP-553.
 *
 * Asserts that the Atlas serves FIXTURE data when the runtime override is
 * mock-on (?mock=1 / x-mock-active: 1) and REAL data when mock-off
 * (?mock=0 / x-mock-active: 0) — all within a single running server process.
 *
 * Resolution path exercised end-to-end:
 *   HTTP request
 *   → middleware.ts  (reads ?mock param or "mock" cookie → sets x-mock-active header)
 *   → isMockActive() (reads x-mock-active header)
 *   → repoRoot()     (returns FIXTURE_ROOT when true, real repo root when false)
 *   → getFlows()     (Map<repoRoot,Flow[]> cache — one bucket per root)
 *   → presence of the fixture-only sentinel flow id asserted.
 *
 * Sentinel flow: "leafcutter/mock-mode-toggle"
 *   - Exists ONLY in leafcutter-web/fixtures/docs/product-truth/flows/leafcutter/.
 *   - Is absent from the live repo's docs/product-truth/flows/ directory.
 *   - mock=1 → MUST be present  (FIXTURE_ROOT loaded into its own cache bucket)
 *   - mock=0 → MUST be absent   (real repo root loaded into its own cache bucket)
 *
 * Two UXP-553 bug fixes guarded by this route:
 *   (A) middleware now persists a sticky cookie ("0"/"1") instead of deleting it,
 *       so ?mock=0 does not silently revert to the env default on the next request.
 *   (B) every loader caches by repoRoot() (Map<string,T>) so toggling the override
 *       within a single process does not serve stale data from the previous root.
 *
 * UXP-610: this endpoint is CI-only and must not exist in a production
 * deployment (it discloses which flow ids are fixture-only, and toggles data
 * sources on request — not something to expose to real visitors). It uses
 * isProductionRuntime() (lib/data/runtime.ts) — the SAME server-side NODE_ENV
 * signal the mock-mode data seam itself gates on for the production
 * default-deny — so "present in CI" and "absent in production" are two
 * sides of the one decision and cannot drift apart. In production the
 * handler returns a bare not-found before running any of its real logic —
 * including before the loader modules are even imported.
 *
 * Returns:
 *   404                     — production; endpoint does not exist
 *   200 { ok: true,  ... }  — mode and flow-presence match expectations
 *   500 { ok: false, ... }  — mismatch, or a loader threw; toggle/cache-by-root regressed
 */

import { NextResponse } from "next/server";
import { isMockActive, FIXTURE_ROOT } from "@/lib/data/mock";
import { isProductionRuntime } from "@/lib/data/runtime";

/**
 * Flow id that exists ONLY in the fixture store (leafcutter-web/fixtures/).
 * If this id is ever added to the real repo's product-truth flows, update this
 * constant to a different fixture-only id so the assertion stays meaningful.
 */
const FIXTURE_ONLY_FLOW_ID = "leafcutter/mock-mode-toggle";

// Declared with NO parameter: Next.js validates the route-handler signature at
// build time and rejects an optional first argument ("NextRequest | undefined"
// is not assignable to "NextRequest | Request"), which fails `next build`. This
// route needs no field off the request — isMockActive() reads next/headers()
// directly — and a zero-arg handler is valid for both Next.js and the tests.
export async function GET(): Promise<NextResponse> {
  // UXP-610: CI-only endpoint — genuinely absent in production. Short-circuit
  // before any real logic runs, and before the loader modules below are even
  // imported (they are loaded lazily, on demand, past this point).
  if (isProductionRuntime()) {
    return new NextResponse(null, { status: 404 });
  }

  const mockActive = isMockActive();

  let rootUsed: string;
  let flows: { id: string }[];
  try {
    const { repoRoot } = await import("@/lib/data/repo");
    const { getFlows } = await import("@/lib/data/flows");
    rootUsed = repoRoot();
    flows = getFlows();
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return NextResponse.json(
      { ok: false, mockActive, error: `loader threw: ${msg}` },
      { status: 500 },
    );
  }
  const fixtureFlowPresent = flows.some((f) => f.id === FIXTURE_ONLY_FLOW_ID);

  // Expected: the fixture-only sentinel is present iff mock is active.
  //   mock=on  → isMockActive()=true  → rootUsed=FIXTURE_ROOT → flow PRESENT ✓
  //   mock=off → isMockActive()=false → rootUsed=realRoot     → flow ABSENT  ✓
  //
  // If the Map cache leaked (single-value bug), querying mock=0 after mock=1
  // would return the cached fixture flows → flow still PRESENT → ok=false (500).
  const expectedPresence = mockActive;
  const ok = fixtureFlowPresent === expectedPresence;

  const payload = {
    ok,
    mockActive,
    repoRootUsed: rootUsed,
    fixtureRoot: FIXTURE_ROOT,
    fixtureFlowPresent,
    expectedPresence,
    flowId: FIXTURE_ONLY_FLOW_ID,
    flowCount: flows.length,
    error: ok
      ? null
      : mockActive
      ? `mock=1 but "${FIXTURE_ONLY_FLOW_ID}" is ABSENT — repoRoot() is not returning FIXTURE_ROOT, or loader is not using repoRoot()`
      : `mock=0 but "${FIXTURE_ONLY_FLOW_ID}" is PRESENT — cache-by-root leaked: fixture root data served under real-root key`,
  };

  return NextResponse.json(payload, { status: ok ? 200 : 500 });
}
