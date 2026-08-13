/**
 * Black-box integration tests for the CI drift-guard route
 * (leafcutter-web/app/api/drift-guard/route.ts), derived exclusively from the
 * acceptance criteria — NOT from reading the implementation.
 *
 * ACs covered: UXP-609, UXP-609-1, UXP-609-2.
 *
 * Loader names (getAtlas / getFlows / getMockData / getScreenTitles) come
 * from .github/workflows/fixture-drift.yml's documented description of what
 * /api/drift-guard invokes ("which invokes the real loaders … against
 * leafcutter-web/fixtures/") — a CI workflow comment, not route.ts itself —
 * so citing them here stays within the black-box mandate.
 */
import { describe, it, expect, afterEach, vi } from "vitest";
import { NextRequest } from "next/server";

afterEach(() => {
  vi.resetModules();
  vi.restoreAllMocks();
});

// Full AtlasSnapshot shape (lib/data/types.ts — not on the forbidden list) so
// the real route.ts can run its checks against our fixture without an
// unrelated TypeError (undefined.length) masking the actual AC assertion.
const EMPTY_COUNTS = {
  total: 0,
  byStatus: {},
  byLevel: {},
  byPriority: {},
  byReadiness: {},
  byComponent: {},
};

const EMPTY_ATLAS: any = {
  generatedAt: new Date().toISOString(),
  acs: [],
  acComponents: [],
  tickets: [],
  components: [],
  roadmap: { currentPhase: "", currentOutcome: "", phases: [] },
  agents: [],
  acCounts: EMPTY_COUNTS,
  ticketCounts: { total: 0, byStatus: {}, byLifecycle: {} },
  backlog: { byBucket: {}, waterfall: [], buildableLeaves: 0 },
  nextUp: [],
  builtUnflipped: [],
  coverage: {
    totalAcs: 0,
    guarded: 0,
    guardedPct: 0,
    rolledUpGuarded: 0,
    histogram: [],
    byLevel: [],
    byComponent: [],
    totalTestFiles: 0,
  },
  traceability: {
    doneGuard: {
      total: 0,
      guarded: 0,
      unguarded: 0,
      pct: 0,
      leafTotal: 0,
      leafGuarded: 0,
      leafUnguarded: 0,
      leafPct: 0,
    },
    orphanTests: {
      files: 0,
      linkedFiles: 0,
      orphanFiles: 0,
      orphanFilePct: 0,
      orphanFileSamples: [],
      fns: 0,
      linkedFns: 0,
      orphanFns: 0,
      orphanFnPct: 0,
    },
    untracedCode: { scopes: [] },
    ticketsWithTraceability: 0,
    ticketsTotal: 0,
  },
  activity: { inProgress: [], inFlightEpics: [], telemetryAvailable: false },
};

const POPULATED_ATLAS: any = {
  ...EMPTY_ATLAS,
  acs: [{ id: "FAKE-1" }],
  acComponents: [{ id: "fake-component" }],
  tickets: [{ id: "T-1" }],
  components: [{ id: "fake-component" }],
  agents: [{ id: "fake-agent" }],
  nextUp: [{ id: "FAKE-2" }],
  roadmap: {
    currentPhase: "phase_1",
    currentOutcome: "fake outcome",
    phases: [{ id: "phase_1" }],
  },
};

async function callDriftGuard(opts: {
  mockActive: boolean;
  loaders?: "populated" | "empty";
  onGetAtlas?: () => void;
}) {
  vi.resetModules();
  const loaderMode = opts.loaders ?? "populated";

  vi.doMock("@/lib/data/mock", () => ({
    isMockActive: () => opts.mockActive,
    FIXTURE_ROOT: "/fake/fixture-root",
  }));

  vi.doMock("@/lib/data/atlas", () => ({
    getAtlas: () => {
      opts.onGetAtlas?.();
      return loaderMode === "empty" ? EMPTY_ATLAS : POPULATED_ATLAS;
    },
  }));

  vi.doMock("@/lib/data/flows", () => ({
    getFlows: () => (loaderMode === "empty" ? [] : [{ id: "fake/flow" }]),
    getMockData: () => (loaderMode === "empty" ? [] : [{ id: "fake/mock" }]),
    getScreenTitles: () =>
      loaderMode === "empty" ? {} : { "fake-screen": "Fake Screen" },
  }));

  const mod = await import("@/app/api/drift-guard/route");
  const request = new NextRequest("http://localhost/api/drift-guard");
  return mod.GET(request);
}

describe("UXP-609 — drift-guard asserts mock mode active BEFORE evaluating drift", () => {
  it("drift_guard_asserts_mock_active_before_drift", async () => {
    // covers: UXP-609
    // "it first asserts that mock mode is genuinely active … before it
    // evaluates drift" — when mock is NOT active, the drift loaders must
    // never run, and the result must never be reported clean (200).
    let atlasWasCalled = false;
    const response = await callDriftGuard({
      mockActive: false,
      onGetAtlas: () => {
        atlasWasCalled = true;
      },
    });
    expect(response.status).not.toBe(200);
    expect(atlasWasCalled).toBe(false);
  });
});

describe("UXP-609-1 — a mis-set environment fails loudly, never false-green", () => {
  it("mis_set_env_fails_with_named_reason", async () => {
    // covers: UXP-609-1
    const response = await callDriftGuard({ mockActive: false });
    expect(response.status).not.toBe(200);
    const body = (await response.text()).toLowerCase();
    // Must NAME the reason — mock mode not active — not just fail silently.
    expect(body).toMatch(/mock/);
    expect(body).toMatch(/not active|inactive|not.*genuinely active/);
  });
});

describe("UXP-609-2 — zero fixture records never produces a vacuous clean pass", () => {
  it("zero_fixture_records_fails_not_clean", async () => {
    // covers: UXP-609-2
    const response = await callDriftGuard({ mockActive: true, loaders: "empty" });
    expect(response.status).not.toBe(200);
    const body = (await response.text()).toLowerCase();
    expect(body).toMatch(/empty|zero|no (fixture|record)s?|absent/);
  });
});
