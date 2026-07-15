"use client";

/**
 * Floating control surfaces for the Atlas canvas: the filter panel (level /
 * status toggles + text search) and the always-on legend (work-status swatches
 * + edge-type key). Both are presentational; state lives in AtlasExplorer.
 */
import * as React from "react";
import { Search, X, SlidersHorizontal } from "lucide-react";
import { cn } from "@/lib/utils";
import { LEVEL_TONE, WORK_STATUS_TONE } from "@/lib/status";
import type { AcLevel, WorkStatus } from "@/lib/data/types";
import { AC_EDGE_LEGEND, edgeStyle } from "./edges";

export const FILTER_LEVELS: AcLevel[] = ["L0", "L1", "L2", "L3"];
export const FILTER_STATUSES: WorkStatus[] = [
  "done",
  "in_progress",
  "todo",
  "blocked",
  "not_started",
  "unknown",
];

export interface FilterState {
  levels: Set<AcLevel>;
  statuses: Set<WorkStatus>;
  search: string;
  colorByCoverage: boolean;
}

export function FilterPanel({
  filters,
  onChange,
  detailMode,
  onReset,
}: {
  filters: FilterState;
  onChange: (next: FilterState) => void;
  detailMode: boolean;
  onReset: () => void;
}) {
  const toggleLevel = (lvl: AcLevel) => {
    const next = new Set(filters.levels);
    if (next.has(lvl)) next.delete(lvl);
    else next.add(lvl);
    onChange({ ...filters, levels: next });
  };
  const toggleStatus = (st: WorkStatus) => {
    const next = new Set(filters.statuses);
    if (next.has(st)) next.delete(st);
    else next.add(st);
    onChange({ ...filters, statuses: next });
  };

  const dirty =
    filters.search !== "" ||
    filters.colorByCoverage ||
    filters.levels.size !== FILTER_LEVELS.length ||
    filters.statuses.size !== FILTER_STATUSES.length;

  return (
    <div className="panel w-64 p-3.5">
      <div className="mb-2.5 flex items-center justify-between">
        <div className="eyebrow flex items-center gap-1.5">
          <SlidersHorizontal className="h-3 w-3" />
          Filters
        </div>
        {dirty && (
          <button
            type="button"
            onClick={onReset}
            className="text-[11px] text-muted-foreground transition-colors hover:text-foreground"
          >
            Reset
          </button>
        )}
      </div>

      <div className="relative mb-3">
        <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
        <input
          value={filters.search}
          onChange={(e) => onChange({ ...filters, search: e.target.value })}
          placeholder={detailMode ? "Search id or title…" : "Search components…"}
          className="w-full rounded-md border border-border bg-background/60 py-1.5 pl-8 pr-7 text-xs text-foreground placeholder:text-muted-foreground/70 focus:border-primary/50 focus:outline-none focus:ring-1 focus:ring-primary/40"
        />
        {filters.search && (
          <button
            type="button"
            onClick={() => onChange({ ...filters, search: "" })}
            className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        )}
      </div>

      {detailMode ? (
        <>
          <div className="mb-1.5 text-[10px] font-medium uppercase tracking-wider text-muted-foreground/80">
            Level
          </div>
          <div className="mb-3 flex flex-wrap gap-1.5">
            {FILTER_LEVELS.map((lvl) => {
              const on = filters.levels.has(lvl);
              const tone = LEVEL_TONE[lvl];
              return (
                <button
                  key={lvl}
                  type="button"
                  onClick={() => toggleLevel(lvl)}
                  className={cn(
                    "rounded-md border px-2 py-1 text-[11px] font-medium transition-all",
                    on ? "text-foreground" : "border-border text-muted-foreground/60 hover:text-muted-foreground",
                  )}
                  style={
                    on
                      ? {
                          borderColor: `hsl(${tone.hsl} / 0.5)`,
                          background: `hsl(${tone.hsl} / 0.14)`,
                          color: `hsl(${tone.hsl})`,
                        }
                      : undefined
                  }
                >
                  {lvl}
                </button>
              );
            })}
          </div>

          <div className="mb-1.5 text-[10px] font-medium uppercase tracking-wider text-muted-foreground/80">
            Work status
          </div>
          <div className="flex flex-wrap gap-1.5">
            {FILTER_STATUSES.map((st) => {
              const on = filters.statuses.has(st);
              const tone = WORK_STATUS_TONE[st];
              return (
                <button
                  key={st}
                  type="button"
                  onClick={() => toggleStatus(st)}
                  className={cn(
                    "inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-[11px] transition-all",
                    on ? "border-border bg-secondary/60 text-foreground" : "border-border/60 text-muted-foreground/50 hover:text-muted-foreground",
                  )}
                >
                  <span
                    className="h-1.5 w-1.5 rounded-full"
                    style={{ background: `hsl(${tone.hsl})`, opacity: on ? 1 : 0.4 }}
                  />
                  {tone.label}
                </button>
              );
            })}
          </div>

          <div className="mt-3 flex items-center justify-between gap-2 border-t border-border/50 pt-3">
            <span className="text-[11px] text-muted-foreground">
              Color by test coverage
            </span>
            <button
              type="button"
              role="switch"
              aria-checked={filters.colorByCoverage}
              onClick={() =>
                onChange({ ...filters, colorByCoverage: !filters.colorByCoverage })
              }
              className={cn(
                "relative h-4 w-7 shrink-0 rounded-full transition-colors",
                filters.colorByCoverage ? "bg-primary" : "bg-muted",
              )}
            >
              <span
                className={cn(
                  "absolute top-0.5 h-3 w-3 rounded-full bg-background transition-transform",
                  filters.colorByCoverage ? "translate-x-3.5" : "translate-x-0.5",
                )}
              />
            </button>
          </div>
          {filters.colorByCoverage && (
            <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-[10px] text-muted-foreground">
              <span className="inline-flex items-center gap-1">
                <span className="h-1.5 w-1.5 rounded-full" style={{ background: "hsl(356 72% 56%)" }} />
                0 tests
              </span>
              <span className="inline-flex items-center gap-1">
                <span className="h-1.5 w-1.5 rounded-full" style={{ background: "hsl(38 92% 58%)" }} />
                1–2
              </span>
              <span className="inline-flex items-center gap-1">
                <span className="h-1.5 w-1.5 rounded-full" style={{ background: "hsl(150 60% 48%)" }} />
                3+
              </span>
            </div>
          )}
        </>
      ) : (
        <p className="text-[11px] leading-relaxed text-muted-foreground">
          Click a component to drill into its acceptance-criteria graph. Level &
          status filters activate in detail view.
        </p>
      )}
    </div>
  );
}

