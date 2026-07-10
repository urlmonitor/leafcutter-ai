"use client";

import * as React from "react";
import { fmt, pct } from "@/lib/utils";

/** One plottable datum shared by every Pulse chart. Plain-serializable. */
export interface ChartDatum {
  key: string;
  label: string;
  value: number;
  hsl: string; // HSL channels, e.g. "150 64% 52%"
}

/** Recharts injects these into a Tooltip `content` element. */
interface TipPayloadEntry {
  name?: string | number;
  value?: string | number;
  color?: string;
  payload?: ChartDatum;
}
interface TipProps {
  active?: boolean;
  payload?: TipPayloadEntry[];
  total?: number;
}

function TipShell({
  swatch,
  name,
  value,
  total,
}: {
  swatch: string;
  name: React.ReactNode;
  value: number;
  total?: number;
}) {
  return (
    <div className="rounded-lg border border-border bg-popover/95 px-3 py-2 text-xs shadow-xl backdrop-blur">
      <div className="flex items-center gap-2">
        <span className="h-2 w-2 rounded-[3px]" style={{ background: swatch }} />
        <span className="font-medium text-foreground">{name}</span>
      </div>
      <div className="mt-1 tabular-nums text-muted-foreground">
        {fmt(value)}
        {typeof total === "number" && total > 0 ? ` · ${pct(value, total)}%` : null}
      </div>
    </div>
  );
}

/** Tooltip for the status donut (shows share of total). */
export function DonutTooltip({ active, payload, total }: TipProps) {
  if (!active || !payload || payload.length === 0) return null;
  const p = payload[0];
  const datum = p.payload;
  const swatch = datum ? `hsl(${datum.hsl})` : p.color ?? "currentColor";
  return (
    <TipShell swatch={swatch} name={p.name ?? datum?.label ?? ""} value={Number(p.value ?? 0)} total={total} />
  );
}

/** Tooltip for bar charts (levels, lifecycle). */
export function BarTooltip({ active, payload }: TipProps) {
  if (!active || !payload || payload.length === 0) return null;
  const p = payload[0];
  const datum = p.payload;
  const swatch = datum ? `hsl(${datum.hsl})` : p.color ?? "currentColor";
  return (
    <TipShell swatch={swatch} name={datum?.label ?? p.name ?? ""} value={Number(p.value ?? 0)} />
  );
}
