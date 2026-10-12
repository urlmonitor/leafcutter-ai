"use client";

/**
 * Selector controls of the Flows view: the segmented toggles (source / kind /
 * realization), the per-flow selector and the drill breadcrumb. Presentational
 * only: all state stays in <FlowsView>.
 */
import * as React from "react";
import { cn } from "@/lib/utils";
import type { Flow, FlowKind, FlowRealization, FlowSource } from "@/lib/data/types";
import { RealizationBadge } from "./realization-badge";
import { ChevronRight } from "lucide-react";

export const SOURCES: FlowSource[] = ["mock", "real"];
export const KINDS: FlowKind[] = ["user", "data", "architecture"];
// "all" plus the three realizations, in built→spec→mock order (most→least real).
export type RealizationFilter = "all" | FlowRealization;
export const REALIZATIONS: FlowRealization[] = ["built", "spec", "mock"];
export const REALIZATION_LABEL: Record<RealizationFilter, string> = {
  all: "All",
  built: "Built",
  spec: "Spec",
  mock: "Sample",
};

export function Segmented<T extends string>({
  label,
  options,
  value,
  onChange,
  render,
}: {
  label: string;
  options: T[];
  value: T;
  onChange: (next: T) => void;
  render: (opt: T) => React.ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground/80">
        {label}
      </span>
      <div className="inline-flex flex-wrap gap-1 rounded-lg border border-border/70 bg-card/60 p-1">
        {options.map((opt) => {
          const active = opt === value;
          return (
            <button
              key={opt}
              type="button"
              onClick={() => onChange(opt)}
              className={cn(
                "inline-flex items-center gap-2 rounded-md px-3 py-1.5 text-sm transition-colors",
                active
                  ? "bg-primary/15 font-medium text-foreground"
                  : "text-muted-foreground hover:bg-secondary/60 hover:text-foreground",
              )}
            >
              {render(opt)}
            </button>
          );
        })}
      </div>
    </div>
  );
}

/** Per-flow selector (only flows matching source + kind). */
export function FlowSelector({
  flows,
  activeId,
  onSelect,
}: {
  flows: Flow[];
  activeId: string | undefined;
  onSelect: (id: string) => void;
}) {
  return (
    <div className="mb-4 flex flex-wrap items-center gap-2">
      <span className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground/80">
        Flow
      </span>
      <div className="inline-flex flex-wrap gap-1 rounded-lg border border-border/70 bg-card/60 p-1">
        {flows.map((f) => {
          const active = f.id === activeId;
          return (
            <button
              key={f.id}
              type="button"
              onClick={() => onSelect(f.id)}
              className={cn(
                "inline-flex items-center gap-2 rounded-md px-3 py-1.5 text-sm transition-colors",
                active
                  ? "bg-primary/15 font-medium text-foreground"
                  : "text-muted-foreground hover:bg-secondary/60 hover:text-foreground",
              )}
            >
              <span>{f.name}</span>
              {f.realization !== "built" && (
                <RealizationBadge realization={f.realization} size="sm" />
              )}
              <span
                className={cn(
                  "rounded px-1.5 py-0.5 font-mono text-[10px] tabular-nums",
                  active
                    ? "bg-success/15 text-success"
                    : "bg-muted/50 text-muted-foreground",
                )}
              >
                {f.implSummary.done}/{f.implSummary.total} done
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

/** Breadcrumb drill path — click a crumb to zoom back out to that level. */
export function FlowCrumbs({
  crumbs,
  onSelect,
}: {
  crumbs: Flow[];
  onSelect: (index: number) => void;
}) {
  return (
      <nav className="mb-3 flex flex-wrap items-center gap-1 text-sm">
        {crumbs.map((c, i) => {
          const last = i === crumbs.length - 1;
          return (
            <React.Fragment key={c.id}>
              {i > 0 && (
                <ChevronRight className="h-3.5 w-3.5 text-muted-foreground/60" />
              )}
              <button
                type="button"
                disabled={last}
                onClick={() => onSelect(i)}
                className={cn(
                  "rounded-md px-2 py-1 transition-colors",
                  last
                    ? "font-medium text-foreground"
                    : "text-muted-foreground hover:bg-secondary/60 hover:text-foreground",
                )}
              >
                {c.name}
              </button>
            </React.Fragment>
          );
        })}
      </nav>
  );
}
