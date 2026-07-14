"use client";

import * as React from "react";
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts";
import { FileWarning, Unlink } from "lucide-react";
import { fmt } from "@/lib/utils";
import { DonutTooltip } from "@/components/pulse/chart-primitives";
import type { OrphanStat } from "./shared";

const ORPHAN_HSL = "356 72% 56%"; // destructive — the untraceable share
const LINKED_HSL = "150 60% 48%"; // leaf green — traces to a requirement

function OrphanDonut({
  orphan,
  linked,
  pct,
  unit,
}: {
  orphan: number;
  linked: number;
  pct: number;
  unit: string;
}) {
  const data = [
    { key: "orphan", label: "Orphan (no AC)", value: orphan, hsl: ORPHAN_HSL },
    { key: "linked", label: "Traces to an AC", value: linked, hsl: LINKED_HSL },
  ].filter((d) => d.value > 0);
  const total = orphan + linked;
  return (
    <div className="relative h-[190px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            dataKey="value"
            nameKey="label"
            innerRadius={58}
            outerRadius={84}
            paddingAngle={2}
            stroke="hsl(var(--card))"
            strokeWidth={2}
            startAngle={90}
            endAngle={-270}
            isAnimationActive={false}
          >
            {data.map((d) => (
              <Cell key={d.key} fill={`hsl(${d.hsl})`} />
            ))}
          </Pie>
          <Tooltip content={<DonutTooltip total={total} />} />
        </PieChart>
      </ResponsiveContainer>
      <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
        <div className="text-3xl font-semibold tabular-nums text-destructive">{pct}%</div>
        <div className="eyebrow mt-0.5">orphan {unit}</div>
      </div>
    </div>
  );
}

/**
 * Orphan tests — test files & functions that name no acceptance criterion, and
 * so cannot be traced back to a requirement. Two donuts (file- and function-
 * level) plus a sample of orphan files. Reframes the coverage view's second
 * honest signal: a test can pass without anyone knowing what it proves.
 */
export function OrphanTests({ stat }: { stat: OrphanStat }) {
  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_1fr_minmax(0,1.1fr)]">
      {/* File-level donut */}
      <div className="flex flex-col">
        <OrphanDonut
          orphan={stat.orphanFiles}
          linked={stat.linkedFiles}
          pct={stat.orphanFilePct}
          unit="files"
        />
        <p className="mt-1 text-center text-xs text-muted-foreground">
          <span className="font-semibold text-destructive">{fmt(stat.orphanFiles)}</span> of{" "}
          {fmt(stat.files)} test files name no AC
        </p>
      </div>

      {/* Function-level donut */}
      <div className="flex flex-col">
        <OrphanDonut
          orphan={stat.orphanFns}
          linked={stat.linkedFns}
          pct={stat.orphanFnPct}
          unit="functions"
        />
        <p className="mt-1 text-center text-xs text-muted-foreground">
          <span className="font-semibold text-destructive">{fmt(stat.orphanFns)}</span> of{" "}
          {fmt(stat.fns)} test functions name no AC
        </p>
      </div>

      {/* Sample list */}
      <div className="rounded-xl border border-border/70 bg-card/40 p-4">
        <div className="eyebrow mb-2 flex items-center gap-1.5">
          <FileWarning className="h-3.5 w-3.5 text-destructive" />
          Orphan test files — sample
        </div>
        <ul className="space-y-1.5">
          {stat.orphanFileSamples.map((f) => (
            <li key={f} className="flex items-start gap-2 text-[11px]">
              <Unlink className="mt-0.5 h-3 w-3 shrink-0 text-destructive/70" />
              <span className="truncate font-mono text-muted-foreground" title={f}>
                {f}
              </span>
            </li>
          ))}
        </ul>
        <p className="mt-3 border-t border-border/50 pt-2 text-[11px] leading-relaxed text-muted-foreground/80">
          These tests exist and may pass — but nothing links them to a requirement, so a green run
          proves nothing traceable. The fix is a referenced AC id in the test.
        </p>
      </div>
    </div>
  );
}
