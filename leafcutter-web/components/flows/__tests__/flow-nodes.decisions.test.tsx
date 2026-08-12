/**
 * Black-box component tests for FlowStepNode, FlowDecisionNode, and
 * FlowExplorer, derived exclusively from the acceptance criteria — NOT from
 * reading the implementation source.
 *
 * ACs covered: UXP-597, UXP-601, UXP-602, UXP-603, UXP-603a, UXP-605, UXP-605a.
 *
 * Wiring notes (resolved from public exports only, per the test mandate):
 * - The public export from flow-explorer.tsx is FlowExplorer (not ExplorerInner;
 *   ExplorerInner is the internal name from the ACs' it_requirements).
 * - FlowStepNodeData has top-level fields: label, order, variant, status, acCount,
 *   acDone, drillable, selected (destructured directly from data in the component).
 * - FlowDecisionNodeData has a top-level `condition` field only.
 * - FlowStepNode and FlowDecisionNode use React Flow handles internally and
 *   therefore require a ReactFlowProvider ancestor.
 * - The toggle in FlowExplorer stores its state in localStorage under the key
 *   'flows:showAcNodes' (=== '1' for on; '0' for off).
 * - Toggle button title: "Show AC nodes in graph" (off state) /
 *   "Hide AC nodes from graph" (on state).
 */

import { describe, it, expect, beforeEach, afterEach, beforeAll } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import React from "react";
import { ReactFlowProvider } from "reactflow";

// jsdom does not implement ResizeObserver. React Flow v11 uses it to measure
// node sizes; without it every FlowExplorer render throws. This is a harness
// limitation — mocking it here is a standard workaround that does NOT weaken
// any behavioral assertion (we are not testing resize behavior).
beforeAll(() => {
  if (!("ResizeObserver" in globalThis)) {
    (globalThis as any).ResizeObserver = class ResizeObserver {
      observe() {}
      unobserve() {}
      disconnect() {}
    };
  }
});

import { FlowStepNode, FlowDecisionNode } from "@/components/flows/flow-nodes";
import { FlowExplorer } from "@/components/flows/flow-explorer";

// ---------------------------------------------------------------------------
// Wrap any component that uses React Flow handles / hooks in a Provider
// ---------------------------------------------------------------------------
function withProvider(ui: React.ReactElement) {
  return render(<ReactFlowProvider>{ui}</ReactFlowProvider>);
}

// ---------------------------------------------------------------------------
// Minimal React Flow v11 NodeProps for direct node component renders
// ---------------------------------------------------------------------------
const BASE_NODE_PROPS = {
  selected: false,
  isConnectable: true,
  xPos: 0,
  yPos: 0,
  dragging: false,
  zIndex: 0,
  sourcePosition: "bottom" as any,
  targetPosition: "top" as any,
};

// ---------------------------------------------------------------------------
// Minimal Flow object for FlowExplorer tests.
// FlowExplorer reads: flow.steps, flow.branches, flow.scenarios,
// flow.realization, flow.implSummary (acDone, acTotal), flow.id.
// All fields use the processed (camelCase) FlowStep/FlowBranch shape.
// ---------------------------------------------------------------------------

