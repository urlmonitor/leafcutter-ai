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
 *   2. Self-edge extraction — edges whose source === target (AC -> AC parent /
 *      depends_on / superseded_by) are pulled OUT of the layout and reported
 *      per node, so the caller can badge them instead of drawing degenerate
 *      loops that overlap the card.
 *
 * Pure functions, no React and no fs: safe to import anywhere.
 */
import type { GraphEdge, GraphNode, SelfRel } from "./types";

/** Horizontal distance between rank columns (node is 200px wide). */
export const ARTIFACT_COL_GAP = 320;
/** Vertical distance between nodes stacked in the same column. */
export const ARTIFACT_ROW_GAP = 170;

export interface ArtifactPosition {
  x: number;
  y: number;
}

export interface ArtifactLayout {
  /** nodeId -> canvas position. */
  positions: Map<string, ArtifactPosition>;
  /** nodeId -> self-referencing relationships, each with its encoding field. */
  selfRels: Map<string, SelfRel[]>;
  /** Edges with self-references removed — safe to hand to React Flow. */
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
  for (const e of edges) {
    if (e.source === e.target) {
      const arr = selfRels.get(e.source) ?? [];
      arr.push({
        rel: e.rel ?? e.label ?? "self",
        field: e.field ?? "—",
        enforcement: e.enforcement ?? "none",
        shape: e.shape ?? "clean",
        note: e.note,
      });
      selfRels.set(e.source, arr);
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

  return { positions, selfRels, edges: linkEdges };
}
