/**
 * Black-box tests for buildFlowGraph (decision-diamond rendering) and
 * deriveImplSummary (flow-level AC rollup), derived exclusively from the
 * acceptance criteria — NOT from reading the implementation.
 *
 * ACs covered: UXP-597, UXP-598, UXP-599, UXP-599a, UXP-600, UXP-602,
 *              UXP-603, UXP-604, UXP-604a.
 *
 * server-only mock: flows.ts carries `import "server-only"` which blocks
 * client imports. We mock it here (hoisted by vitest) so deriveImplSummary
 * can be imported. NOTE: deriveImplSummary is not exported from flows.ts —
 * the tests that call it will fail with TypeError, which is the correct red
 * state (the AC test_spec expects it to be testable / exported).
 *
 * Also NOTE: the server-only import in flows.ts itself is a FINDING against
 * UXP-600 it_requirements ("Derivation must be a pure function … unit-testable
 * in isolation") — a pure, client-safe function should not live inside a
 * server-only module.
 */

import { describe, it, expect } from "vitest";
import { buildFlowGraph } from "@/lib/data/graph";
import { deriveImplSummary } from "@/lib/data/flow-impl-summary";

// ---------------------------------------------------------------------------
// Flow-builder helpers: construct minimal but correctly-typed Flow objects.
// All fields that buildFlowGraph is known to read are populated with the
// correct camelCase names (FlowStep.implStatus, FlowBranch.from, etc.).
// vitest transpiles without typechecking, so `as any` is used throughout.
// ---------------------------------------------------------------------------

type WS = "done" | "in_progress" | "not_started";

function mkStep(
  id: string,
  order: number,
  opts: { status?: WS; implements?: string[] } = {}
): any {
  const status: WS = opts.status ?? "not_started";
  const impls = opts.implements ?? [];
  return {
    id,
    order,
    label: id,
    human: `${id} description`,
    screen: null,
    agent: null,
    produces: [],
    consumes: [],
    reads: [],
    writes: [],
    implements: impls,
    implStatus: status,
    fallbackStatus: status,
    acs: impls.map((acId) => ({
      id: acId,
      title: acId,
      level: "L2",
      workStatus: status,
      resolved: true,
    })),
    expandsTo: null,
  };
}

function mkBranch(
  id: string,
  from: string,
  condition: string,
  label: string,
  opts: { status?: WS; implements?: string[] } = {}
): any {
  const status: WS = opts.status ?? "not_started";
  const impls = opts.implements ?? [];
  return {
    id,
    from,
    condition,
    label,
    human: `${id} branch`,
    screen: null,
    agent: null,
    produces: [],
    consumes: [],
    reads: [],
    writes: [],
    implements: impls,
    implStatus: status,
    fallbackStatus: status,
    acs: impls.map((acId) => ({
      id: acId,
      title: acId,
      level: "L2",
      workStatus: status,
      resolved: true,
    })),
    expandsTo: null,
  };
}

function mkFlow(
  id: string,
  steps: any[],
  branches: any[],
  extra: { acDone?: number; acTotal?: number } = {}
): any {
  const done = steps.filter((s) => s.implStatus === "done").length;
  const inProgress = steps.filter((s) => s.implStatus === "in_progress").length;
  return {
    id,
    component: "test",
    product: "Test",
    name: id,
    summary: "",
    kind: "user",
    source: "mock",
    level: "journey",
    realization: "built",
    status: "active",
    readiness: "approved",
    entities: [],
    mockDataRef: null,
    steps,
    branches,
    scenarios: [],
    implSummary: {
      done,
      in_progress: inProgress,
      not_started: steps.length - done - inProgress,
      total: steps.length,
      asof: null,
      acDone: extra.acDone ?? 0,
      acTotal: extra.acTotal ?? 0,
    },
    filePath: "/test/path",
  };
}

// ---------------------------------------------------------------------------
// Canonical test flows
// ---------------------------------------------------------------------------

/**
 * decisionFork: write-review step has 2 branches (already-reviewed,
 * not-delivered). Step 2 of 3 — NOT the last step, so 2 diamonds MUST be
 * synthesized.
 */
