/**
 * Drift-guard endpoint — UXP-554 parse-through check.
 *
 * Invokes the real Atlas loaders (getAtlas, getFlows, getMockData, getScreenTitles)
 * against whichever repo root isMockActive() resolves. When the server is started
 * with LEAFCUTTER_MOCK=1, every loader reads from leafcutter-web/fixtures/ via the
 * repoRoot() seam — exercising the same repoPath() → parse path the app uses.
 *
 * CI invokes this route after building with LEAFCUTTER_MOCK=1 and starting the
 * server; a non-200 response or a truthy `errors` array fails the build.
 *
 * Returns:
 *   200 { ok: true,  checks: { ... } }                     — all checks pass
 *   500 { ok: false, errors: string[], checks: { ... } }   — at least one check failed
 */

import { NextResponse } from "next/server";
import { getAtlas } from "@/lib/data/atlas";
import { getFlows, getMockData, getScreenTitles } from "@/lib/data/flows";
import { isMockActive, FIXTURE_ROOT } from "@/lib/data/mock";

interface CheckResult {
  label: string;
  count: number;
  pass: boolean;
  error?: string;
}

export async function GET(): Promise<NextResponse> {
  const errors: string[] = [];
  const checks: CheckResult[] = [];

  const mockActive = isMockActive();

  // ── 1. getAtlas() — exercises ac-store, tickets, components, roadmap, agents loaders ──
  try {
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
