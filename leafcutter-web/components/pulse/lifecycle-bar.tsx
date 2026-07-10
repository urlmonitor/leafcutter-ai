"use client";

import * as React from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Cell,
  ResponsiveContainer,
  Tooltip,
  LabelList,
} from "recharts";
import { fmt } from "@/lib/utils";
import { BarTooltip, type ChartDatum } from "./chart-primitives";

/**
 * Tickets by lifecycle (done / epic / inbox / other) as vertical bars — the
 * delivery throughput split. Colors passed in via `data[].hsl`.
 */
export function LifecycleBar({ data }: { data: ChartDatum[] }) {
  return (
    <div className="h-[220px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 22, right: 8, bottom: 0, left: 8 }} barCategoryGap="24%">
          <XAxis
            dataKey="label"
            tickLine={false}
            axisLine={false}
            tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }}
          />
          <YAxis hide domain={[0, "dataMax"]} />
          <Tooltip cursor={{ fill: "hsl(var(--muted) / 0.3)" }} content={<BarTooltip />} />
          <Bar dataKey="value" radius={[5, 5, 0, 0]} maxBarSize={64} isAnimationActive={false}>
            {data.map((d) => (
              <Cell key={d.key} fill={`hsl(${d.hsl})`} />
            ))}
            <LabelList
              dataKey="value"
              position="top"
              formatter={(value) => fmt(Number(value))}
              fill="hsl(var(--foreground))"
              fontSize={12}
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