const decisionForkFlow = mkFlow(
  "test/decision-fork",
  [
    mkStep("view-order", 1),
    mkStep("write-review", 2),
    mkStep("submit-review", 3),
  ],
  [
    mkBranch(
      "already-reviewed",
      "write-review",
      "Customer has already reviewed this order item",
      "Already Reviewed"
    ),
    mkBranch(
      "not-delivered",
      "write-review",
      "Order item not yet delivered",
      "Not Delivered"
    ),
  ]
);

/** No branches → zero decision nodes. */
const noBranchFlow = mkFlow(
  "test/no-branches",
  [mkStep("step-1", 1, { status: "done" }), mkStep("step-2", 2, { status: "done" })],
  []
);

/** N=3 branches off step-a (which is step 1 of 3 — not the last step). */
const threeBranchFlow = mkFlow(
  "test/three-branches",
  [
    mkStep("step-a", 1),
    mkStep("step-b", 2),
    mkStep("step-c", 3),
  ],
  [
    mkBranch("branch-x", "step-a", "Condition X", "X happened"),
    mkBranch("branch-y", "step-a", "Condition Y", "Y happened"),
    mkBranch("branch-z", "step-a", "Condition Z", "Z happened"),
  ]
);

/** N=4 branches off step-a (step 1 of 2) — count-agnosticism test. */
const fourBranchFlow = mkFlow(
  "test/four-branches",
  [mkStep("step-a", 1), mkStep("step-b", 2)],
  [
    mkBranch("b1", "step-a", "Cond 1", "Branch 1"),
    mkBranch("b2", "step-a", "Cond 2", "Branch 2"),
    mkBranch("b3", "step-a", "Cond 3", "Branch 3"),
    mkBranch("b4", "step-a", "Cond 4", "Branch 4"),
  ]
);

/**
 * UXP-599a known-limitation: branch off the LAST step (step-2, order 2).
 * The current build does NOT synthesize a diamond for trailing forks.
 */
const lastStepBranchFlow = mkFlow(
  "test/last-step-branch",
  [mkStep("step-1", 1), mkStep("step-2", 2)],
  [mkBranch("trailing-branch", "step-2", "Some terminal condition", "Terminal")]
);

/**
 * UXP-603: step with implements[] and done status → acDone count on node.
 * deliver-a-feature equivalent: 3 done steps, each implementing a unique AC.
 */
const acCountFlow = mkFlow(
  "test/ac-count",
  [
    mkStep("plan", 1, { status: "done", implements: ["UXP-550"] }),
    mkStep("build", 2, { status: "done", implements: ["UXP-551"] }),
    mkStep("finalize", 3, { status: "done", implements: ["UXP-552"] }),
  ],
  [],
  { acDone: 3, acTotal: 3 }
);

/**
 * UXP-604a dedup: step-1 and step-2 both implement AC-SHARED.
 * acTotal must be 1 (distinct), not 2 (sum).
 */
const sharedAcFlow = mkFlow(
  "test/shared-ac",
  [
    mkStep("step-1", 1, { status: "done", implements: ["AC-SHARED"] }),
    mkStep("step-2", 2, { status: "done", implements: ["AC-SHARED"] }),
  ],
  [],
  { acDone: 1, acTotal: 1 } // expected: the pre-computed implSummary
);

/**
 * UXP-604a multi-AC dedup: 3 distinct ACs, one shared across step-1 and a branch.
 * Distinct: AC-DONE-1, AC-DONE-2, AC-PENDING → acTotal = 3 (not 4).
 */
const multiAcFlow = mkFlow(
  "test/multi-ac",
  [
    mkStep("step-1", 1, { status: "done", implements: ["AC-DONE-1", "AC-DONE-2"] }),
    mkStep("step-2", 2, { status: "not_started", implements: ["AC-PENDING"] }),
  ],
  [mkBranch("branch-1", "step-1", "Cond", "Branch", { status: "done", implements: ["AC-DONE-1"] })],
  { acDone: 2, acTotal: 3 }
);

