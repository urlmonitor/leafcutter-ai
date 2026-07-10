"use client";

/**
 * Custom React Flow node renderers for the Atlas.
 *   componentNode — a glowing "galaxy" disc; size ∝ AC count, ring ∝ done %.
 *   acNode        — a compact AC card; border by level, tint by work-status.
 * nodeTypes is defined once at module scope (React Flow requires a stable ref).
 */
import * as React from "react";
import { Handle, Position, type NodeProps } from "reactflow";
import { cn } from "@/lib/utils";
import { LEVEL_TONE, WORK_STATUS_TONE } from "@/lib/status";
import type { AcLevel, WorkStatus } from "@/lib/data/types";

/* ---------------- Component (galaxy) node ---------------- */

export interface ComponentNodeData {
  label: string;
  hsl: string;
  count: number;
  done: number;
  diameter: number;
  selected?: boolean;
}

function ComponentNodeImpl({ data }: NodeProps<ComponentNodeData>) {
  const { label, hsl, count, done, diameter, selected } = data;
  const donePct = count > 0 ? Math.round((done / count) * 100) : 0;
  const fontScale = Math.max(0.8, Math.min(1.4, diameter / 150));
  return (
    <div
      className="group relative flex items-center justify-center rounded-full transition-transform duration-200 hover:scale-[1.04]"
      style={{
        width: diameter,
        height: diameter,
        // progress ring: leaf-green arc for done, faint track for the rest
        background: `conic-gradient(hsl(${hsl}) ${donePct}%, hsl(156 16% 18%) ${donePct}% 100%)`,
        padding: 6,
        boxShadow: selected
          ? `0 0 0 3px hsl(${hsl} / 0.9), 0 0 42px hsl(${hsl} / 0.55)`
          : `0 0 34px hsl(${hsl} / 0.28)`,
      }}
    >
      {/* hidden center handles so edges route disc-center to disc-center */}
      <Handle
        type="target"
        position={Position.Top}
        className="!h-1 !w-1 !min-w-0 !border-0 !bg-transparent"
        style={{ left: "50%", top: "50%" }}
        isConnectable={false}
      />
      <Handle
        type="source"
        position={Position.Bottom}
        className="!h-1 !w-1 !min-w-0 !border-0 !bg-transparent"
        style={{ left: "50%", top: "50%" }}
        isConnectable={false}
      />
      <div
        className="flex h-full w-full flex-col items-center justify-center rounded-full border border-border/60 bg-card/95 px-3 text-center backdrop-blur"
        style={{ boxShadow: "inset 0 1px 0 hsl(150 40% 90% / 0.05)" }}
      >
        <span
          className="font-semibold leading-tight text-foreground"
          style={{ fontSize: `${0.72 * fontScale}rem` }}
        >
          {label}
        </span>
        <span
          className="mt-0.5 font-mono tabular-nums"
          style={{ fontSize: `${0.95 * fontScale}rem`, color: `hsl(${hsl})` }}
        >
          {count}
        </span>
        <span
          className="text-[9px] uppercase tracking-wider text-muted-foreground"
          style={{ fontSize: `${0.5 * fontScale}rem` }}
        >
          {donePct}% done
        </span>
      </div>
    </div>
  );
}

export const ComponentNode = React.memo(ComponentNodeImpl);

/* ---------------- AC node ---------------- */

export interface AcNodeData {
  id: string;
  title: string;
  level: AcLevel;
  status: WorkStatus;
  selected?: boolean;
  dimmed?: boolean;
  coverageHsl?: string; // when set (color-by-coverage), overrides the status dot
}

function AcNodeImpl({ data }: NodeProps<AcNodeData>) {
  const { id, title, level, status, selected, dimmed, coverageHsl } = data;
  const lvl = LEVEL_TONE[level] ?? LEVEL_TONE.L2;
  const st = WORK_STATUS_TONE[status] ?? WORK_STATUS_TONE.unknown;
  const dotHsl = coverageHsl ?? st.hsl;
  return (
    <div
      className={cn(
        "w-[212px] rounded-lg border bg-card/90 px-3 py-2 backdrop-blur transition-all duration-150",
        "hover:-translate-y-0.5",
        dimmed && "opacity-30",
      )}
      style={{
        borderColor: `hsl(${lvl.hsl} / 0.55)`,
        boxShadow: selected
          ? `0 0 0 2px hsl(${lvl.hsl}), 0 10px 30px -12px hsl(${lvl.hsl} / 0.6)`
          : `0 8px 22px -16px hsl(0 0% 0% / 0.8)`,
      }}
    >
      <Handle
        type="target"
        position={Position.Left}
        className="!h-1.5 !w-1.5 !border-0"
        style={{ background: `hsl(${lvl.hsl})` }}
        isConnectable={false}
      />
      <Handle
        type="source"
        position={Position.Right}
        className="!h-1.5 !w-1.5 !border-0"
        style={{ background: `hsl(${lvl.hsl})` }}
        isConnectable={false}
      />
      <div className="flex items-center justify-between gap-2">
        <span className="truncate font-mono text-[11px] font-medium text-foreground">
          {id}
        </span>
        <span
          className="rounded px-1 py-0.5 text-[9px] font-semibold uppercase tracking-wide"
          style={{ color: `hsl(${lvl.hsl})`, background: `hsl(${lvl.hsl} / 0.12)` }}
        >
          {level}
        </span>
      </div>
      <div className="mt-1 flex items-start gap-1.5">
        <span
          className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full"
          style={{ background: `hsl(${dotHsl})` }}
          title={coverageHsl ? "Test coverage" : st.label}
        />
        <span className="line-clamp-2 text-[11px] leading-snug text-muted-foreground">
          {title || "Untitled"}
        </span>
      </div>
    </div>
  );
}

export const AcNode = React.memo(AcNodeImpl);

export const nodeTypes = {
  componentNode: ComponentNode,
  acNode: AcNode,
} as const;
