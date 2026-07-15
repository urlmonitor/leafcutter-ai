import * as React from "react";
import { ShieldCheck } from "lucide-react";
import { fmt } from "@/lib/utils";
import { Panel } from "@/components/ui/kit";
import { gradeLabel, type ScoreTile } from "./shared";

/**
 * The headline traceability-health metric: guard coverage over the LOGICAL
 * denominator — SHIPPED (done) ACs — not the whole store. Leads with the big
 * percentage, then breaks the done population into guarded vs unguarded, and
 * notes the leaf-only figure (leaves are the directly-testable behaviours).
 * Server-safe (no hooks).
 */
export function HeadlineGuard({
  pct,
  guarded,
  unguarded,
  total,
  leafPct,
  leafGuarded,
  leafTotal,
  hsl,
}: {
  pct: number;
  guarded: number;
  unguarded: number;
  total: number;
  leafPct: number;
  leafGuarded: number;
  leafTotal: number;
  hsl: string;
}) {
  const guardW = total ? (guarded / total) * 100 : 0;
  return (
    <Panel className="relative overflow-hidden">
      <div
        className="pointer-events-none absolute -right-10 -top-16 h-56 w-56 rounded-full opacity-[0.14] blur-3xl"
        style={{ background: `hsl(${hsl})` }}
      />
      <div className="grid gap-8 lg:grid-cols-[minmax(0,340px)_1fr] lg:items-center">
        {/* The big number */}
        <div>
          <div className="eyebrow mb-2 flex items-center gap-1.5">
            <ShieldCheck className="h-3.5 w-3.5" style={{ color: `hsl(${hsl})` }} />
            Shipped-AC guard coverage
          </div>
          <div className="flex items-end gap-3">
            <span
              className="text-6xl font-semibold leading-none tracking-tight tabular-nums"
              style={{ color: `hsl(${hsl})` }}
            >
              {pct}%
            </span>
            <span className="mb-1 text-sm text-muted-foreground">
              of shipped
              <br />
              ACs are guarded
            </span>
          </div>
          <p className="mt-3 max-w-sm text-sm leading-relaxed text-muted-foreground">
            Of the <span className="font-semibold text-foreground">{fmt(total)}</span> acceptance
            criteria that are actually <span className="text-success">done</span>, only{" "}
            <span className="font-semibold text-foreground">{fmt(guarded)}</span> are named by a
            test. Measured over shipped work — the logical denominator — not the whole store.
          </p>
          <p className="mt-2 text-xs text-muted-foreground">
            Leaf criteria (directly testable):{" "}
            <span className="font-semibold" style={{ color: `hsl(${hsl})` }}>
              {leafPct}%
            </span>{" "}
            — {fmt(leafGuarded)} of {fmt(leafTotal)} guarded.
          </p>
        </div>

        {/* Guarded vs unguarded split of the shipped population */}
        <div>
          <div className="mb-2 flex items-baseline justify-between text-xs text-muted-foreground">
            <span>Shipped acceptance criteria</span>
            <span className="tabular-nums">{fmt(total)} done</span>
          </div>
          <div className="flex h-8 w-full overflow-hidden rounded-lg border border-border/60">
            <div
              className="flex items-center justify-center text-[11px] font-semibold text-background"
              style={{ width: `${Math.max(guardW, 6)}%`, background: `hsl(${hsl})` }}
              title={`${guarded} guarded`}
            >
              {guarded}
            </div>
            <div
              className="flex flex-1 items-center justify-center bg-destructive/15 text-[11px] font-semibold text-destructive"
              title={`${unguarded} unguarded`}
            >
              {fmt(unguarded)} unguarded
            </div>
          </div>
          <div className="mt-3 grid grid-cols-2 gap-3">
            <div className="rounded-lg border border-border/60 bg-card/40 px-3 py-2.5">
              <div className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
                <span className="h-2 w-2 rounded-[3px]" style={{ background: `hsl(${hsl})` }} />
                Guarded
              </div>
              <div className="mt-0.5 text-xl font-semibold tabular-nums text-foreground">
                {fmt(guarded)}
              </div>
            </div>
            <div className="rounded-lg border border-destructive/25 bg-destructive/[0.06] px-3 py-2.5">
              <div className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
                <span className="h-2 w-2 rounded-[3px] bg-destructive" />
                Unguarded — regression-blind
              </div>
              <div className="mt-0.5 text-xl font-semibold tabular-nums text-destructive">
                {fmt(unguarded)}
              </div>
            </div>
          </div>
        </div>
      </div>
    </Panel>
  );
}

/** A 2×2 / 1×4 row of graded health tiles. Server-safe. */
export function HealthScorecard({ tiles }: { tiles: ScoreTile[] }) {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {tiles.map((t) => {
        const grade = gradeLabel(t.hsl);
        return (
          <Panel key={t.key} className="relative flex flex-col overflow-hidden">
            <div
              className="pointer-events-none absolute -right-6 -top-8 h-20 w-20 rounded-full opacity-20 blur-2xl"
              style={{ background: `hsl(${t.hsl})` }}
            />
            <div className="flex items-start justify-between gap-2">
              <div className="eyebrow">{t.label}</div>
              <span
                className="shrink-0 rounded-full border px-1.5 py-0.5 text-[10px] font-medium"
                style={{
                  color: `hsl(${t.hsl})`,
                  borderColor: `hsl(${t.hsl} / 0.35)`,
                  background: `hsl(${t.hsl} / 0.1)`,
                }}
              >
                {grade}
              </span>
            </div>
            <div
              className="mt-2 text-3xl font-semibold tracking-tight tabular-nums"
              style={{ color: `hsl(${t.hsl})` }}
            >
              {t.value}
            </div>
            <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-muted/50">
              <div
                className="h-full rounded-full"
                style={{ width: `${Math.max(2, Math.min(100, t.meter))}%`, background: `hsl(${t.hsl})` }}
              />
            </div>
            <div className="mt-2 text-xs text-muted-foreground">{t.sub}</div>
            {t.detail && (
              <div className="mt-auto pt-1.5 text-[11px] text-muted-foreground/70">{t.detail}</div>
            )}
          </Panel>
        );
      })}
    </div>
  );
}