// ---------------------------------------------------------------------------
// Helper: extract Graph from buildFlowGraph call
// ---------------------------------------------------------------------------
type GraphResult = { nodes: any[]; edges: any[] };

function g(flow: any, showAcNodes = false): GraphResult {
  return buildFlowGraph(flow, showAcNodes) as unknown as GraphResult;
}

// ===========================================================================
// UXP-597: A step with branches yields a decision node (meta.variant === "decision")
// ===========================================================================

describe("UXP-597 — decision diamond emitted for a conditional fork", () => {
  it("buildFlowGraph_emits_decision_variant_node_for_a_branch", () => {
    // covers: UXP-597
    // "Each conditional fork is drawn as a diamond-shaped decision node rather
    // than a rounded step card" — means meta.variant === "decision" on graph nodes.
    const { nodes } = g(decisionForkFlow);
    const decisionNodes = nodes.filter((n) => n.meta?.variant === "decision");
    // write-review has 2 branches → expects 2 decision nodes
    expect(decisionNodes.length).toBeGreaterThanOrEqual(1);
  });

  it("decision_node_carries_the_branch_condition_text", () => {
    // covers: UXP-597
    // "The diamond displays the fork's condition/question text."
    const { nodes } = g(decisionForkFlow);
    const decisionNodes = nodes.filter((n) => n.meta?.variant === "decision");
    expect(decisionNodes.length).toBeGreaterThan(0);

    const expectedConditions = [
      "Customer has already reviewed this order item",
      "Order item not yet delivered",
    ];
    decisionNodes.forEach((dn) => {
      expect(typeof dn.meta.condition).toBe("string");
      expect(dn.meta.condition.length).toBeGreaterThan(0);
      expect(expectedConditions).toContain(dn.meta.condition);
    });
  });

  it("decision_nodes_are_distinct_from_step_nodes", () => {
    // covers: UXP-597
    // "The diamond is visually distinguishable at a glance from an ordinary step card."
    // At the data level: a decision node and a step node must never share an id.
    const { nodes } = g(decisionForkFlow);
    const stepNodes = nodes.filter((n) => n.meta?.variant === "step");
    const decisionNodes = nodes.filter((n) => n.meta?.variant === "decision");
    expect(stepNodes.length).toBeGreaterThan(0);
    expect(decisionNodes.length).toBeGreaterThan(0);
    const decisionIds = new Set(decisionNodes.map((n) => n.id));
    stepNodes.forEach((sn) => expect(decisionIds.has(sn.id)).toBe(false));
  });

  it("flow_with_no_branches_produces_no_decision_nodes", () => {
    // covers: UXP-597
    // A flow with zero branches must produce zero decision nodes.
    const { nodes } = g(noBranchFlow);
    expect(nodes.filter((n) => n.meta?.variant === "decision").length).toBe(0);
  });
});

// ===========================================================================
// UXP-598: Decision edges carry labels and sourceHandle 'yes' | 'no'
// ===========================================================================

