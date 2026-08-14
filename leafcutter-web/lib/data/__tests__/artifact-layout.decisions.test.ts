/**
 * Black-box tests for KM-ADM-004 ("AC-to-AC dependency is drawn as a
 * traversable edge, not hidden in a badge"), derived exclusively from the
 * AC's Then-clauses — NOT from reading the fix (the fix has not landed;
 * this file is authored BEFORE python-coder/frontend-coder touch
 * lib/data/artifact-layout.ts).
 *
 * AC: docs/acceptance-criteria/knowledge-management/KM-ADM-004.yaml
 *
 * Symptom under test: layoutArtifactGraph()'s "1. Split self-edges out"
 * block (lib/data/artifact-layout.ts) partitions purely on
 * `source === target`, so it lumps the three PARENT_OF self-edges
 * (structural hierarchy, safely badge-summarised) together with
 * DEPENDS_ON and SUPERSEDED_BY (real many-to-many traversals) and drops
 * ALL FIVE out of the returned `edges` array. DEPENDS_ON / SUPERSEDED_BY
 * must instead be promoted back into the drawn edge set while the three
 * PARENT_OF variants stay badge-only — and every one of the five must
 * still appear in the per-node `selfRels` badge listing regardless of
 * promotion.
 *
 * Per this repo's "Real-artifact behavioral spot-check" convention
 * (CLAUDE.md), the fixture for this file is the REAL on-disk
 * docs/reference/artifact-knowledge-graph.graph.json — not a hand-authored
 * synthetic doc — read directly off disk, resolved relative to this test
 * file's own location, and run through the real buildArtifactGraph() the
 * same way components/atlas/__tests__/absent-edges.decisions.test.ts does.
 */
import { describe, it, expect } from "vitest";
import fs from "node:fs";
import path from "node:path";
import { buildArtifactGraph } from "@/lib/data/graph";
import { layoutArtifactGraph } from "@/lib/data/artifact-layout";
import type { Flow } from "@/lib/data/types";

// ---------------------------------------------------------------------------
// Load the REAL authored graph doc. Path resolved from this file's own
// location (worktree root is 4 levels up from lib/data/__tests__).
// ---------------------------------------------------------------------------
const GRAPH_JSON_PATH = path.resolve(
  __dirname,
  "../../../../docs/reference/artifact-knowledge-graph.graph.json",
);

function loadRealGraphDoc(): { id: string; nodes: any[]; edges: any[] } {
  const raw = fs.readFileSync(GRAPH_JSON_PATH, "utf8");
  return JSON.parse(raw);
}

const REAL_DOC = loadRealGraphDoc();
const REAL_EDGES = REAL_DOC.edges;

/** The three PARENT_OF self-edges that must remain badge-only. */
const PARENT_OF_EDGE_IDS = ["ac-parent-id", "ac-parent-field", "ac-parent-coveredby"];
/** The two genuine-traversal self-edges that must be promoted to visible edges. */
const PROMOTED_EDGE_IDS = ["ac-depends", "ac-superseded"];
/** All five self-relations authored on the "ac" node. */
const ALL_AC_SELF_EDGE_IDS = [...PARENT_OF_EDGE_IDS, ...PROMOTED_EDGE_IDS];

function realGraphFlow(): Flow {
  return {
    id: REAL_DOC.id,
    component: "artifact-knowledge-graph",
    product: null,
    name: "test",
    summary: "",
    kind: "architecture",
    source: "real",
    level: "journey",
    realization: "built",
    status: "active",
    readiness: "approved",
    entities: [],
    mockDataRef: null,
    steps: [],
    branches: [],
    scenarios: [],
    implSummary: {
      done: 0,
      in_progress: 0,
      not_started: 0,
      total: 0,
      asof: null,
      acDone: 0,
      acTotal: 0,
    },
    filePath: "docs/reference/artifact-knowledge-graph.graph.json",
    graphNodes: REAL_DOC.nodes,
    graphEdges: REAL_EDGES,
  } as unknown as Flow;
}

// ---------------------------------------------------------------------------
// Sanity on the fixture itself — not a KM-ADM-004 behavior assertion, just a
// guard that the "read the real artifact" premise still holds. If this ever
// fails, the IDs above (and the rest of this file) need updating, not the
// layout function.
// ---------------------------------------------------------------------------
describe("sanity — the real graph doc still carries the five documented ac self-relations", () => {
  it("real_doc_has_exactly_the_five_documented_ac_self_edges", () => {
    // covers: KM-ADM-004
    const acSelfIds = REAL_EDGES.filter((e: any) => e.source === "ac" && e.target === "ac")
      .map((e: any) => e.id)
      .sort();
    expect(acSelfIds).toEqual([...ALL_AC_SELF_EDGE_IDS].sort());
  });
});

