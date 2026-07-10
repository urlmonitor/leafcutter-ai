/**
 * Edge-kind visual vocabulary for the AC subgraph. One place that maps a
 * GraphEdgeKind to its stroke colour / dash / label so the canvas and the
 * legend never drift apart.
 */
import type { GraphEdgeKind } from "@/lib/data/types";

export interface EdgeStyleSpec {
  label: string;
  hsl: string;
  dashed: boolean;
}

export const EDGE_STYLES: Record<string, EdgeStyleSpec> = {
  depends_on: { label: "depends on", hsl: "150 64% 52%", dashed: false },
  delivers_to: { label: "delivers to", hsl: "168 60% 46%", dashed: true },
  expects_from: { label: "expects from", hsl: "200 78% 60%", dashed: true },
  covers: { label: "covers", hsl: "150 8% 52%", dashed: true },
  implements: { label: "implements", hsl: "265 60% 66%", dashed: true },
  member_of: { label: "member of", hsl: "150 8% 52%", dashed: true },
  flow: { label: "flow", hsl: "38 92% 58%", dashed: false },
};

export function edgeStyle(kind: GraphEdgeKind): EdgeStyleSpec {
  return EDGE_STYLES[kind] ?? EDGE_STYLES.depends_on;
}

/** Edge kinds that actually appear in the AC subgraph, for the legend. */
export const AC_EDGE_LEGEND: GraphEdgeKind[] = [
  "depends_on",
  "delivers_to",
  "expects_from",
  "covers",
];