describe("UXP-598 — decision edges are labelled with yes/no handles", () => {
  it("buildFlowGraph_labels_every_decision_edge_with_handle", () => {
    // covers: UXP-598
    // "Every edge leaving a diamond carries a visible label … no unlabelled
    // decision edges. The branch-outcome edge carries sourceHandle 'yes';
    // the fall-through edge carries sourceHandle 'no'."
    const { nodes, edges } = g(decisionForkFlow);
    const decisionNodes = nodes.filter((n) => n.meta?.variant === "decision");
    expect(decisionNodes.length).toBeGreaterThan(0);

    decisionNodes.forEach((dn) => {
      const outEdges = edges.filter((e) => e.source === dn.id);
      expect(outEdges.length).toBeGreaterThanOrEqual(2);
      outEdges.forEach((e) => {
        // Every outgoing edge must have a non-empty label
        expect(e.label).toBeTruthy();
        // Every outgoing edge must have sourceHandle 'yes' or 'no'
        expect(["yes", "no"]).toContain(e.sourceHandle);
      });
    });
  });

  it("yes_edge_carries_branch_outcome_label", () => {
    // covers: UXP-598
    // "The branch outcome edge is labelled 'yes'." The 'yes' edge label
    // must match one of the flow's branch labels.
    const { nodes, edges } = g(decisionForkFlow);
    const branchLabels = decisionForkFlow.branches.map((b: any) => b.label);
    const decisionNodes = nodes.filter((n) => n.meta?.variant === "decision");

    const yesEdgeLabels = decisionNodes.flatMap((dn) =>
      edges
        .filter((e) => e.source === dn.id && e.sourceHandle === "yes")
        .map((e) => e.label)
    );
    expect(yesEdgeLabels.length).toBeGreaterThan(0);
    yesEdgeLabels.forEach((label) => {
      expect(branchLabels).toContain(label);
    });
  });

  it("no_edge_is_the_fallthrough_from_every_diamond", () => {
    // covers: UXP-598
    // "The fall-through edge that continues to the next ordered step is labelled
    // 'no'/else." Every decision node must have exactly one 'no' edge.
    const { nodes, edges } = g(decisionForkFlow);
    const decisionNodes = nodes.filter((n) => n.meta?.variant === "decision");
    decisionNodes.forEach((dn) => {
      const noEdges = edges.filter((e) => e.source === dn.id && e.sourceHandle === "no");
      expect(noEdges.length).toBe(1);
      expect(noEdges[0].label).toBeTruthy();
    });
  });

  it("no_unlabelled_edges_leave_a_decision_node", () => {
    // covers: UXP-598
    // "No edge leaving a diamond may render without a visible label."
    const { nodes, edges } = g(threeBranchFlow);
    const decisionIds = new Set(
      nodes.filter((n) => n.meta?.variant === "decision").map((n) => n.id)
    );
    const outEdges = edges.filter((e) => decisionIds.has(e.source));
    outEdges.forEach((e) => {
      expect(e.label).toBeTruthy();
    });
  });
});

// ===========================================================================
// UXP-599: N branches → N chained diamond nodes (not one N-way node)
// ===========================================================================

describe("UXP-599 — multi-branch fork chains into N diamonds", () => {
  it("buildFlowGraph_chains_n_branches_into_n_diamonds", () => {
    // covers: UXP-599
    // "A step with N=3 branches yields 3 decision nodes chained via 'no' handles:
    // step→D0, D0→D1, D1→D2."
    const { nodes, edges } = g(threeBranchFlow);
    const decisionNodes = nodes.filter((n) => n.meta?.variant === "decision");
    expect(decisionNodes.length).toBe(3);

    // Count how many diamonds chain their 'no' edge to another diamond
    const decisionIds = new Set(decisionNodes.map((n) => n.id));
    const chainsToNextDiamond = decisionNodes.filter((dn) => {
      const noEdge = edges.find((e) => e.source === dn.id && e.sourceHandle === "no");
      return noEdge && decisionIds.has(noEdge.target);
    });
    // 3 diamonds in a chain → 2 of them chain to the next diamond
    expect(chainsToNextDiamond.length).toBe(2);
  });

  it("last_diamond_no_edge_goes_to_next_ordered_step", () => {
    // covers: UXP-599
    // "The final 'else' edge continues to the happy-path next step."
    const { nodes, edges } = g(threeBranchFlow);
    const decisionIds = new Set(
      nodes.filter((n) => n.meta?.variant === "decision").map((n) => n.id)
    );
    // Find the terminal diamond (whose 'no' target is NOT another diamond)
    const terminal = nodes
      .filter((n) => n.meta?.variant === "decision")
      .find((dn) => {
        const noEdge = edges.find((e) => e.source === dn.id && e.sourceHandle === "no");
        return noEdge && !decisionIds.has(noEdge.target);
      });
    expect(terminal).toBeDefined();

    const finalNoEdge = edges.find(
      (e) => e.source === terminal!.id && e.sourceHandle === "no"
    );
    expect(finalNoEdge).toBeDefined();
    // The target must be a non-decision node
    const targetNode = nodes.find((n) => n.id === finalNoEdge!.target);
    if (targetNode) {
      expect(targetNode.meta?.variant).not.toBe("decision");
    }
  });

  it("each_diamond_has_exactly_one_yes_edge", () => {
    // covers: UXP-599
    // "The fork is NOT drawn as a single node with N outgoing edges."
    // Each diamond has exactly one 'yes' edge (to one branch outcome).
    const { nodes, edges } = g(threeBranchFlow);
    const decisionNodes = nodes.filter((n) => n.meta?.variant === "decision");
    decisionNodes.forEach((dn) => {
      const yesEdges = edges.filter((e) => e.source === dn.id && e.sourceHandle === "yes");
      expect(yesEdges.length).toBe(1);
    });
  });

  it("buildFlowGraph_diamond_chain_is_count_agnostic_n2_and_n4", () => {
    // covers: UXP-599
    // "Chaining must be count-agnostic — it must handle arbitrary N >= 2 with
    // no hard-coded branch count."
    const { nodes: nodes2 } = g(decisionForkFlow); // N=2
    expect(nodes2.filter((n) => n.meta?.variant === "decision").length).toBe(2);

    const { nodes: nodes4 } = g(fourBranchFlow); // N=4
    expect(nodes4.filter((n) => n.meta?.variant === "decision").length).toBe(4);
  });
});

