import * as React from "react";
import { ShieldAlert, CheckCircle2 } from "lucide-react";
import { fmt, humanize } from "@/lib/utils";
import { LEVEL_TONE } from "@/lib/status";
import { Badge, EmptyState } from "@/components/ui/kit";
import type { CoverageRow } from "./shared";

/**
 * The actionable risk list: acceptance criteria marked DONE that have zero
 * directly-guarding test. These shipped without a guard — the single most
 * useful thing this whole view surfaces. Server-safe (no hooks).
 */
export function GapsCallout({
  rows,
  total,
  cap,
}: {
  rows: CoverageRow[];
  total: number;
  cap: number;
}) {
  if (total === 0) {
    return (
      <EmptyState
        icon={<CheckCircle2 className="h-8 w-8" />}
        title="Every done AC has a guarding test"
        hint="No acceptance criterion is marked done while carrying zero directly-guarding tests."
      />
    );
  }

  const shown = rows.slice(0, cap);

  return (
    <div>
      <div className="mb-4 flex items-start gap-3 rounded-lg border border-destructive/25 bg-destructive/[0.06] p-4">
        <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0 text-destructive" />
        <div>
          <p className="text-sm font-medium text-foreground">
            {fmt(total)} criteria are marked <span className="text-success">done</span> with{" "}
            <span className="text-destructive">no directly-guarding test</span>.
          </p>
          <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
            These behaviours were built and signed off, yet nothing in the test suite names
            them. A regression here would pass CI silently. Rolled-up counts note where a
            composite parent is instead covered through its child criteria.
          </p>
        </div>
      </div>

      <ul className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        {shown.map((r) => {
          const lvl = LEVEL_TONE[r.level];
          const viaChildren = !r.isLeaf && r.testRolledUpCount > 0;
          return (
            <li
              key={r.id}
              className="flex items-center gap-3 rounded-lg border border-border/60 bg-card/40 px-3 py-2.5"
            >
              <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-destructive" />
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm text-foreground" title={r.title}>
                  {r.title}
                </div>
                <div className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[11px] text-muted-foreground">
                  <span className="font-mono text-muted-foreground/80">{r.id}</span>
                  <span>·</span>
                  <span>{humanize(r.component)}</span>
                  {viaChildren && (
                    <span className="text-warning">· {r.testRolledUpCount} via children</span>
                  )}
                </div>
              </div>
              <Badge tone={lvl} className="shrink-0">
                {r.level}
              </Badge>
            </li>
          );
        })}
      </ul>

      {total > shown.length && (
        <p className="mt-3 text-xs text-muted-foreground">
          Showing {fmt(shown.length)} of {fmt(total)} — filter the full explorer below with{" "}
          <span className="font-medium text-foreground">Done but unguarded</span> to see them all.
        </p>
      )}
    </div>
  );
}
