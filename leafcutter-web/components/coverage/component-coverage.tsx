"use client";

import * as React from "react";
import { ArrowDownWideNarrow, Boxes } from "lucide-react";
import { cn, fmt } from "@/lib/utils";
import { colorForKey } from "@/lib/status";
import { coverageToneHsl, type CoverageBar } from "./shared";

type SortMode = "worst" | "largest";

const INITIAL = 12;

/**
 * Per-component guarded% as a sorted bar list. Defaults to worst-covered first
 * so the zeros surface immediately; a toggle re-sorts by component size. Bars
 * are tinted by a coverage-health tone (red → amber → green).
 */
export function ComponentCoverage({ bars }: { bars: CoverageBar[] }) {
  const [sort, setSort] = React.useState<SortMode>("worst");
  const [expanded, setExpanded] = React.useState(false);

  const sorted = React.useMemo(() => {
    const copy = [...bars];
    if (sort === "largest") {
      copy.sort((a, b) => b.total - a.total || a.pct - b.pct);
    } else {
      // worst coverage first, but let larger surfaces break ties (bigger risk)
      copy.sort((a, b) => a.pct - b.pct || b.total - a.total);
    }
    return copy;
  }, [bars, sort]);

  const shown = expanded ? sorted : sorted.slice(0, INITIAL);
  const zeros = bars.filter((b) => b.guarded === 0).length;

  // Two AC-store namespaces can humanize to the same label (e.g. build_pipeline
  // vs build-pipeline). Surface the raw id for any label that collides so the
  // duplicate rows read as distinct data, not a rendering bug.
  const dupLabels = React.useMemo(() => {
    const seen = new Map<string, number>();
    for (const b of bars) seen.set(b.label, (seen.get(b.label) ?? 0) + 1);
    return new Set([...seen].filter(([, n]) => n > 1).map(([l]) => l));
  }, [bars]);

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <p className="text-xs text-muted-foreground">
          <span className="font-semibold text-destructive">{zeros}</span> components have
          zero guarded criteria.
        </p>
        <div className="inline-flex rounded-lg border border-border/70 bg-card/50 p-0.5 text-xs">
          {(["worst", "largest"] as SortMode[]).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => setSort(m)}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 font-medium transition-colors",
                sort === m
                  ? "bg-primary/15 text-foreground"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {m === "worst" ? <ArrowDownWideNarrow className="h-3.5 w-3.5" /> : <Boxes className="h-3.5 w-3.5" />}
              {m === "worst" ? "Worst covered" : "By size"}
            </button>
          ))}
        </div>
      </div>

      <ul className="space-y-2.5">
        {shown.map((b) => {
          const tone = coverageToneHsl(b.pct);
          return (
            <li key={b.key} className="grid grid-cols-[1fr_auto] items-center gap-3">
              <div className="min-w-0">
                <div className="mb-1 flex items-center gap-2">
                  <span
                    className="h-1.5 w-1.5 shrink-0 rounded-full"
                    style={{ background: `hsl(${colorForKey(b.key)})` }}
                  />
                  <span className="truncate text-sm text-foreground" title={b.key}>
                    {b.label}
                  </span>
                  {dupLabels.has(b.label) && (
                    <span className="shrink-0 font-mono text-[10px] text-muted-foreground/60">
                      {b.key}
                    </span>
                  )}
                  <span className="shrink-0 text-[11px] tabular-nums text-muted-foreground/70">
                    {fmt(b.total)} ACs
                  </span>
                </div>
                <div className="h-2 w-full overflow-hidden rounded-full bg-muted/40">
                  <div
                    className="h-full rounded-full transition-all"
                    style={{ width: `${Math.max(b.pct, b.guarded > 0 ? 2 : 0)}%`, background: `hsl(${tone})` }}
                  />
                </div>
              </div>
              <div className="w-24 text-right">
                <span className="text-sm font-semibold tabular-nums" style={{ color: `hsl(${tone})` }}>
                  {b.pct}%
                </span>
                <span className="ml-1 text-[11px] tabular-nums text-muted-foreground">
                  {fmt(b.guarded)}/{fmt(b.total)}
                </span>
              </div>
            </li>
          );
        })}
      </ul>

      {sorted.length > INITIAL && (
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="mt-4 text-xs font-medium text-primary transition-colors hover:text-primary/80"
        >
          {expanded ? "Show fewer" : `Show all ${fmt(sorted.length)} components`}
        </button>
      )}
    </div>
  );
}