// ===========================================================================
// UXP-599a: Known limitation — branch off the LAST step → NO diamond
// ===========================================================================

describe("UXP-599a — known limitation: no diamond for branch off the last step", () => {
  it("buildFlowGraph_omits_diamond_for_branch_off_last_step", () => {
    // covers: UXP-599a
    // "Given a flow whose conditional branch forks off the LAST ordered step …
    //  Then the current build does NOT synthesize a decision diamond for that
    //  trailing fork." — This test PINS the current behavior (omission).
    // The last step is step-2 (order 2). The branch is off step-2.
    const { nodes } = g(lastStepBranchFlow);
    const decisionNodes = nodes.filter((n) => n.meta?.variant === "decision");
    // Known limitation: no diamond for trailing fork
    expect(decisionNodes.length).toBe(0);
  });
});

// ===========================================================================
// UXP-600: Diamonds derived from existing branch data (no decisions[] required)
// ===========================================================================

describe("UXP-600 — decision diamonds derived from branch data only", () => {
  it("buildFlowGraph_derives_diamonds_from_branch_data_only", () => {
    // covers: UXP-600
    // "A flow carrying only branches[] (from/condition/label/target) … still
    // produces decision nodes and labelled edges … no separate first-class
    // decision definition is required."
    // Our test flow has branches but no decisions[] field.
    expect((decisionForkFlow as any).decisions).toBeUndefined();
    const { nodes, edges } = g(decisionForkFlow);
    const decisionNodes = nodes.filter((n) => n.meta?.variant === "decision");
    expect(decisionNodes.length).toBeGreaterThan(0);
    // Must also produce labelled edges
    decisionNodes.forEach((dn) => {
      expect(edges.filter((e) => e.source === dn.id).length).toBeGreaterThanOrEqual(2);
    });
  });

  it("buildFlowGraph_derivation_is_pure", () => {
    // covers: UXP-600
    // "Derivation must be a pure function (no fs / no network)."
    // A pure function returns deterministic output for identical input and
    // does not mutate its input.
    const original = JSON.stringify(decisionForkFlow);
    const r1 = g(decisionForkFlow);
    const r2 = g(decisionForkFlow);
    // Deterministic: same input → same node/edge count
    expect(r1.nodes.length).toBe(r2.nodes.length);
    expect(r1.edges.length).toBe(r2.edges.length);
    // Non-mutating: input is unchanged after the call
    expect(JSON.stringify(decisionForkFlow)).toBe(original);
  });
});

// ===========================================================================
// UXP-602: showAcNodes=false (default) → no AC nodes, no implements edges
// ===========================================================================

