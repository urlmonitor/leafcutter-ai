/**
 * Layered layout for the artifact knowledge graph.
 *
 * The authored JSON gives each node a `rank` (its column). Stacking nodes
 * naively inside a column produces a readable grid but a tangled edge mess,
 * because a hub node (AC) links to almost every other artifact. This module
 * adds the two things that make the default view legible without dragging:
 *
 *   1. Barycenter ordering — nodes inside a column are re-ordered so each sits
 *      near the average vertical position of its neighbours (Sugiyama step 2).
 *      A few forward/backward sweeps removes most crossings.
 *   2. Self-edge handling — edges whose source === target (AC -> AC) are always
 *      reported per node so the caller can badge them. Whether they are ALSO
 *      drawn depends on what the relation means; see SELF_RELS_DRAWN below.
 *
 * Pure functions, no React and no fs: safe to import anywhere.
 */
import type { GraphEdge, GraphNode, SelfRel } from "./types";

/**
 * Self-relations that are DRAWN as edges in addition to being badged.
 *
 * Not every self-edge deserves a line. The AC node carries five, and they split
 * cleanly in two:
 *
 *   - Three PARENT_OF variants encode ONE derivable hierarchy (strip the last ID
 *     segment). They are structure, not a traversal, and drawing all three would
 *     put three overlapping loops on the card for a fact the badge states better.
 *   - DEPENDS_ON and SUPERSEDED_BY are genuine many-to-many traversals: given
 *     this AC, which others does a change here reach? That is the question the
 *     whole map exists to answer, so it must be a clickable line — the trust
 *     panel (enforcement, shape, cardinality, the Gap 8 caveat) hangs off edge
 *     selection and is unreachable from a badge.
 *
 * Drawing does NOT imply trusting: ac-depends stays enforced-but-AMBIGUOUS and
 * still renders amber with its warn glyph.
 */
export const SELF_RELS_DRAWN = new Set(["DEPENDS_ON", "SUPERSEDED_BY"]);

/** Horizontal distance between rank columns (node is 200px wide). */
export const ARTIFACT_COL_GAP = 320;
/** Vertical distance between nodes stacked in the same column. */
export const ARTIFACT_ROW_GAP = 170;

export interface ArtifactPosition {
  x: number;
  y: number;
}

/** Append to a Map-of-arrays, creating the bucket on first use. */
function arrPush<T>(map: Map<string, T[]>, key: string, value: T): void {
  const arr = map.get(key) ?? [];
  arr.push(value);
  map.set(key, arr);
}

export interface ArtifactLayout {
  /** nodeId -> canvas position. */
  positions: Map<string, ArtifactPosition>;
  /** nodeId -> ALL self-referencing relationships, each with its encoding field. */
  selfRels: Map<string, SelfRel[]>;
  /**
   * Edges to hand React Flow: every cross-node edge, plus the self-edges whose
   * relation is in SELF_RELS_DRAWN. The drawn self-edges also appear in
   * `selfRels` — badge and line are complementary, not exclusive.
   */
  edges: GraphEdge[];
}

/**
 * Compute a crossing-reduced layered layout.
 *
 * @param nodes Artifact nodes carrying `meta.rank`.
 * @param edges All authored edges (self-edges are filtered out of the result).
 * @param sweeps Barycenter refinement passes; 4 is plenty for a graph this size.
 */
