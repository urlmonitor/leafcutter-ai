"use client";

/**
 * Presentational pieces of the Flows view: level chip, step rollup, realization
 * banner and the 'not found' notice.
 */
import * as React from "react";
import Link from "next/link";
import { Badge } from "@/components/ui/kit";
import { humanize } from "@/lib/utils";
import { WORK_STATUS_TONE } from "@/lib/status";
import type { Flow, FlowLevel } from "@/lib/data/types";
import { RealizationBadge, realizationMeta } from "../realization-badge";
import { Layers } from "lucide-react";

// HSL accents for the flow-level chip (journey → pipeline → agent = drill deeper).
const LEVEL_HSL: Record<FlowLevel, string> = {
  journey: "205 78% 60%",
  pipeline: "150 64% 52%",
  agent: "265 60% 66%",
};

export function LevelChip({ level }: { level: FlowLevel }) {
  const hsl = LEVEL_HSL[level];
  return (
    <span
      className="inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium"
      style={{
        color: `hsl(${hsl})`,
        background: `hsl(${hsl} / 0.12)`,
        borderColor: `hsl(${hsl} / 0.3)`,
      }}
      title={`Flow level: ${level}`}
    >
      <Layers className="h-3 w-3" />
      {humanize(level)}
    </span>
  );
}

/** Shown instead of a flow when the requested address names none (404). */
export interface FlowsViewNotice {
  title: string;
  detail: string;
  actionLabel: string;
  actionHref: string;
}

/**
 * Step rollup is meaningless for a stepless architecture map — it rendered
 * "0 done · 0 in progress · 0 not started of 0 steps", a fabricated progress
 * claim. Suppressed for architecture kinds.
 */
export function StepRollup({ flow }: { flow: Flow }) {
  const s = flow.implSummary;
  if (!s || flow.kind === "architecture") return null;
  return (
    <div className="flex flex-wrap items-center justify-end gap-1.5">
      {flow.realization !== "built" && (
        <RealizationBadge realization={flow.realization} className="mr-1" />
      )}
      <Badge tone={WORK_STATUS_TONE.done} dot>
        {s.done} done
      </Badge>
      <Badge tone={WORK_STATUS_TONE.in_progress} dot>
        {s.in_progress} in progress
      </Badge>
      <Badge tone={WORK_STATUS_TONE.not_started} dot>
        {s.not_started} not started
      </Badge>
      <span className="ml-1 text-xs text-muted-foreground">
        of <span className="font-mono tabular-nums text-foreground">{s.total}</span> steps
      </span>
    </div>
  );
}

/**
 * Realization banner — never let a reviewer read a spec/sample flow as a live map.
 * Excluded for architecture maps: the banner asserts "the system it maps does
 * not exist yet", which is false for a schema of the live repo.
 */
export function RealizationBanner({ flow }: { flow: Flow }) {
  if (flow.realization === "built" || flow.kind === "architecture") return null;
  const meta = realizationMeta(flow.realization);
  if (!meta) return null;
  return (
      <div
        className="mb-4 flex items-start gap-3 rounded-lg border px-4 py-3"
        style={{
          borderColor: `hsl(${meta.hsl} / 0.5)`,
          background: `hsl(${meta.hsl} / 0.1)`,
        }}
      >
        <RealizationBadge realization={flow.realization} />
        <p className="text-sm leading-relaxed text-foreground/90">
          {meta.description}{" "}
          <span className="text-muted-foreground">
            The step colours below track whether each step&apos;s acceptance
            criteria are authored — not whether this system is running.
          </span>
        </p>
      </div>
  );
}

export function FlowNotice({ notice }: { notice: FlowsViewNotice }) {
  return (
    <div role="alert" className="rounded-lg border border-border/70 bg-card/60 p-6">
      <h2 className="text-lg font-semibold text-foreground">{notice.title}</h2>
      <p className="mt-2 max-w-2xl break-words text-sm text-muted-foreground">
        {notice.detail}
      </p>
      <Link
        href={notice.actionHref}
        className="mt-4 inline-flex rounded-md bg-primary/15 px-3 py-1.5 text-sm font-medium text-foreground transition-colors hover:bg-primary/25"
      >
        {notice.actionLabel}
      </Link>
    </div>
  );
}

/** A known flow opened with a `?step=` that names no step or branch (not a 404). */
export function StepNotice({ detail }: { detail: string }) {
  return (
    <div role="status" className="mb-4 rounded-lg border border-warning/40 bg-warning/10 px-4 py-3">
      <h2 className="text-sm font-semibold text-foreground">Step not found</h2>
      <p className="mt-1 break-words text-sm text-muted-foreground">{detail}</p>
    </div>
  );
}