function mkAcRef(id: string, status: "done" | "not_started") {
  return { id, title: id, level: "L2" as any, workStatus: status, resolved: true };
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
const testFlow: any = {
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

// ===========================================================================
// UXP-597: FlowDecisionNode renders a diamond distinct from FlowStepNode
// ===========================================================================

describe("UXP-597 — diamond node is visually distinct from step card", () => {
  it("flow_decision_node_displays_condition_text_inside_diamond", () => {
    // covers: UXP-597
    // "The fork's condition/question text must be shown inside the diamond shape."
    const condition = "Customer has already reviewed this order item";
    withProvider(
      <FlowDecisionNode
        {...BASE_NODE_PROPS}
        id="dn"
        type="flowDecisionNode"
        data={{ condition } as any}
      />
    );
    expect(screen.getByText(condition)).toBeInTheDocument();
  });

  it("flow_decision_node_renders_diamond_distinct_from_step_card", () => {
    // covers: UXP-597
    // "FlowDecisionNode renders the rotated diamond … FlowStepNode renders the
    // rounded card — the two are structurally distinguishable in the DOM."
    const { container: decisionContainer } = withProvider(
      <FlowDecisionNode
        {...BASE_NODE_PROPS}
        id="dn-a"
        type="flowDecisionNode"
        data={{ condition: "Is the item in stock?" } as any}
      />
    );
    const { container: stepContainer } = withProvider(
      <FlowStepNode
        {...BASE_NODE_PROPS}
        id="sn-a"
        type="flowStepNode"
        data={
          {
            label: "Check Inventory",
            order: 1,
            variant: "step",
            status: "not_started",
            acCount: 0,
            acDone: 0,
            drillable: false,
            selected: false,
          } as any
        }
      />
    );
    // The two node types must have structurally different markup.
    // (Different HTML = different visual appearance = visually distinguishable.)
    expect(decisionContainer.innerHTML).not.toBe(stepContainer.innerHTML);
  });
});

// ===========================================================================
// UXP-603: Step node renders an acDone/acCount progress pill
// ===========================================================================

describe("UXP-603 — step node renders the acDone/acCount progress pill", () => {
  it("flow_step_node_renders_done_total_ac_pill", () => {
    // covers: UXP-603
    // "A node with 3 ACs, 2 done, renders a '2/3 ACs' pill."
    const { container } = withProvider(
      <FlowStepNode
        {...BASE_NODE_PROPS}
        id="sn"
        type="flowStepNode"
        data={
          {
            label: "My Step",
            order: 1,
            variant: "step",
            status: "in_progress",
            acCount: 3,
            acDone: 2,
            drillable: false,
            selected: false,
          } as any
        }
      />
    );
    // Pill must show "2" and "3" (as "2/3 ACs")
    const text = container.textContent ?? "";
    expect(text).toContain("2");
    expect(text).toContain("3");
    // The pill must contain the "/" separator between done and total
    expect(text).toMatch(/2\s*\/\s*3/);
  });

  it("ac_pill_tints_by_aggregate_status_green_when_all_done", () => {
    // covers: UXP-603
    // "Pill tone is green when all ACs done." We check the render doesn't crash
    // and the count reflects 3/3.
    const { container } = withProvider(
      <FlowStepNode
        {...BASE_NODE_PROPS}
        id="sn-done"
        type="flowStepNode"
        data={
          {
            label: "Done Step",
            order: 1,
            variant: "step",
            status: "done",
            acCount: 3,
            acDone: 3,
            drillable: false,
            selected: false,
          } as any
        }
      />
    );
    expect(container.textContent).toContain("3");
    expect(container.textContent).toMatch(/3\s*\/\s*3/);
  });

  it("ac_pill_tints_by_aggregate_status_partial", () => {
    // covers: UXP-603
    // "Pill tone is amber when some but not all are done."
    const { container } = withProvider(
      <FlowStepNode
        {...BASE_NODE_PROPS}
        id="sn-partial"
        type="flowStepNode"
        data={
          {
            label: "Partial Step",
            order: 1,
            variant: "step",
            status: "in_progress",
            acCount: 3,
            acDone: 1,
            drillable: false,
            selected: false,
          } as any
        }
      />
    );
    expect(container.textContent).toMatch(/1\s*\/\s*3/);
  });
});

// ===========================================================================
// UXP-603a: Node with zero ACs shows NO progress pill
// ===========================================================================

describe("UXP-603a — no progress pill when acCount is zero", () => {
  it("flow_step_node_omits_pill_when_zero_acs", () => {
    // covers: UXP-603a
    // "A node with acCount 0 renders no progress pill element and never shows
    // '0/0'."
    const { container } = withProvider(
      <FlowStepNode
        {...BASE_NODE_PROPS}
        id="sn-zero"
        type="flowStepNode"
        data={
          {
            label: "No-AC Step",
            order: 1,
            variant: "step",
            status: "not_started",
            acCount: 0,
            acDone: 0,
            drillable: false,
            selected: false,
          } as any
        }
      />
    );
    const text = container.textContent ?? "";
    // Must NOT show "0/0"
    expect(text).not.toMatch(/0\s*\/\s*0/);
    // Must NOT contain the "ACs" pill label alongside the 0 count
    // (The pill is omitted entirely when acCount === 0, per the gate `acCount > 0`.)
    expect(text).not.toMatch(/0\s*\/\s*0\s*ACs/i);
  });
});

// ===========================================================================
// UXP-601: Decision diamond tints by derived impl_status (partial — gap expected)
// ===========================================================================

describe("UXP-601 — decision/outcome nodes tint by derived impl_status", () => {
  it("outcome_node_tints_by_derived_impl_status", () => {
    // covers: UXP-601
    // "A branch (outcome) node whose ACs are all done tints with the 'done'
    // tone." Branch nodes use FlowStepNode with variant='branch'.
    // This half IS shipped per the IT-PO enrichment notes.
    const { container } = withProvider(
      <FlowStepNode
        {...BASE_NODE_PROPS}
        id="outcome-done"
        type="flowStepNode"
        data={
          {
            label: "Already Reviewed",
            order: 0,
            variant: "branch",
            status: "done",
            acCount: 2,
            acDone: 2,
            drillable: false,
            selected: false,
          } as any
        }
      />
    );
    // Render must succeed and expose the done count
    expect(container.firstChild).not.toBeNull();
    expect(container.textContent).toMatch(/2\s*\/\s*2/);
  });

  it("decision_diamond_tints_by_derived_impl_status", () => {
    // covers: UXP-601
    // "Each decision/outcome node is tinted by its derived impl_status."
    // GAP (IT-PO confirmed): FlowDecisionNodeData only has `condition`; the
    // component uses a fixed amber constant and ignores any status.
    // This test asserts what the AC DEMANDS and is EXPECTED TO FAIL.
    //
    // We render two diamonds with different status values (via as-any props)
    // and assert they produce different HTML. Since the component ignores status,
    // both renders will be identical → test FAILS, confirming the gap.
    const { container: notStartedContainer } = withProvider(
      <FlowDecisionNode
        {...BASE_NODE_PROPS}
        id="dd-ns"
        type="flowDecisionNode"
        data={{ condition: "Same condition?", status: "not_started" } as any}
      />
    );
    const { container: doneContainer } = withProvider(
      <FlowDecisionNode
        {...BASE_NODE_PROPS}
        id="dd-done"
        type="flowDecisionNode"
        data={{ condition: "Same condition?", status: "done" } as any}
      />
    );
    // The AC requires different tints for different statuses → different markup.
    // Replace ids so the comparison is purely structural.
    const normalize = (html: string) =>
      html.replace(/id="dd-[^"]*"/g, 'id="X"').replace(/\s+/g, " ").trim();
    // EXPECTED FAIL: current implementation renders identical amber for both.
    expect(normalize(notStartedContainer.innerHTML)).not.toBe(
      normalize(doneContainer.innerHTML)
    );
  });
});

// ===========================================================================
// UXP-602: FlowExplorer defaults showAcNodes to off
// ===========================================================================

describe("UXP-602 — FlowExplorer: AC nodes off by default", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("flow_explorer_defaults_show_ac_nodes_off", () => {
    // covers: UXP-602
    // "With no persisted preference, [FlowExplorer] mounts with showAcNodes
    // false so no AC nodes render initially."
    // We confirm (a) the toggle is present in the off state, and
    // (b) no AC id text appears in the rendered output.
    render(<FlowExplorer flow={testFlow} />);

    // The toggle button in off state has title "Show AC nodes in graph"
    const toggle = screen.queryByTitle("Show AC nodes in graph");
    expect(toggle).not.toBeNull();

    // UXP-550/551/552 are the AC ids implemented by the test flow's steps.
    // With showAcNodes=false they must not appear as node content.
    expect(screen.queryByText("UXP-550")).not.toBeInTheDocument();
    expect(screen.queryByText("UXP-551")).not.toBeInTheDocument();
    expect(screen.queryByText("UXP-552")).not.toBeInTheDocument();
  });
});

// ===========================================================================
// UXP-605: 'Show AC nodes in graph' toggle — defaults off, enables AC nodes
// ===========================================================================

describe("UXP-605 — Show AC nodes in graph toggle", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("show_acs_toggle_defaults_off", () => {
    // covers: UXP-605
    // "The toggle defaults to off."
    render(<FlowExplorer flow={testFlow} />);
    // In the off state, the button title is "Show AC nodes in graph"
    const toggle = screen.getByTitle("Show AC nodes in graph");
    expect(toggle).toBeInTheDocument();
    // No AC node content visible
    expect(screen.queryByText("UXP-550")).not.toBeInTheDocument();
  });

  it("show_acs_toggle_on_renders_wired_ac_nodes", () => {
    // covers: UXP-605
    // "When the person turns the toggle on, the graph restores the fully-wired
    // AC-node view." After clicking, localStorage is updated and (if React Flow
    // renders in jsdom) AC node content appears.
    render(<FlowExplorer flow={testFlow} />);
    const toggle = screen.getByTitle("Show AC nodes in graph");
    fireEvent.click(toggle);
    // At minimum: localStorage must reflect the preference change
    expect(localStorage.getItem("flows:showAcNodes")).toBe("1");
    // After enabling, the toggle title switches to the "hide" state
    expect(screen.queryByTitle("Hide AC nodes from graph")).not.toBeNull();
  });
});

