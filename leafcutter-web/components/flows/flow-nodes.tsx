"use client";

/**
 * Custom React Flow node renderers for the Flows view.
 *   flowStepNode — a flow step (or branch) card; tint by LIVE derived implStatus.
 *   acNode       — reused from the Atlas (compact AC card, tint by work-status).
 * nodeTypes is defined once at module scope (React Flow needs a stable ref).
 */
import * as React from "react";
import { Handle, Position, type NodeProps } from "reactflow";
import { GitBranch, Monitor, Maximize2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { WORK_STATUS_TONE } from "@/lib/status";
import type { FlowRealization, WorkStatus } from "@/lib/data/types";
import { AcNode } from "@/components/atlas/nodes";
import { RealizationBadge } from "./realization-badge";

export interface FlowStepNodeData {
  label: string;
  order?: number;
  screen: string | null;
  screenTitle?: string | null; // resolved mockup title for the screen slug, if any
  realization?: FlowRealization;
  status: WorkStatus;
  variant: "step" | "branch";
  acCount: number;
  acDone: number;        // count of ACs with workStatus === "done" for this step
  drillable?: boolean;   // step has a resolvable expands_to child flow
  selected?: boolean;
}

function FlowStepNodeImpl({ data }: NodeProps<FlowStepNodeData>) {
  const { label, order, screen, screenTitle, realization, status, variant, acCount, acDone, drillable, selected } = data;
  const st = WORK_STATUS_TONE[status] ?? WORK_STATUS_TONE.unknown;
  const isBranch = variant === "branch";
  return (
    <div
      className={cn(
        "w-[220px] rounded-xl border bg-card/90 px-3.5 py-3 backdrop-blur transition-all duration-150",
        "hover:-translate-y-0.5",
        isBranch && "border-dashed",
        drillable && "cursor-pointer",
      )}
      style={{
        borderColor: `hsl(${st.hsl} / 0.6)`,
        boxShadow: selected
          ? `0 0 0 2px hsl(${st.hsl}), 0 12px 32px -14px hsl(${st.hsl} / 0.65)`
          : `0 8px 22px -16px hsl(0 0% 0% / 0.8)`,
      }}
    >
      <Handle
        type="target"
        position={Position.Left}
        className="!h-1.5 !w-1.5 !border-0"
        style={{ background: `hsl(${st.hsl})` }}
        isConnectable={false}
      />
      <Handle
        type="source"
        position={Position.Right}
        className="!h-1.5 !w-1.5 !border-0"
        style={{ background: `hsl(${st.hsl})` }}
        isConnectable={false}
      />
      <Handle
        type="source"
        position={Position.Bottom}
        className="!h-1.5 !w-1.5 !border-0"
        style={{ background: `hsl(${st.hsl})` }}
        isConnectable={false}
      />
      <div className="flex items-center justify-between gap-2">
        <span className="inline-flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
          {isBranch ? (
            <GitBranch className="h-3 w-3" />
          ) : (
            <span className="font-mono">{order ?? ""}</span>
          )}
          {isBranch ? "Branch" : "Step"}
        </span>
        <div className="flex items-center gap-1">
          {realization && realization !== "built" && (
            <RealizationBadge realization={realization} size="sm" />
          )}
          {drillable && (
            <span
              data-flow-drill="true"
              title="Open sub-flow"
              className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide text-primary transition-colors bg-primary/15 hover:bg-primary/25"
            >
              <Maximize2 className="h-2.5 w-2.5" />
              Open
            </span>
          )}
          <span
            className="rounded px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide"
            style={{ color: `hsl(${st.hsl})`, background: `hsl(${st.hsl} / 0.12)` }}
          >
            {st.label}
          </span>
        </div>
      </div>
      <div className="mt-1.5 text-sm font-semibold leading-snug text-foreground">
        {label}
      </div>
      <div className="mt-1.5 flex items-center gap-2 text-[10px] text-muted-foreground">
        {screen && (
          <span
            className="inline-flex items-center gap-1"
            title={screenTitle ? `Screen: ${screenTitle} (${screen})` : `Screen: ${screen}`}
          >
            <Monitor className="h-3 w-3" />
            {screenTitle ?? screen}
          </span>
        )}
        {acCount > 0 && (
          <span className="inline-flex flex-col gap-0.5">
            <span
              className="rounded px-1.5 py-0.5 font-mono text-[9px] font-semibold tabular-nums"
              style={{ color: `hsl(${st.hsl})`, background: `hsl(${st.hsl} / 0.14)` }}
            >
              {acDone}/{acCount} ACs
            </span>
            <span className="h-0.5 w-full overflow-hidden rounded-full bg-muted/30">
              <span
                className="block h-full rounded-full transition-all duration-300"
                style={{
                  width: `${acCount > 0 ? Math.round((acDone / acCount) * 100) : 0}%`,
                  background: `hsl(${st.hsl})`,
                  opacity: 0.75,
                }}
              />
            </span>
          </span>
        )}
        {drillable && (
          <span
            data-flow-drill="true"
            className="inline-flex items-center gap-1 font-medium text-primary"
            title="Open sub-flow"
          >
            <Maximize2 className="h-2.5 w-2.5" />
            sub-flow
          </span>
        )}
      </div>
    </div>
  );
}

export const FlowStepNode = React.memo(FlowStepNodeImpl);

// ---------------------------------------------------------------------------
// Decision diamond node (ADR-025 chaining semantics)
//
// Visually: a rotated square — the classic flowchart decision symbol.
// Colour: --warning (amber, 38 94% 60%) — signals a conditional fork, distinct
// from rectangular step cards which tint by implStatus.
// Layout: 130 × 130px outer container; 90 × 90px inner square rotated 45°.
// The corners of the 90px diamond align with the 130px box edges, so
// Position.Left/Right/Bottom handles land exactly at the diamond's vertices.
// ---------------------------------------------------------------------------
export interface FlowDecisionNodeData {
  condition: string;     // question text rendered inside the diamond
  yesLabel?: string;     // label on the downward "yes" edge
  noLabel?: string;      // label on the rightward "no/else" edge
  status?: WorkStatus;   // derived impl_status for tinting (UXP-601)
}

function FlowDecisionNodeImpl({ data }: NodeProps<FlowDecisionNodeData>) {
  const { condition, status } = data;
  // Tint the diamond by derived impl_status (UXP-601).
  // Falls back to in_progress (amber) when status is absent — preserves the
  // previous amber appearance for nodes without a status field.
  const st = WORK_STATUS_TONE[status ?? "in_progress"] ?? WORK_STATUS_TONE.unknown;
  return (
    <div
      style={{ width: 130, height: 130, position: "relative", display: "flex", alignItems: "center", justifyContent: "center" }}
    >
      {/* Target: left vertex — incoming edge from step or previous diamond */}
      <Handle
        type="target"
        position={Position.Left}
        className="!h-1.5 !w-1.5 !border-0"
        style={{ background: `hsl(${st.hsl})`, top: "50%" }}
        isConnectable={false}
      />
      {/* Source id="no": right vertex — no/else edge to next diamond or next step */}
      <Handle
        type="source"
        id="no"
        position={Position.Right}
        className="!h-1.5 !w-1.5 !border-0"
        style={{ background: `hsl(${st.hsl})`, top: "50%" }}
        isConnectable={false}
      />
      {/* Source id="yes": bottom vertex — yes edge to the branch outcome */}
      <Handle
        type="source"
        id="yes"
        position={Position.Bottom}
        className="!h-1.5 !w-1.5 !border-0"
        style={{ background: `hsl(${st.hsl})`, left: "50%" }}
        isConnectable={false}
      />

      {/* Diamond shape: 90×90 square rotated 45°; tint follows derived impl_status */}
      <div
        style={{
          width: 90,
          height: 90,
          flexShrink: 0,
          transform: "rotate(45deg)",
          background: `hsl(${st.hsl} / 0.1)`,
          border: `1.5px solid hsl(${st.hsl} / 0.72)`,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          transition: "box-shadow 150ms ease-out",
        }}
      >
        {/* Counter-rotate content so text stays upright */}
        <div
          style={{
            transform: "rotate(-45deg)",
            textAlign: "center",
            width: 90,
            padding: "0 6px",
            pointerEvents: "none",
          }}
        >
          <div
            style={{
              fontSize: 11,
              fontWeight: 700,
              color: `hsl(${st.hsl})`,
              letterSpacing: "0.06em",
              marginBottom: 2,
            }}
          >
            ?
          </div>
          <div
            style={{
              fontSize: 9,
              color: "hsl(155 7% 75%)",
              lineHeight: 1.3,
              overflow: "hidden",
              display: "-webkit-box",
              WebkitLineClamp: 3,
              WebkitBoxOrient: "vertical",
            }}
          >
            {condition}
          </div>
        </div>
      </div>
    </div>
  );
}

export const FlowDecisionNode = React.memo(FlowDecisionNodeImpl);

export const flowNodeTypes = {
  flowStepNode: FlowStepNode,
  acNode: AcNode,
  flowDecisionNode: FlowDecisionNode,
} as const;
