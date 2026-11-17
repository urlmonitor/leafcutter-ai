"use client";

/**
 * Legend panel of the step/branch canvas: step-status and edge-type keys, the
 * feature-level AC rollup and the "Show ACs in graph" toggle.
 */
import * as React from "react";
import { edgeStyle } from "@/components/atlas/edges";
import { WORK_STATUS_TONE } from "@/lib/status";
import { cn } from "@/lib/utils";
import type { Flow, WorkStatus } from "@/lib/data/types";

const STATUS_LEGEND: WorkStatus[] = ["done", "in_progress", "not_started"];
const EDGE_LEGEND_ALL = ["flow", "implements"] as const;
type EdgeLegendKind = (typeof EDGE_LEGEND_ALL)[number];

export function FlowLegend({
  flow,
  showAcNodes,
  onToggleAcNodes,
}: {
  flow: Flow;
  showAcNodes: boolean;
  onToggleAcNodes: () => void;
}) {
  return (
  <div className="pointer-events-none absolute right-4 top-4 z-10">
    <div className="pointer-events-auto panel max-w-xs p-3.5">
      <div className="eyebrow mb-2">Legend</div>
      <div className="mb-1 text-[10px] font-medium uppercase tracking-wider text-muted-foreground/80">
        Step status
      </div>
      <div className="mb-3 flex flex-wrap gap-x-3 gap-y-1.5">
        {STATUS_LEGEND.map((st) => {
          const tone = WORK_STATUS_TONE[st];
          return (
            <span
              key={st}
              className="inline-flex items-center gap-1.5 text-[11px] text-muted-foreground"
            >
              <span
                className="h-2 w-2 rounded-full"
                style={{ background: `hsl(${tone.hsl})` }}
              />
              {tone.label}
            </span>
          );
        })}
      </div>
      <div className="mb-1 text-[10px] font-medium uppercase tracking-wider text-muted-foreground/80">
        Edge type
      </div>
      <div className="mb-3 flex flex-wrap gap-x-3 gap-y-1.5">
        {(showAcNodes ? EDGE_LEGEND_ALL : (["flow"] as EdgeLegendKind[])).map((kind) => {
          const spec = edgeStyle(kind);
          return (
            <span
              key={kind}
              className="inline-flex items-center gap-1.5 text-[11px] text-muted-foreground"
            >
              <svg width="20" height="6" className="overflow-visible">
                <line
                  x1="0"
                  y1="3"
                  x2="20"
                  y2="3"
                  stroke={`hsl(${spec.hsl})`}
                  strokeWidth="2"
                  strokeDasharray={spec.dashed ? "4 3" : undefined}
                />
              </svg>
              {spec.label}
            </span>
          );
        })}
      </div>
      {/* Feature-level AC rollup + "Show ACs in graph" toggle */}
      <div className="border-t border-border/50 pt-2.5">
        {flow.implSummary.acTotal > 0 && (
          <div className="mb-2 text-[11px] text-muted-foreground">
            Feature:{" "}
            <span
              className="font-mono font-semibold tabular-nums"
              style={{ color: `hsl(${WORK_STATUS_TONE.done.hsl})` }}
            >
              {flow.implSummary.acDone}
            </span>
            <span className="font-mono tabular-nums">
              /{flow.implSummary.acTotal}
            </span>{" "}
            ACs done
          </div>
        )}
        <button
          type="button"
          onClick={onToggleAcNodes}
          className={cn(
            "inline-flex w-full items-center justify-between gap-2 rounded-md px-2.5 py-1.5 text-[11px] transition-colors",
            showAcNodes
              ? "bg-primary/15 text-primary"
              : "text-muted-foreground hover:bg-secondary/60 hover:text-foreground",
          )}
          title={showAcNodes ? "Hide AC nodes from graph" : "Show AC nodes in graph"}
        >
          <span>Show ACs in graph</span>
          <span
            className={cn(
              "h-2.5 w-2.5 rounded-full border transition-colors",
              showAcNodes
                ? "border-primary/60 bg-primary"
                : "border-muted-foreground/40 bg-transparent",
            )}
          />
        </button>
      </div>
    </div>
  </div>
  );
}
