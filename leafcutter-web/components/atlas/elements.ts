/** React Flow edges of the Atlas: the component galaxy and the AC detail DAG. */
import { MarkerType, type Edge } from "reactflow";
import type { GraphEdge } from "@/lib/data/types";
import { edgeStyle } from "./edges";

/** Galaxy edges between visible discs, flipped so arrowheads land on the dependent. */
export function galaxyEdges(edges: GraphEdge[], visibleIds: Set<string>): Edge[] {
  return edges
    .filter((e) => visibleIds.has(e.source) && visibleIds.has(e.target))
    .map((e) => {
      const w = e.weight ?? 1;
      return {
        id: e.id,
        source: e.target,
        target: e.source,
        animated: w >= 4,
        markerEnd: { type: MarkerType.ArrowClosed, color: "hsl(150 64% 52%)", width: 16, height: 16 },
        style: {
          stroke: "hsl(150 64% 52%)",
          strokeWidth: 1 + Math.min(w, 8) * 0.7,
          opacity: 0.28 + Math.min(w, 10) * 0.05,
        },
      };
    });
}

/**
 * Detail edges. depends_on / expects_from point dependent -> prerequisite in the
 * data, so they are flipped; covers and delivers_to already flow downstream.
 */
export function detailEdges(edges: GraphEdge[]): Edge[] {
  return edges.map((e) => {
    const spec = edgeStyle(e.kind);
    const flip = e.kind === "depends_on" || e.kind === "expects_from";
    return {
      id: e.id,
      source: flip ? e.target : e.source,
      target: flip ? e.source : e.target,
      markerEnd: { type: MarkerType.ArrowClosed, color: `hsl(${spec.hsl})`, width: 14, height: 14 },
      style: {
        stroke: `hsl(${spec.hsl})`,
        strokeWidth: e.kind === "depends_on" ? 1.8 : 1.4,
        opacity: e.kind === "covers" ? 0.35 : 0.7,
        strokeDasharray: spec.dashed ? "5 4" : undefined,
      },
    };
  });
}
