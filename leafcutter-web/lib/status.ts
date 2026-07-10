/**
 * Shared status & category vocabulary — the single source of truth for how
 * work-status, level, priority, and readiness map to colors and labels across
 * EVERY view (badges, charts, graph nodes, legends). Pure / client-safe.
 *
 * Colors are given both as a Tailwind token class set (for DOM) and a raw HSL
 * string (for canvas/SVG contexts like React Flow & Recharts).
 */
import type { AcLevel, Priority, Readiness, WorkStatus } from "./data/types";

export interface Tone {
  label: string;
  hsl: string;          // e.g. "150 60% 48%" (channels, wrap with hsl())
  text: string;         // tailwind text class
  bg: string;           // tailwind bg tint class
  border: string;       // tailwind border class
  dot: string;          // tailwind bg class for a solid dot
}

const tone = (
  label: string,
  hsl: string,
  text: string,
  bg: string,
  border: string,
  dot: string,
): Tone => ({ label, hsl, text, bg, border, dot });

export const WORK_STATUS_TONE: Record<WorkStatus, Tone> = {
  done: tone("Done", "150 60% 48%", "text-success", "bg-success/10", "border-success/30", "bg-success"),
  in_progress: tone("In progress", "38 92% 58%", "text-warning", "bg-warning/10", "border-warning/30", "bg-warning"),
  todo: tone("Ready", "205 78% 60%", "text-info", "bg-info/10", "border-info/30", "bg-info"),
  not_started: tone("Not started", "150 8% 60%", "text-muted-foreground", "bg-muted/40", "border-border", "bg-muted-foreground"),
  blocked: tone("Blocked", "356 72% 56%", "text-destructive", "bg-destructive/10", "border-destructive/30", "bg-destructive"),
  unknown: tone("Unknown", "150 8% 45%", "text-muted-foreground", "bg-muted/30", "border-border", "bg-muted-foreground/60"),
};

export const LEVEL_TONE: Record<AcLevel, Tone> = {
  L0: tone("L0 · Value", "265 60% 66%", "text-chart-4", "bg-chart-4/10", "border-chart-4/30", "bg-chart-4"),
  L1: tone("L1 · Feature", "200 78% 60%", "text-chart-5", "bg-chart-5/10", "border-chart-5/30", "bg-chart-5"),
  L2: tone("L2 · Behavior", "150 64% 52%", "text-chart-1", "bg-chart-1/10", "border-chart-1/30", "bg-chart-1"),
  L3: tone("L3 · Edge case", "168 60% 46%", "text-chart-2", "bg-chart-2/10", "border-chart-2/30", "bg-chart-2"),
};

export const PRIORITY_TONE: Record<Priority, Tone> = {
  critical: tone("Critical", "356 72% 56%", "text-destructive", "bg-destructive/10", "border-destructive/30", "bg-destructive"),
  high: tone("High", "38 92% 58%", "text-warning", "bg-warning/10", "border-warning/30", "bg-warning"),
  medium: tone("Medium", "205 78% 60%", "text-info", "bg-info/10", "border-info/30", "bg-info"),
  low: tone("Low", "150 8% 60%", "text-muted-foreground", "bg-muted/40", "border-border", "bg-muted-foreground"),
  unknown: tone("—", "150 8% 45%", "text-muted-foreground", "bg-muted/30", "border-border", "bg-muted-foreground/60"),
};

export const READINESS_TONE: Record<Readiness, Tone> = {
  approved: tone("Approved", "150 60% 48%", "text-success", "bg-success/10", "border-success/30", "bg-success"),
  reviewed: tone("Reviewed", "205 78% 60%", "text-info", "bg-info/10", "border-info/30", "bg-info"),
  draft: tone("Draft", "150 8% 60%", "text-muted-foreground", "bg-muted/40", "border-border", "bg-muted-foreground"),
  unknown: tone("—", "150 8% 45%", "text-muted-foreground", "bg-muted/30", "border-border", "bg-muted-foreground/60"),
};

/** Categorical palette for arbitrary keys (component types, agent categories). */
export const CATEGORICAL_HSL = [
  "150 64% 52%", "168 60% 46%", "38 92% 58%", "265 60% 66%",
  "200 78% 60%", "20 80% 60%", "320 55% 62%", "96 50% 55%",
  "48 90% 60%", "230 60% 66%",
];

/** Deterministic color for a free-form key (stable across renders). */
export function colorForKey(key: string): string {
  let h = 0;
  for (let i = 0; i < key.length; i++) h = (h * 31 + key.charCodeAt(i)) >>> 0;
  return CATEGORICAL_HSL[h % CATEGORICAL_HSL.length];
}
