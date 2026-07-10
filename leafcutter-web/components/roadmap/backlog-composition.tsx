"use client";

import * as React from "react";
import Link from "next/link";
import { ArrowUpRight } from "lucide-react";
import {
  Bar,
  BarChart,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Legend } from "@/components/ui/kit";

export type CompositionDatum = {
  label: string;
  value: number;
  hsl: string;
  desc?: string;
};

const AXIS_COLOR = "hsl(150 8% 60%)";

function ChartTooltip({
  active,
  payload,
  total,
}: {
  active?: boolean;
  payload?: { payload: CompositionDatum }[];
  total: number;
}) {
  if (!active || !payload || payload.length === 0) return null;
  const d = payload[0].payload;
  const share = total ? Math.round((d.value / total) * 100) : 0;
  return (
    <div className="panel max-w-[15rem] px-3 py-2 text-xs">
      <div className="flex items-center gap-2 font-medium text-foreground">
        <span className="h-2 w-2 rounded-[3px]" style={{ background: `hsl(${d.hsl})` }} />
        {d.label}
      </div>
      <div className="mt-0.5 tabular-nums text-muted-foreground">
        {d.value.toLocaleString("en-US")} ACs · {share}%
      </div>
      {d.desc && <div className="mt-1 leading-snug text-muted-foreground/80">{d.desc}</div>}
    </div>
  );
}

function Chart({ data, labelWidth = 82 }: { data: CompositionDatum[]; labelWidth?: number }) {
  const total = data.reduce((s, d) => s + d.value, 0);
  const height = Math.max(96, data.length * 40);
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart
        data={data}
        layout="vertical"
        margin={{ top: 2, right: 16, bottom: 2, left: 0 }}
        barCategoryGap="26%"
      >
        <XAxis type="number" hide />
        <YAxis
          type="category"
          dataKey="label"
          width={labelWidth}
          tickLine={false}
          axisLine={false}
          tick={{ fill: AXIS_COLOR, fontSize: 12 }}
        />
        <Tooltip
          cursor={{ fill: "hsl(156 14% 13% / 0.5)" }}
          content={<ChartTooltip total={total} />}
        />
        <Bar dataKey="value" radius={[0, 5, 5, 0]} maxBarSize={22} isAnimationActive={false}>
          {data.map((d) => (
            <Cell key={d.label} fill={`hsl(${d.hsl})`} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

export function BacklogComposition({
  bucketData,
  priorityData,
  buildableLeaves,
  readyCount,
}: {
  bucketData: CompositionDatum[];
  priorityData: CompositionDatum[];
  buildableLeaves: number;
  readyCount: number;
}) {
  return (
    <div className="space-y-6">
      <div className="grid gap-6 lg:grid-cols-2">
        <div>
          <div className="mb-1 flex items-baseline justify-between">
            <h3 className="text-sm font-semibold tracking-tight text-foreground">
              Not-done ACs by bucket
            </h3>
            <span className="text-xs tabular-nums text-muted-foreground">
              {readyCount.toLocaleString("en-US")} ready ·{" "}
              {buildableLeaves.toLocaleString("en-US")} buildable leaves
            </span>
          </div>
          <p className="mb-3 text-xs text-muted-foreground">
            Honest classification — why the raw todo pile is not the buildable backlog.
          </p>
          <Chart data={bucketData} labelWidth={112} />
          <Legend className="mt-3" items={bucketData} />
        </div>

        <div>
          <div className="mb-1 flex items-baseline justify-between">
            <h3 className="text-sm font-semibold tracking-tight text-foreground">
              Open ACs by priority
            </h3>
            <span className="text-xs tabular-nums text-muted-foreground">context</span>
          </div>
          <p className="mb-3 text-xs text-muted-foreground">
            How the not-done pile skews by priority — not all of it is buildable.
          </p>
          <Chart data={priorityData} />
          <Legend className="mt-3" items={priorityData} />
        </div>
      </div>

      <div className="border-t border-border/60 pt-3 text-xs text-muted-foreground">
        <Link
          href="/now"
          className="inline-flex items-center gap-1 text-primary/90 transition-colors hover:text-primary"
        >
          See the full backlog waterfall and built-but-unflipped list on Now &amp; Next
          <ArrowUpRight className="h-3 w-3" />
        </Link>
      </div>
    </div>
  );
}