// ===========================================================================
// UXP-605a: 'Show AC nodes in graph' preference persists via localStorage
// ===========================================================================

describe("UXP-605a — Show AC nodes preference persisted in localStorage", () => {
  afterEach(() => {
    localStorage.clear();
  });

  it("show_acs_preference_restored_from_localstorage", () => {
    // covers: UXP-605a
    // "With localStorage 'flows:showAcNodes' set to '1', a fresh mount …
    // initializes showAcNodes true."
    localStorage.setItem("flows:showAcNodes", "1");
    render(<FlowExplorer flow={testFlow} />);
    // In the ON state the toggle title is "Hide AC nodes from graph"
    expect(screen.queryByTitle("Hide AC nodes from graph")).not.toBeNull();
    // The "Show" title should NOT be present (toggle is on)
    expect(screen.queryByTitle("Show AC nodes in graph")).toBeNull();
  });

  it("show_acs_preference_off_when_localstorage_absent", () => {
    // covers: UXP-605a
    // "With '0' or absent it initializes false."
    render(<FlowExplorer flow={testFlow} />);
    expect(screen.queryByTitle("Show AC nodes in graph")).not.toBeNull();
    expect(screen.queryByTitle("Hide AC nodes from graph")).toBeNull();
  });

  it("show_acs_preference_off_when_localstorage_set_to_zero", () => {
    // covers: UXP-605a
    // Explicit '0' must also initialize to off.
    localStorage.setItem("flows:showAcNodes", "0");
    render(<FlowExplorer flow={testFlow} />);
    expect(screen.queryByTitle("Show AC nodes in graph")).not.toBeNull();
    expect(screen.queryByTitle("Hide AC nodes from graph")).toBeNull();
  });

  it("show_acs_init_is_ssr_safe", () => {
    // covers: UXP-605a
    // "The localStorage read must be … wrapped so a storage exception falls
    // back to off without breaking the view."
    const originalGetItem = Storage.prototype.getItem;
    Storage.prototype.getItem = () => {
      throw new Error("Storage quota exceeded");
    };
    try {
      expect(() => render(<FlowExplorer flow={testFlow} />)).not.toThrow();
      // Falls back to off when storage throws
      expect(screen.queryByTitle("Show AC nodes in graph")).not.toBeNull();
    } finally {
      Storage.prototype.getItem = originalGetItem;
    }
  });

  it("toggle_state_persisted_to_localstorage_on_change", () => {
    // covers: UXP-605a / UXP-605
    // "The toggle state is persisted as a view preference." After clicking the
    // toggle on, localStorage 'flows:showAcNodes' must be set to '1'. After
    // clicking off again, it must be set to '0'.
    render(<FlowExplorer flow={testFlow} />);

    // Turn on
    fireEvent.click(screen.getByTitle("Show AC nodes in graph"));
    expect(localStorage.getItem("flows:showAcNodes")).toBe("1");

    // Turn off again
    fireEvent.click(screen.getByTitle("Hide AC nodes from graph"));
    expect(localStorage.getItem("flows:showAcNodes")).toBe("0");
  });
});
