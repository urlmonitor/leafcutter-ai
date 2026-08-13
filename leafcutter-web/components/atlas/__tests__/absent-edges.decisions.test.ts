/**
 * Black-box tests for KM-ADM-003 ("Atlas draws an absent relation as a gap,
 * never as an untrusted link"), derived exclusively from the AC's Gherkin
 * Then-clauses — NOT from reading the fix (the fix has not landed; this file
 * is authored BEFORE python-coder/frontend-coder touch lib/data/types.ts,
 * lib/data/graph.ts, components/atlas/edges.ts, or
 * components/flows/flow-explorer.tsx).
 *
 * Symptom under test (commit b7e9919c6): docs/reference/artifact-knowledge-graph.graph.json
 * now marks four relations that do not exist in the repo with status:"absent".
 * artifactEdgeStyle() ignores `status` entirely (it only reads enforcement x
 * shape), and buildArtifactGraph() never copies `status` out of the JSON onto
 * the produced GraphEdge — so all four absent edges render identically to a
 * present-but-unenforced ("untrusted"/grey) link, and the four recorded gaps
 * read as real links.
 *
 * Root-cause guard (KM-ADM-001 antipattern, explicitly rejected in the AC
 * notes): the verdict must be derived from the DECLARED `status` field, never
 * inferred from the incidental absence of another field such as `shape`
 * (absent edges happen to omit `shape`, which is the one-file shortcut the AC
 * forbids). See the "AC3" describe block below — it is the most important
 * test in this file.
 *
 * Per this repo's "Real-artifact behavioral spot-check" convention
 * (CLAUDE.md), the fixture for this file is the REAL on-disk
 * docs/reference/artifact-knowledge-graph.graph.json — not a hand-authored
 * synthetic doc — read directly off disk, resolved relative to this test
 * file's own location.
 */
import { describe, it, expect } from "vitest";
import fs from "node:fs";
import path from "node:path";
import { artifactEdgeStyle, INGESTABILITY_LEGEND } from "@/components/atlas/edges";
import type { Ingestability } from "@/components/atlas/edges";
import { buildArtifactGraph } from "@/lib/data/graph";
import type { Flow } from "@/lib/data/types";

// ---------------------------------------------------------------------------
// Load the REAL authored graph doc. Path resolved from this file's own
// location (worktree root is 4 levels up from components/atlas/__tests__).
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

/** The four gap edges KM-ADM-002 introduced with status "absent". */
const ABSENT_EDGE_IDS = [
  "source-implements-ac",
  "test-exercises-source",
  "changelog-delivers-ac",
  "mockup-realizes-ac",
];

const PRESENT_EDGES = REAL_EDGES.filter((e) => e.status === "present");
const ABSENT_EDGES = REAL_EDGES.filter((e) => e.status === "absent");

// ---------------------------------------------------------------------------
// Sanity on the fixture itself — not a KM-ADM-003 behavior assertion, just a
// guard that the "read the real artifact" premise still holds. If this ever
// fails, the four IDs above (and the rest of this file) need updating, not
// the renderer.
// ---------------------------------------------------------------------------
describe("sanity — the real graph doc still carries the four documented absent edges", () => {
  it("real_doc_has_exactly_the_four_documented_absent_edges", () => {
    // covers: KM-ADM-003
    const absentIds = ABSENT_EDGES.map((e) => e.id).sort();
    expect(absentIds).toEqual([...ABSENT_EDGE_IDS].sort());
  });
});

/** Unique (enforcement, shape) combos actually used by PRESENT edges in the real doc. */
function presentCombos(): { enforcement: string; shape: string }[] {
  const seen = new Set<string>();
  const combos: { enforcement: string; shape: string }[] = [];
  for (const e of PRESENT_EDGES) {
    const shape = e.shape ?? "clean";
    const key = `${e.enforcement}::${shape}`;
    if (seen.has(key)) continue;
    seen.add(key);
    combos.push({ enforcement: e.enforcement, shape });
  }
  return combos;
}

