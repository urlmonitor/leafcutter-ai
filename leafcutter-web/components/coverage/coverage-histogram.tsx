"use client";

import * as React from "react";
import {
  Bar,
  BarChart,
  Cell,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { fmt, pct } from "@/lib/utils";
import type { HistogramDatum } from "./shared";

/**
 * Distribution of ACs by how many tests DIRECTLY guard them (0 / 1 / 2 / 3+).
 * The "0" bar is the story — it is deliberately coloured red so the size of the
 * unguarded population is impossible to miss.
 */
function HistTooltip({
  active,
  payload,
  total,
}: {
  active?: boolean;
  payload?: { payload: HistogramDatum }[];
  total: number;
}) {
  if (!active || !payload || payload.length === 0) return null;
  const d = payload[0].payload;
  const label = d.bucket === "0" ? "0 tests" : d.bucket === "3+" ? "3+ tests" : `${d.bucket} test${d.bucket === "1" ? "" : "s"}`;
  return (
    <div className="panel px-3 py-2 text-xs">
      <div className="flex items-center gap-2 font-medium text-foreground">
        <span className="h-2 w-2 rounded-[3px]" style={{ background: `hsl(${d.hsl})` }} />
        {label}
      </div>
      <div className="mt-0.5 tabular-nums text-muted-foreground">
        {fmt(d.count)} ACs · {pct(d.count, total)}% of all criteria
      </div>
    </div>
  );
}

export function CoverageHistogram({ data }: { data: HistogramDatum[] }) {
  const total = data.reduce((s, d) => s + d.count, 0);
  return (
    <div className="h-[240px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 26, right: 8, bottom: 4, left: 4 }} barCategoryGap="22%">
          <XAxis
            dataKey="bucket"
            tickLine={false}
            axisLine={false}
            tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }}
            tickFormatter={(b) => (b === "0" ? "0 tests" : b === "3+" ? "3+ tests" : b)}
          />
          <YAxis hide domain={[0, "dataMax"]} />
          <Tooltip cursor={{ fill: "hsl(var(--muted) / 0.3)" }} content={<HistTooltip total={total} />} />
          <Bar dataKey="count" radius={[6, 6, 0, 0]} isAnimationActive={false} maxBarSize={120}>
            {data.map((d) => (
              <Cell key={d.bucket} fill={`hsl(${d.hsl})`} />
            ))}
            <LabelList
              dataKey="count"
              position="top"
              formatter={(v) => fmt(Number(v))}
              fill="hsl(var(--foreground))"
              fontSize={13}
              fontWeight={600}
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