export function AtlasLegend({ detailMode }: { detailMode: boolean }) {
  return (
    <div className="panel max-w-xs p-3.5">
      <div className="eyebrow mb-2">Legend</div>
      <div className="mb-1 text-[10px] font-medium uppercase tracking-wider text-muted-foreground/80">
        Work status
      </div>
      <div className="mb-3 flex flex-wrap gap-x-3 gap-y-1.5">
        {FILTER_STATUSES.map((st) => {
          const tone = WORK_STATUS_TONE[st];
          return (
            <span key={st} className="inline-flex items-center gap-1.5 text-[11px] text-muted-foreground">
              <span className="h-2 w-2 rounded-full" style={{ background: `hsl(${tone.hsl})` }} />
              {tone.label}
            </span>
          );
        })}
      </div>
      {detailMode && (
        <>
          <div className="mb-1 text-[10px] font-medium uppercase tracking-wider text-muted-foreground/80">
            Edge type
          </div>
          <div className="flex flex-wrap gap-x-3 gap-y-1.5">
            {AC_EDGE_LEGEND.map((kind) => {
              const spec = edgeStyle(kind);
              return (
                <span key={kind} className="inline-flex items-center gap-1.5 text-[11px] text-muted-foreground">
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
        </>
      )}
    </div>
  );
}
