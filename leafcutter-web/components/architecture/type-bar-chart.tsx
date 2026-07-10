"use client";

import * as React from "react";
import {
  Bar,
  BarChart,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { TypeStat } from "./lib";

interface Row {
  label: string;
  count: number;
  documented: number;
  hsl: string;
}

export function TypeBarChart({ data }: { data: TypeStat[] }) {
  const rows: Row[] = data.map((d) => ({
    label: d.label,
    count: d.count,
    documented: d.documented,
    hsl: d.hsl,
  }));

  return (
    <div className="h-[280px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={rows}
          layout="vertical"
          margin={{ top: 4, right: 16, bottom: 4, left: 8 }}
          barCategoryGap={10}
        >
          <XAxis
            type="number"
            allowDecimals={false}
            tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 11 }}
            axisLine={{ stroke: "hsl(var(--border))" }}
            tickLine={false}
          />
          <YAxis
            type="category"
            dataKey="label"
            width={104}
            tick={{ fill: "hsl(var(--foreground))", fontSize: 12 }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip cursor={{ fill: "hsl(var(--muted) / 0.4)" }} content={<ChartTooltip />} />
          <Bar dataKey="count" radius={[0, 5, 5, 0]} maxBarSize={22} isAnimationActive={false}>
            {rows.map((r) => (
              <Cell key={r.label} fill={`hsl(${r.hsl})`} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function ChartTooltip({ active, payload }: { active?: boolean; payload?: { payload: Row }[] }) {
  if (!active || !payload?.length) return null;
  const r = payload[0].payload;
  return (
    <div className="rounded-lg border border-border/80 bg-popover/95 px-3 py-2 text-xs shadow-xl backdrop-blur">
      <div className="mb-1 flex items-center gap-1.5 font-medium text-foreground">
        <span className="h-2 w-2 rounded-[3px]" style={{ background: `hsl(${r.hsl})` }} />
        {r.label}
      </div>
      <div className="tabular-nums text-muted-foreground">
        <span className="text-foreground">{r.count}</span> components
      </div>
      <div className="tabular-nums text-muted-foreground">
        <span className="text-foreground">{r.documented}</span> documented
      </div>
    </div>
  );
}
