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
import type { WorkStatus } from "@/lib/data/types";
import { AcNode } from "@/components/atlas/nodes";

export interface FlowStepNodeData {
  label: string;
  order?: number;
  screen: string | null;
  status: WorkStatus;
  variant: "step" | "branch";
  acCount: number;
  drillable?: boolean;   // step has a resolvable expands_to child flow
  selected?: boolean;
}

function FlowStepNodeImpl({ data }: NodeProps<FlowStepNodeData>) {
  const { label, order, screen, status, variant, acCount, drillable, selected } = data;
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
          <span className="inline-flex items-center gap-1">
            <Monitor className="h-3 w-3" />
            {screen}
          </span>
        )}
        {acCount > 0 && (
          <span className="font-mono">
            {acCount} AC{acCount === 1 ? "" : "s"}
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

export const flowNodeTypes = {
  flowStepNode: FlowStepNode,
  acNode: AcNode,
} as const;
