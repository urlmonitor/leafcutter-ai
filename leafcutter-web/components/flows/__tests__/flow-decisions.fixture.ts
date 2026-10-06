import type { AcRef, Flow } from "@/lib/data/types";

// ---------------------------------------------------------------------------
// Minimal Flow object for FlowExplorer tests.
// FlowExplorer reads: flow.steps, flow.branches, flow.scenarios,
// flow.realization, flow.implSummary (acDone, acTotal), flow.id.
// All fields use the processed (camelCase) FlowStep/FlowBranch shape.
// ---------------------------------------------------------------------------

function mkAcRef(id: string, status: "done" | "not_started"): AcRef {
  return { id, title: id, level: "L2", workStatus: status, resolved: true };
}

function mkFlowStep(id: string, order: number, implements_: string[], status: "done" | "not_started") {
  return {
    id,
    order,
    label: id,
    human: `${id}`,
    screen: null,
    agent: null,
    produces: [],
    consumes: [],
    reads: [],
    writes: [],
    implements: implements_,
    implStatus: status,
    fallbackStatus: status,
    acs: implements_.map((a) => mkAcRef(a, status)),
    expandsTo: null,
  };
}

/** A fully-typed Flow object that FlowExplorer can render without crashing. */
export const testFlow: Flow = {
  id: "test/deliver-a-feature",
  component: "build-pipeline",
  product: "Leafcutter",
  name: "Deliver a feature end-to-end",
  summary: "Test flow",
  kind: "user",
  source: "real",
  level: "journey",
  realization: "built",
  status: "active",
  readiness: "approved",
  entities: [],
  mockDataRef: null,
  steps: [
    mkFlowStep("plan", 1, ["UXP-550"], "done"),
    mkFlowStep("build", 2, ["UXP-551"], "done"),
    mkFlowStep("finalize", 3, ["UXP-552"], "done"),
  ],
  branches: [],
  scenarios: [],
  implSummary: {
    done: 3,
    in_progress: 0,
    not_started: 0,
    total: 3,
    asof: null,
    acDone: 3,
    acTotal: 3,
  },
  filePath: "/test/deliver-a-feature.flow.json",
};