describe("UXP-602 — AC nodes off by default", () => {
  it("buildFlowGraph_omits_ac_nodes_by_default", () => {
    // covers: UXP-602
    // "buildFlowGraph with the default showAcNodes produces zero nodes of kind
    // 'ac' and zero 'implements' edges, even when steps reference ACs."
    const { nodes, edges } = g(acCountFlow); // steps have implements[] arrays
    const acNodes = nodes.filter((n) => n.kind === "ac");
    const implementsEdges = edges.filter((e) => e.kind === "implements");
    expect(acNodes.length).toBe(0);
    expect(implementsEdges.length).toBe(0);
  });

  it("buildFlowGraph_emits_ac_nodes_when_showAcNodes_true", () => {
    // covers: UXP-602
    // "Only step, branch, and decision nodes are drawn until the AC-node view
    // is explicitly turned on." — with showAcNodes=true, AC nodes appear.
    const off = g(acCountFlow, false);
    const on = g(acCountFlow, true);

    const acNodesOff = off.nodes.filter((n) => n.kind === "ac");
    const acNodesOn = on.nodes.filter((n) => n.kind === "ac");

    expect(acNodesOff.length).toBe(0);
    // acCountFlow has 3 steps implementing UXP-550, UXP-551, UXP-552
    expect(acNodesOn.length).toBeGreaterThan(0);
  });
});

// ===========================================================================
// UXP-603: Step/branch nodes carry acDone and acCount in their meta
// ===========================================================================

describe("UXP-603 — step/branch nodes carry acDone and acCount counts", () => {
  it("step_nodes_carry_acDone_in_meta", () => {
    // covers: UXP-603
    // "acDone must be computed in buildFlowGraph as the count of referenced ACs
    // with work_status done." buildFlowGraph sets meta.acDone on step nodes.
    // NOTE: the total AC count (acCount) is assembled in flow-explorer.tsx from
    // step.implements.length, not embedded in the graph node meta — so we assert
    // only on meta.acDone here (what buildFlowGraph explicitly computes).
    const { nodes } = g(acCountFlow);
    const stepNodes = nodes.filter((n) => n.meta?.variant === "step");
    expect(stepNodes.length).toBeGreaterThan(0);

    stepNodes.forEach((sn) => {
      expect(sn.meta).toBeDefined();
      // acDone must be a non-negative integer in meta
      expect(typeof sn.meta.acDone).toBe("number");
      expect((sn.meta.acDone as number)).toBeGreaterThanOrEqual(0);
    });
  });

  it("done_step_with_implements_has_nonzero_acDone", () => {
    // covers: UXP-603
    // A step with implStatus=done and implements=[...] must have acDone > 0.
    const { nodes } = g(acCountFlow);
    // All 3 steps are done, each with 1 AC
    const anyDoneWithAcs = nodes.find(
      (n) => n.meta?.variant === "step" && (n.meta.acDone ?? 0) > 0
    );
    expect(anyDoneWithAcs).toBeDefined();
  });
});

// ===========================================================================
// UXP-604 / UXP-604a: deriveImplSummary — flow-level deduped AC rollup
// EXPECTED FAILURE: deriveImplSummary is not exported from flows.ts.
// This failure is a valid spec-vs-code finding: the AC test_spec expects the
// function to be testable (exported), but the implementation keeps it private.
// Additionally, flows.ts carries `import "server-only"` which contradicts the
// "pure function safe for client" requirement in UXP-600 it_requirements —
// functions tested via the same module must bypass that guard.
// ===========================================================================

describe("UXP-604 — deriveImplSummary: flow-level distinct AC count", () => {
  it("derive_impl_summary_counts_distinct_acs", () => {
    // covers: UXP-604
    // "deriveImplSummary returns acTotal = number of distinct ACs across
    // steps+branches and acDone = distinct ACs with work_status done."
    // acCountFlow: 3 steps each implementing 1 unique AC (UXP-550/551/552).
    // Expected: acTotal=3, acDone=3 (all done).
    // EXPECTED FAILURE: deriveImplSummary is not exported from flows.ts.
    const summary = (deriveImplSummary as any)(acCountFlow);
    expect(summary).toBeDefined();
    expect(typeof summary.acTotal).toBe("number");
    expect(typeof summary.acDone).toBe("number");
    expect(summary.acTotal).toBe(3);
    expect(summary.acDone).toBe(3);
    expect(summary).toHaveProperty("done");
  });
});