// ===========================================================================
// AC — DEPENDS_ON and SUPERSEDED_BY are drawn as visible edges, selectable
// and counted in the graph's edge total.
// ===========================================================================
describe("KM-ADM-004 — DEPENDS_ON and SUPERSEDED_BY are promoted to visible edges", () => {
  it("ac1_ac_depends_and_ac_superseded_are_present_in_the_returned_edges_array", () => {
    // covers: KM-ADM-004
    const graph = buildArtifactGraph(realGraphFlow());
    const layout = layoutArtifactGraph(graph.nodes as any, graph.edges as any);
    const edgeIds = new Set(layout.edges.map((e) => e.id));
    for (const id of PROMOTED_EDGE_IDS) {
      expect(edgeIds.has(id)).toBe(true);
    }
  });
});

// ===========================================================================
// AC — the three PARENT_OF variants remain badge rows, because they encode
// one derivable hierarchy rather than a traversal.
// ===========================================================================
describe("KM-ADM-004 — the three PARENT_OF self-edges stay badge-only, never drawn", () => {
  it("ac2_parent_of_edges_are_absent_from_the_returned_edges_array", () => {
    // covers: KM-ADM-004
    const graph = buildArtifactGraph(realGraphFlow());
    const layout = layoutArtifactGraph(graph.nodes as any, graph.edges as any);
    const edgeIds = new Set(layout.edges.map((e) => e.id));
    for (const id of PARENT_OF_EDGE_IDS) {
      expect(edgeIds.has(id)).toBe(false);
    }
  });
});

// ===========================================================================
// AC — every self-relation still appears in the node badge, so no relation
// is lost from the field-level listing by being promoted to an edge.
// ===========================================================================
describe("KM-ADM-004 — every self-relation still appears in the node badge listing", () => {
  it("ac3_ac_node_selfrels_still_lists_all_five_self_relations", () => {
    // covers: KM-ADM-004
    const graph = buildArtifactGraph(realGraphFlow());
    const layout = layoutArtifactGraph(graph.nodes as any, graph.edges as any);
    const acSelfRels = layout.selfRels.get("ac") ?? [];
    expect(acSelfRels.length).toBe(5);
    const dependsOnEntry = acSelfRels.find(
      (r) => r.rel === "DEPENDS_ON" && r.field === "depends_on",
    );
    expect(dependsOnEntry).toBeDefined();
  });
});

// ===========================================================================
// AC — promoting ac-depends to a visible edge must not silently upgrade its
// trust: it keeps its authored enforcement/shape/note, still "enforced" but
// "ambiguous", so a sibling test can still rate the pair "reconcile", not
// "ingestable".
// ===========================================================================
describe("KM-ADM-004 — the promoted ac-depends edge keeps its authored trust payload", () => {
  it("ac4_promoted_ac_depends_edge_keeps_enforced_ambiguous_and_a_note", () => {
    // covers: KM-ADM-004
    const graph = buildArtifactGraph(realGraphFlow());
    const layout = layoutArtifactGraph(graph.nodes as any, graph.edges as any);
    const acDependsEdge = layout.edges.find((e) => e.id === "ac-depends");
    expect(acDependsEdge).toBeDefined();
    expect((acDependsEdge as any)?.enforcement).toBe("enforced");
    expect((acDependsEdge as any)?.shape).toBe("ambiguous");
    expect(((acDependsEdge as any)?.note ?? "").length).toBeGreaterThan(0);
  });
});

// ===========================================================================
// AC — layout safety: a promoted self-edge must not corrupt the layered
// layout. Every node still receives a position, and no position is NaN
// (the barycenter code computes neighbour averages; a self-edge adds a node
// as its own neighbour, which is the obvious way this fix could go wrong).
// ===========================================================================
describe("KM-ADM-004 — a promoted self-edge does not corrupt the layered layout", () => {
  it("ac5_every_node_gets_a_finite_non_nan_position_after_promotion", () => {
    // covers: KM-ADM-004
    const graph = buildArtifactGraph(realGraphFlow());
    const layout = layoutArtifactGraph(graph.nodes as any, graph.edges as any);
    expect(layout.positions.size).toBe(graph.nodes.length);
    for (const node of graph.nodes) {
      const pos = layout.positions.get(node.id);
      expect(pos).toBeDefined();
      expect(Number.isNaN(pos?.x)).toBe(false);
      expect(Number.isNaN(pos?.y)).toBe(false);
    }
  });
});
