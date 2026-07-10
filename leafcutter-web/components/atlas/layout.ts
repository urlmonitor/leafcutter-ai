/**
 * Deterministic graph layout for the AC Atlas. Pure math — no React, no fs.
 *
 *  - galaxyPositions(): lays component-rollup nodes on a ring, ordered by size,
 *    returning CENTER coordinates (the explorer offsets by each node's radius).
 *  - dagPositions(): lays an AC subgraph as a left-to-right layered DAG, one
 *    column per level (L0 … L3), y-stacked within a column with a light
 *    barycenter pass to reduce edge crossings.
 *
 * Both are stable across renders for identical input (no randomness).
 */
import type { AcLevel, Graph } from "@/lib/data/types";

export interface XY {
  x: number;
  y: number;
}

const LEVEL_ORDER: AcLevel[] = ["L0", "L1", "L2", "L3"];

/** Center points evenly spread on a circle, first node at 12 o'clock. */
export function ringPositions(count: number, radius: number): XY[] {
  if (count <= 0) return [];
  if (count === 1) return [{ x: 0, y: 0 }];
  const out: XY[] = [];
  for (let i = 0; i < count; i++) {
    const angle = (i / count) * Math.PI * 2 - Math.PI / 2;
    out.push({ x: Math.cos(angle) * radius, y: Math.sin(angle) * radius });
  }
  return out;
}

/**
 * Layout a component-galaxy graph. `sizeOf` gives each node's visual radius so
 * the ring radius can scale with node count and returned positions are centers.
 * Returns a map id -> center XY.
 */
export function galaxyPositions(
  nodes: { id: string; weight: number }[],
): Map<string, XY> {
  const ordered = [...nodes].sort(
    (a, b) => b.weight - a.weight || a.id.localeCompare(b.id),
  );
  const n = ordered.length;
  // Ring radius grows with node count so cards never crowd.
  const radius = Math.max(300, n * 46);
  const pts = ringPositions(n, radius);
  const map = new Map<string, XY>();
  ordered.forEach((node, i) => map.set(node.id, pts[i] ?? { x: 0, y: 0 }));
  return map;
}

/**
 * Layered DAG layout: x by AC level, y stacked within the column. A single
 * barycenter sweep orders each column by the mean row of its neighbours in the
 * previous column, which visibly untangles depends_on / covers chains.
 */
export function dagPositions(
  graph: Graph,
  opts: { colGap?: number; rowGap?: number } = {},
): Map<string, XY> {
  const colGap = opts.colGap ?? 320;
  const rowGap = opts.rowGap ?? 78;

  const levelOf = new Map<string, AcLevel>();
  for (const node of graph.nodes) {
    levelOf.set(node.id, (node.level as AcLevel) ?? "L2");
  }

  // Bucket node ids by level, preserving only levels that exist.
  const columns: string[][] = LEVEL_ORDER.map((lvl) =>
    graph.nodes.filter((nd) => (nd.level ?? "L2") === lvl).map((nd) => nd.id),
  );

  // Undirected adjacency for barycenter ordering.
  const neighbours = new Map<string, Set<string>>();
  const link = (a: string, b: string) => {
    if (!neighbours.has(a)) neighbours.set(a, new Set());
    if (!neighbours.has(b)) neighbours.set(b, new Set());
    neighbours.get(a)!.add(b);
    neighbours.get(b)!.add(a);
  };
  for (const e of graph.edges) link(e.source, e.target);

  const orderIndex = new Map<string, number>();
  const pos = new Map<string, XY>();

  columns.forEach((col, colIdx) => {
    let ordered: string[];
    if (colIdx === 0) {
      ordered = [...col].sort((a, b) => a.localeCompare(b));
    } else {
      ordered = [...col].sort((a, b) => {
        const ba = barycenter(a, neighbours, orderIndex);
        const bb = barycenter(b, neighbours, orderIndex);
        if (ba !== bb) return ba - bb;
        return a.localeCompare(b);
      });
    }
    const height = (ordered.length - 1) * rowGap;
    ordered.forEach((id, row) => {
      orderIndex.set(id, row);
      pos.set(id, { x: colIdx * colGap, y: row * rowGap - height / 2 });
    });
  });

  return pos;
}

function barycenter(
  id: string,
  neighbours: Map<string, Set<string>>,
  orderIndex: Map<string, number>,
): number {
  const nbrs = neighbours.get(id);
  if (!nbrs || nbrs.size === 0) return Number.POSITIVE_INFINITY;
  let sum = 0;
  let cnt = 0;
  Array.from(nbrs).forEach((nb) => {
    const idx = orderIndex.get(nb);
    if (idx !== undefined) {
      sum += idx;
      cnt++;
    }
  });
  return cnt === 0 ? Number.POSITIVE_INFINITY : sum / cnt;
}
