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
 * AC level distribution (L0 -> L3) as horizontal bars — reveals the pyramid
 * where L2 behaviors dominate. Colors from LEVEL_TONE via `data[].hsl`.
 */
export function LevelsBar({ data }: { data: ChartDatum[] }) {
  return (
    <div className="h-[220px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={data}
          layout="vertical"
          margin={{ top: 4, right: 44, bottom: 0, left: 4 }}
          barCategoryGap={12}
        >
          <XAxis type="number" hide domain={[0, "dataMax"]} />
          <YAxis
            type="category"
            dataKey="label"
            width={40}
            tickLine={false}
            axisLine={false}
            tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }}
          />
          <Tooltip cursor={{ fill: "hsl(var(--muted) / 0.3)" }} content={<BarTooltip />} />
          <Bar
            dataKey="value"
            radius={4}
            maxBarSize={26}
            background={{ fill: "hsl(var(--muted) / 0.25)" }}
            isAnimationActive={false}
          >
            {data.map((d) => (
              <Cell key={d.key} fill={`hsl(${d.hsl})`} />
            ))}
            <LabelList
              dataKey="value"
              position="right"
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