/**
 * Oracle for "what a present edge resolves to TODAY", derived directly from
 * the graph doc's own `legend.ingestable_rule` (and mirrored in edges.ts's
 * own doc comment): ingestable only when enforcement is strong
 * (enforced/derived-validated) AND shape is clean/derived; reconcile when
 * strong-but-caveated or warn-only; otherwise untrusted. This is the CURRENT
 * present-edge contract and, per KM-ADM-003 AC2, must NOT change.
 */
function expectedPresentVerdict(enforcement: string, shape: string): Ingestability {
  const strong = enforcement === "enforced" || enforcement === "derived-validated";
  const clean = shape === "clean" || shape === "derived";
  if (strong && clean) return "ingestable";
  if (strong || enforcement === "warn") return "reconcile";
  return "untrusted";
}

/** The set of verdicts ANY present (enforcement, shape) combo in the real doc can produce today. */
function presentPossibleVerdicts(): Set<Ingestability> {
  return new Set(presentCombos().map((c) => expectedPresentVerdict(c.enforcement, c.shape)));
}

// ===========================================================================
// AC1 — an absent edge resolves to its OWN verdict, distinct from "untrusted"
// and from every verdict a present edge can produce; visually distinguishable.
// ===========================================================================

describe("KM-ADM-003 AC1 — an absent edge resolves to its own distinguishable verdict", () => {
  it("ac1_absent_status_does_not_resolve_to_untrusted", () => {
    // covers: KM-ADM-003
    // "that edge resolves to its own ingestability verdict — distinct from
    //  the 'untrusted' verdict used for links that exist but nothing enforces"
    for (const e of ABSENT_EDGES) {
      const spec = (artifactEdgeStyle as any)(e.enforcement, e.shape, "absent");
      expect(spec.ingestability).not.toBe("untrusted");
    }
  });

  it("ac1_absent_verdict_is_not_a_value_any_present_edge_can_produce", () => {
    // covers: KM-ADM-003
    // The absent verdict must be disjoint from the full set of verdicts
    // ("ingestable" | "reconcile" | "untrusted") present edges can produce —
    // i.e. a genuinely 4th value, not a reuse of one of the three.
    const possible = presentPossibleVerdicts();
    for (const e of ABSENT_EDGES) {
      const spec = (artifactEdgeStyle as any)(e.enforcement, e.shape, "absent");
      expect(possible.has(spec.ingestability)).toBe(false);
    }
  });

  it("ac1_absent_edge_hsl_is_visually_distinguishable_from_every_present_combo", () => {
    // covers: KM-ADM-003
    // "drawn with a visual treatment no present edge can produce" — the hsl
    // colour must not collide with the hsl produced by ANY (enforcement,
    // shape) combination the real graph doc actually uses for a present edge.
    const presentHsls = new Set(
      presentCombos().map((c) => artifactEdgeStyle(c.enforcement, c.shape).hsl),
    );
    for (const e of ABSENT_EDGES) {
      const spec = (artifactEdgeStyle as any)(e.enforcement, e.shape, "absent");
      expect(presentHsls.has(spec.hsl)).toBe(false);
    }
  });
});

// ===========================================================================
// AC2 — safe degradation: no status / status "present" must reproduce
// TODAY's rendering exactly, for every (enforcement, shape) pair the real
// graph doc actually uses on a present edge.
// ===========================================================================

describe("KM-ADM-003 AC2 — safe degradation: adding the status axis must not change existing rendering", () => {
  it.each(presentCombos())(
    "ac2_present_combo_%s_x_%s_unchanged_with_no_status_arg",
    (combo) => {
      // covers: KM-ADM-003
      const { enforcement, shape } = combo as unknown as { enforcement: string; shape: string };
      const spec = artifactEdgeStyle(enforcement, shape);
      expect(spec.ingestability).toBe(expectedPresentVerdict(enforcement, shape));
    },
  );

  it.each(presentCombos())(
    "ac2_present_combo_%s_x_%s_unchanged_with_explicit_present_status",
    (combo) => {
      // covers: KM-ADM-003
      const { enforcement, shape } = combo as unknown as { enforcement: string; shape: string };
      const spec = (artifactEdgeStyle as any)(enforcement, shape, "present");
      expect(spec.ingestability).toBe(expectedPresentVerdict(enforcement, shape));
    },
  );
});

