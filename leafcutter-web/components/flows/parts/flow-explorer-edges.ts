/** React Flow edges of a drawn flow: flow-order arrows, decision labels and yes/no handles. */
import { MarkerType, type Edge } from "reactflow";
import type { GraphEdge } from "@/lib/data/types";
import { edgeStyle } from "@/components/atlas/edges";

export function buildFlowEdges(edges: GraphEdge[]): Edge[] {
  return edges.map((e) => {
    const spec = edgeStyle(e.kind);
    const isFlow = e.kind === "flow";
    const base: Edge = {
      id: e.id,
      source: e.source,
      target: e.target,
      animated: isFlow,
      markerEnd: { type: MarkerType.ArrowClosed, color: `hsl(${spec.hsl})`, width: 15, height: 15 },
      style: {
        stroke: `hsl(${spec.hsl})`,
        strokeWidth: isFlow ? 2 : 1.4,
        opacity: isFlow ? 0.85 : 0.55,
        strokeDasharray: spec.dashed ? "5 4" : undefined,
      },
    };
    // Decision edge label (yes / no / else / continue)
    if (e.label) {
      base.label = e.label;
      base.labelStyle = { fill: "hsl(155 7% 78%)", fontSize: 10, fontWeight: 600 };
      base.labelBgStyle = { fill: "hsl(158 12% 11%)", fillOpacity: 0.88 };
      base.labelBgPadding = [3, 5] as [number, number];
    }
    // Source handle routing for decision diamond edges ("yes" | "no")
    if (e.sourceHandle) base.sourceHandle = e.sourceHandle;
    return base;
  });
}