export function layoutArtifactGraph(
  nodes: GraphNode[],
  edges: GraphEdge[],
  sweeps = 4,
): ArtifactLayout {
  // ---------------------------------------------------------------
  // 1. Split self-edges out — they carry meaning but must not be laid out.
  // ---------------------------------------------------------------
  // The FIELD is what distinguishes them: AC carries three PARENT_OF entries
  // (ID-derivation, `parent`, `covered_by` back-link) that are otherwise
  // identical strings and read as a duplication bug.
  const selfRels = new Map<string, SelfRel[]>();
  const linkEdges: GraphEdge[] = [];
  // Self-edges promoted to drawn edges, tracked separately so they can be kept
  // OUT of the barycenter adjacency below.
  const drawnSelfEdges: GraphEdge[] = [];
  for (const e of edges) {
    if (e.source === e.target) {
      const rel = e.rel ?? e.label ?? "self";
      arrPush(selfRels, e.source, {
        rel,
        field: e.field ?? "—",
        enforcement: e.enforcement ?? "none",
        shape: e.shape ?? "clean",
        note: e.note,
      });
      // Badged AND drawn — the badge keeps the field-level detail, the edge
      // makes the relation clickable and countable.
      if (SELF_RELS_DRAWN.has(rel)) drawnSelfEdges.push(e);
    } else {
      linkEdges.push(e);
    }
  }

  // ---------------------------------------------------------------
  // 2. Bucket nodes into their rank columns.
  // ---------------------------------------------------------------
  const rankOf = new Map<string, number>();
  const columns = new Map<number, string[]>();
  for (const n of nodes) {
    const rank = (n.meta?.rank as number) ?? 0;
    rankOf.set(n.id, rank);
    const arr = columns.get(rank) ?? [];
    arr.push(n.id);
    columns.set(rank, arr);
  }
  const rankKeys = Array.from(columns.keys()).sort((a, b) => a - b);

  // Adjacency (undirected) for barycenter computation.
  const neighbours = new Map<string, string[]>();
  for (const e of linkEdges) {
    const a = neighbours.get(e.source) ?? [];
    a.push(e.target);
    neighbours.set(e.source, a);
    const b = neighbours.get(e.target) ?? [];
    b.push(e.source);
    neighbours.set(e.target, b);
  }

  // Current row index of each node within its column.
  const rowOf = new Map<string, number>();
  for (const key of rankKeys) {
    columns.get(key)!.forEach((id, i) => rowOf.set(id, i));
  }

  // ---------------------------------------------------------------
  // 3. Barycenter sweeps: order each column by the mean row of its neighbours.
  //    Alternating direction converges faster than a single-direction pass.
  // ---------------------------------------------------------------
  const reorder = (keys: number[]) => {
    for (const key of keys) {
      const col = columns.get(key)!;
      const bary = new Map<string, number>();
      for (const id of col) {
        const nb = neighbours.get(id) ?? [];
        // Only neighbours in OTHER columns inform vertical placement.
        const rows = nb
          .filter((m) => rankOf.get(m) !== key)
          .map((m) => rowOf.get(m) ?? 0);
        // Nodes with no cross-column neighbour keep their current slot.
        bary.set(
          id,
          rows.length ? rows.reduce((s, r) => s + r, 0) / rows.length : (rowOf.get(id) ?? 0),
        );
      }
      col.sort((a, b) => (bary.get(a) ?? 0) - (bary.get(b) ?? 0));
      col.forEach((id, i) => rowOf.set(id, i));
    }
  };

  for (let s = 0; s < sweeps; s++) {
    reorder(s % 2 === 0 ? rankKeys : [...rankKeys].reverse());
  }

  // ---------------------------------------------------------------
  // 4. Assign coordinates, vertically centering each column against the
  //    tallest one so the graph reads as a balanced band, not a staircase.
  // ---------------------------------------------------------------
  const tallest = Math.max(...rankKeys.map((k) => columns.get(k)!.length), 1);
  const positions = new Map<string, ArtifactPosition>();
  for (const key of rankKeys) {
    const col = columns.get(key)!;
    const offset = ((tallest - col.length) * ARTIFACT_ROW_GAP) / 2;
    col.forEach((id, i) => {
      positions.set(id, {
        x: key * ARTIFACT_COL_GAP,
        y: offset + i * ARTIFACT_ROW_GAP,
      });
    });
  }

  // Promoted self-edges join the drawn set only HERE, after layout is settled.
  // They are deliberately excluded from `neighbours` above: a self-edge would
  // register a node as its own barycenter neighbour, dragging its row toward
  // its own current position and defeating the crossing reduction.
  return { positions, selfRels, edges: [...linkEdges, ...drawnSelfEdges] };
}