// ===========================================================================
// AC3 — the verdict is derived from the declared `status`, never inferred
// from the absence of another field such as `shape`. THE MOST IMPORTANT TEST
// IN THIS FILE: it is what rules out the one-file shortcut the AC notes
// explicitly reject (inferring "absent" from a missing `shape`).
// ===========================================================================

describe("KM-ADM-003 AC3 — verdict derives from declared status, never inferred from missing shape", () => {
  it("ac3_absent_status_with_an_explicit_shape_still_resolves_to_the_absent_verdict", () => {
    // covers: KM-ADM-003
    // Anti-inference guard, first half: even when `shape` IS present (so the
    // "infer from missing shape" shortcut has no gap to exploit), a
    // declared status "absent" must still win and resolve to the absent
    // verdict. A renderer that keys off "shape is missing" would get this
    // case wrong in the opposite direction from AC3's second half.
    const possible = presentPossibleVerdicts();
    const spec = (artifactEdgeStyle as any)("none", "clean", "absent");
    expect(possible.has(spec.ingestability)).toBe(false);
    expect(spec.ingestability).not.toBe("untrusted");
  });

  it("ac3_present_status_with_no_declared_shape_does_not_resolve_to_the_absent_verdict", () => {
    // covers: KM-ADM-003
    // Anti-inference guard, second half (the actual shortcut the AC
    // forbids): an edge with status "present" but NO declared shape must
    // resolve to a normal present-edge verdict, never the absent one, even
    // though "shape is missing" is exactly the signal the rejected shortcut
    // would have keyed off of.
    const possible = presentPossibleVerdicts();
    const withPresentStatusNoShape = (artifactEdgeStyle as any)("none", undefined, "present");
    expect(possible.has(withPresentStatusNoShape.ingestability)).toBe(true);
  });
});

// ===========================================================================
// AC4 — the on-canvas legend carries a row for the absent treatment.
// ===========================================================================

describe("KM-ADM-003 AC4 — the legend decodes the absent treatment without opening the JSON", () => {
  it("ac4_legend_has_a_row_for_the_absent_treatment_with_a_non_empty_hint", () => {
    // covers: KM-ADM-003
    // "the on-canvas legend carries a row for the absent treatment, so the
    //  reader can decode it without opening the JSON"
    const absentRow = INGESTABILITY_LEGEND.find(
      (row) =>
        (row.key as unknown as string) === "absent" ||
        /absent/i.test(row.label) ||
        /absent/i.test(row.hint),
    );
    expect(absentRow).toBeDefined();
    expect((absentRow?.hint ?? "").length).toBeGreaterThan(0);
  });
});

// ===========================================================================
// AC5 — buildArtifactGraph() carries `status` from the source JSON onto the
// produced GraphEdge, so the renderer can actually read it. Exercised against
// the REAL on-disk graph doc (real-artifact round trip), not a synthetic one.
// ===========================================================================

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

describe("KM-ADM-003 AC5 — buildArtifactGraph carries status onto the produced GraphEdge", () => {
  it("ac5_the_four_absent_edges_carry_status_absent_on_the_produced_graphedge", () => {
    // covers: KM-ADM-003
    const graph = buildArtifactGraph(realGraphFlow());
    const byId = new Map(graph.edges.map((e) => [e.id, e]));
    for (const id of ABSENT_EDGE_IDS) {
      const edge = byId.get(id);
      expect(edge).toBeDefined();
      expect((edge as any).status).toBe("absent");
    }
  });

  it("ac5_every_present_edge_carries_status_present_on_the_produced_graphedge", () => {
    // covers: KM-ADM-003
    const graph = buildArtifactGraph(realGraphFlow());
    const presentSourceIds = new Set(PRESENT_EDGES.map((e) => e.id));
    const checked = graph.edges.filter((e) => presentSourceIds.has(e.id));
    // Sanity: the real doc has 26 present edges — make sure we actually
    // checked a non-trivial number, not zero (which would silently vacuously
    // pass the loop below).
    expect(checked.length).toBeGreaterThan(0);
    for (const edge of checked) {
      expect((edge as any).status).toBe("present");
    }
  });
});
