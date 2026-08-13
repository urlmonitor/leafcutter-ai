"use client";

/**
 * Self-loop edge for the artifact graph — an arc drawn ABOVE the card.
 *
 * React Flow's built-in edge types cannot draw a usable self-edge here. The
 * artifact node exposes exactly one target handle (left) and one source handle
 * (right), both vertically centred, so a default bezier from right to left is a
 * near-flat curve that runs straight THROUGH the card and reads as noise.
 * Giving the node extra handles is not an option either: the existing handles
 * are unnamed, and React Flow resolves an unspecified sourceHandle to the only
 * handle of that type — adding a second unnamed one would silently re-route
 * every other outgoing edge.
 *
 * So this component ignores the handle geometry's implied path and draws its
 * own: up from the right handle, across above the node, back down into the left
 * handle. `nth` (passed via edge.data) lifts each successive loop higher so two
 * relations on the same node do not overlap.
 *
 * Used for DEPENDS_ON and SUPERSEDED_BY (see SELF_RELS_DRAWN in
 * lib/data/artifact-layout.ts) — the AC -> AC traversals a refactorer needs to
 * follow, which a badge row cannot make clickable.
 */
import * as React from "react";
import { EdgeLabelRenderer, type EdgeProps } from "reactflow";

/** Vertical clearance of the first loop above the card's top edge. */
const BASE_LIFT = 58;
/** Additional lift per stacked loop on the same node. */
const LIFT_STEP = 34;
/** Half the node's height — the handles sit at the vertical centre. */
const HALF_NODE_H = 30;

export function SelfLoopEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  markerEnd,
  style,
  label,
  labelStyle,
  data,
}: EdgeProps) {
  const nth = (data as { nth?: number } | undefined)?.nth ?? 0;
  const lift = BASE_LIFT + nth * LIFT_STEP;

  // Apex sits above the card, not above the handle line, so the arc clears the
  // node body rather than grazing it.
  const apexY = Math.min(sourceY, targetY) - HALF_NODE_H - lift;
  const midX = (sourceX + targetX) / 2;

  // Control points pushed outward past each handle so the arc leaves and
  // re-enters roughly horizontally, the way an arrowhead reads best.
  const path = [
    `M ${sourceX},${sourceY}`,
    `C ${sourceX + 46},${sourceY} ${midX + 70},${apexY} ${midX},${apexY}`,
    `C ${midX - 70},${apexY} ${targetX - 46},${targetY} ${targetX},${targetY}`,
  ].join(" ");

  return (
    <>
      <path
        id={id}
        d={path}
        fill="none"
        markerEnd={markerEnd}
        style={style}
        className="react-flow__edge-path"
      />
      {/* Invisible fat stroke — the visible line is 1.3px, far too thin to
          click. Every other edge gets this from React Flow's interactionWidth;
          a custom edge has to draw its own. */}
      <path d={path} fill="none" strokeWidth={18} stroke="transparent" />
      {label ? (
        <EdgeLabelRenderer>
          <div
            style={{
              position: "absolute",
              transform: `translate(-50%, -50%) translate(${midX}px, ${apexY}px)`,
              pointerEvents: "all",
              background: "hsl(158 12% 11% / 0.75)",
              borderRadius: 3,
              padding: "1px 4px",
              fontSize: 9,
              fontWeight: 600,
              ...(labelStyle as React.CSSProperties),
            }}
            className="nodrag nopan"
          >
            {label}
          </div>
        </EdgeLabelRenderer>
      ) : null}
    </>
  );
}

export const artifactEdgeTypes = { selfLoop: SelfLoopEdge };
