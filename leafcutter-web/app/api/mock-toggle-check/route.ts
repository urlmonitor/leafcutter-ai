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
 * Returns:
 *   200 { ok: true,  ... }  — mode and flow-presence match expectations
 *   500 { ok: false, ... }  — mismatch; toggle or cache-by-root has regressed
 */

import { NextResponse } from "next/server";
import { getFlows } from "@/lib/data/flows";
import { isMockActive, FIXTURE_ROOT } from "@/lib/data/mock";
import { repoRoot } from "@/lib/data/repo";

/**
 * Flow id that exists ONLY in the fixture store (leafcutter-web/fixtures/).
 * If this id is ever added to the real repo's product-truth flows, update this
 * constant to a different fixture-only id so the assertion stays meaningful.
 */
const FIXTURE_ONLY_FLOW_ID = "leafcutter/mock-mode-toggle";

export async function GET(): Promise<NextResponse> {
  const mockActive = isMockActive();
  const rootUsed = repoRoot();
  const flows = getFlows();
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
