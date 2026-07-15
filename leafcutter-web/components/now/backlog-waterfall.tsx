"use client";

import * as React from "react";
import { motion } from "framer-motion";
import { ArrowRight } from "lucide-react";
import { fmt } from "@/lib/utils";
import type { WaterfallRow } from "./types";

/** Botanical tone per waterfall bucket (HSL channels). */
const BUCKET_HSL: Record<string, string> = {
  not_done: "150 14% 78%", // pale canopy light — the raw total
  composite: "265 60% 66%", // orchid — roll-up parents
  superseded: "150 8% 48%", // slate — dead
  built_unflipped: "38 92% 58%", // amber — delivered, stale status
  draft: "150 8% 60%", // slate-light
  untriaged: "205 78% 60%", // sky — needs triage
  blocked: "356 72% 56%", // red — waiting on deps
  ready: "150 60% 48%", // leaf green — the truth
};

function Row({
  row,
  max,
  index,
}: {
  row: WaterfallRow;
  max: number;
  index: number;
}) {
  const hsl = BUCKET_HSL[row.bucket] ?? "150 8% 55%";
  const isBase = row.bucket === "not_done";
  const isFinal = row.bucket === "ready";
  const widthPct = max > 0 ? Math.max(2, (row.count / max) * 100) : 0;

  return (
    <div className={isFinal ? "pt-2" : undefined}>
      <div className="mb-1 flex items-baseline justify-between gap-3">
        <div className="flex items-baseline gap-2">
          <span
            className={
              isBase || isFinal
                ? "text-sm font-semibold tracking-tight text-foreground"
                : "text-sm text-muted-foreground"
            }
          >
            {row.label}
          </span>
        </div>
        <span
          className={
            isFinal
              ? "text-lg font-semibold tabular-nums text-success"
              : "text-sm font-medium tabular-nums text-foreground"
          }
        >
          {isBase || isFinal ? "" : "−"}
          {fmt(row.count)}
        </span>
      </div>
      <div className="relative h-3 w-full overflow-hidden rounded-full bg-muted/40">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${widthPct}%` }}
          transition={{ duration: 0.7, delay: index * 0.06, ease: [0.22, 1, 0.36, 1] }}
          className="h-full rounded-full"
          style={{
            background: `hsl(${hsl} / ${isBase || isFinal ? 0.95 : 0.6})`,
            boxShadow: isFinal ? `0 0 18px -2px hsl(${hsl} / 0.6)` : undefined,
          }}
        />
      </div>
      <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground/80">{row.description}</p>
    </div>
  );
}

export function BacklogWaterfall({
  rows,
  nextUpCount,
}: {
  rows: WaterfallRow[];
  nextUpCount: number;
}) {
  const notDone = rows.find((r) => r.bucket === "not_done")?.count ?? 0;
  const ready = rows.find((r) => r.bucket === "ready")?.count ?? 0;
  const max = notDone || Math.max(...rows.map((r) => r.count), 1);
  const collapsePct = notDone > 0 ? Math.round((ready / notDone) * 100) : 0;

  return (
    <div className="grid gap-8 lg:grid-cols-[1fr_260px]">
      {/* The funnel */}
      <div className="space-y-4">
        {rows.map((row, i) => (
          <Row key={row.bucket} row={row} max={max} index={i} />
        ))}
      </div>

      {/* The takeaway */}
      <div className="flex flex-col justify-center gap-4 rounded-xl border border-border/70 bg-card/40 p-5">
        <div className="eyebrow">The honest read</div>
        <div className="flex items-center gap-3">
          <div>
            <div className="text-2xl font-semibold tabular-nums text-muted-foreground line-through decoration-destructive/50 decoration-2">
              {fmt(notDone)}
            </div>
            <div className="text-[11px] text-muted-foreground">raw not-done</div>
          </div>
          <ArrowRight className="h-4 w-4 shrink-0 text-muted-foreground/60" />
          <div>
            <div className="text-3xl font-semibold tabular-nums text-success">{fmt(ready)}</div>
            <div className="text-[11px] text-muted-foreground">genuinely ready</div>
          </div>
        </div>
        <div className="flex items-center gap-2 rounded-lg border border-primary/30 bg-primary/[0.06] px-3 py-2">
          <span className="text-xl font-semibold tabular-nums text-primary">{fmt(nextUpCount)}</span>
          <span className="text-[11px] leading-tight text-muted-foreground">
            auto-pickable next by <span className="font-mono text-primary/90">/build-ac</span>
          </span>
        </div>
        <p className="text-[11px] leading-relaxed text-muted-foreground">
          The scary top-line collapses to just{" "}
          <span className="font-medium text-success">{collapsePct}%</span> once roll-up parents,
          superseded records, untriaged and blocked leaves are removed. Only what remains can
          actually be built today.
        </p>
      </div>
    </div>
  );
}
