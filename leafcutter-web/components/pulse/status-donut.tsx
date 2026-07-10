"use client";

import * as React from "react";
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts";
import { fmt } from "@/lib/utils";
import { DonutTooltip, type ChartDatum } from "./chart-primitives";

/**
 * AC work-status breakdown as a donut. Colors come from WORK_STATUS_TONE
 * (passed in via `data[].hsl`); the center reports the live total.
 */
export function StatusDonut({ data, total }: { data: ChartDatum[]; total: number }) {
  const shown = data.filter((d) => d.value > 0);
  return (
    <div className="relative h-[220px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={shown}
            dataKey="value"
            nameKey="label"
            innerRadius={66}
            outerRadius={96}
            paddingAngle={2}
            stroke="hsl(var(--card))"
            strokeWidth={2}
            startAngle={90}
            endAngle={-270}
          >
            {shown.map((d) => (
              <Cell key={d.key} fill={`hsl(${d.hsl})`} />
            ))}
          </Pie>
          <Tooltip content={<DonutTooltip total={total} />} />
        </PieChart>
      </ResponsiveContainer>
      <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
        <div className="text-3xl font-semibold tabular-nums text-foreground">{fmt(total)}</div>
        <div className="eyebrow mt-1">Criteria</div>
      </div>
    </div>
  );
}