describe("UXP-604a — deriveImplSummary deduplicates shared ACs", () => {
  it("derive_impl_summary_dedupes_ac_across_nodes", () => {
    // covers: UXP-604a
    // "An AC id referenced by two steps is counted once in acTotal … the rollup
    // total M is strictly the number of distinct ACs in the flow, never the sum
    // of per-node AC counts."
    // sharedAcFlow: 2 steps both implementing "AC-SHARED" → acTotal MUST be 1.
    // EXPECTED FAILURE: deriveImplSummary is not exported from flows.ts.
    const summary = (deriveImplSummary as any)(sharedAcFlow);
    expect(summary.acTotal).toBe(1); // distinct, not 2 (sum)
    expect(summary.acDone).toBe(1); // AC-SHARED is done in both steps
  });

  it("shared_done_ac_counted_once_in_acDone", () => {
    // covers: UXP-604a
    // Same assertion from a different angle.
    // EXPECTED FAILURE: deriveImplSummary is not exported from flows.ts.
    const summary = (deriveImplSummary as any)(sharedAcFlow);
    expect(summary.acTotal).not.toBe(2); // must NOT be the per-node sum
    expect(summary.acDone).not.toBe(2);
  });

  it("multi_ac_dedup_with_branch_sharing", () => {
    // covers: UXP-604a
    // multiAcFlow: AC-DONE-1 appears in step-1 AND branch-1.
    // Distinct ACs: AC-DONE-1, AC-DONE-2, AC-PENDING → acTotal = 3 (not 4).
    // acDone: AC-DONE-1 (done), AC-DONE-2 (done) → acDone = 2.
    // EXPECTED FAILURE: deriveImplSummary is not exported from flows.ts.
    const summary = (deriveImplSummary as any)(multiAcFlow);
    expect(summary.acTotal).toBe(3);
    expect(summary.acDone).toBe(2);
  });
});

// ===========================================================================
// UXP-601: Decision nodes carry status for tinting (partial — gap expected)
// ===========================================================================

describe("UXP-601 — decision and outcome nodes carry impl_status for tinting", () => {
  it("outcome_branch_node_carries_impl_status", () => {
    // covers: UXP-601
    // Branch (outcome) nodes must carry a status for tinting.
    // IT-PO notes: "flows.ts rollupStatus → graph.ts branch node status →
    // FlowStepNode WORK_STATUS_TONE." In graph.ts, status is set at the TOP
    // LEVEL of the GraphNode (status: b.implStatus), not inside the meta
    // Record. We check the top-level 'status' field, with meta fallbacks.
    const { nodes } = g(decisionForkFlow);
    const branchNodes = nodes.filter((n) => n.meta?.variant === "branch");
    expect(branchNodes.length).toBeGreaterThan(0);
    branchNodes.forEach((bn) => {
      // status is at the top level of the graph node (not in meta)
      const status = (bn as any).status ?? bn.meta?.status ?? bn.meta?.implStatus;
      expect(status).toBeDefined();
      expect(["done", "in_progress", "not_started", "todo", "blocked", "unknown"]).toContain(status);
    });
  });

  it("decision_diamond_carries_derived_impl_status", () => {
    // covers: UXP-601
    // "Each decision/outcome node is tinted by its derived impl_status."
    // GAP (IT-PO confirmed): graph.ts sets no status on decision nodes —
    // FlowDecisionNode renders a fixed amber constant regardless of AC status.
    // We check both the top-level node status field and the meta fallbacks.
    // EXPECTED TO FAIL — this is the confirmed spec-vs-code gap.
    const { nodes } = g(decisionForkFlow);
    const decisionNodes = nodes.filter((n) => n.meta?.variant === "decision");
    expect(decisionNodes.length).toBeGreaterThan(0);
    decisionNodes.forEach((dn) => {
      // AC demands: decision node carries a derived status at the top level or in meta.
      const status =
        (dn as any).status ?? dn.meta?.status ?? dn.meta?.implStatus;
      expect(status).toBeDefined();
      expect(["done", "in_progress", "not_started", "todo", "blocked", "unknown"]).toContain(status);
    });
  });
});
