import * as React from "react";
import { AlertTriangle } from "lucide-react";
import { fmt } from "@/lib/utils";
import type { CoverageBar } from "./shared";

/**
 * Guarded-vs-total per flight level (L0 → L3). Each row is a track sized to the
 * level's AC count, filled to its guarded share and coloured by LEVEL_TONE.
 * The lowest-covered level is spotlighted as the hole. Server-safe (no hooks).
 */
export function LevelCoverage({ bars }: { bars: CoverageBar[] }) {
  const maxTotal = Math.max(1, ...bars.map((b) => b.total));
  const worst = bars.reduce((lo, b) => (b.pct < lo.pct ? b : lo), bars[0]);

  return (
    <div className="space-y-4">
      {bars.map((b) => {
        const trackW = (b.total / maxTotal) * 100;
        const fillW = b.total ? (b.guarded / b.total) * 100 : 0;
        const isWorst = worst && b.key === worst.key;
        return (
          <div key={b.key}>
            <div className="mb-1.5 flex items-baseline justify-between gap-3">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-foreground">{b.label}</span>
                {isWorst && (
                  <span className="inline-flex items-center gap-1 rounded-full border border-destructive/30 bg-destructive/10 px-1.5 py-0.5 text-[10px] font-medium text-destructive">
                    <AlertTriangle className="h-3 w-3" />
                    biggest gap
                  </span>
                )}
              </div>
              <span className="tabular-nums text-xs text-muted-foreground">
                <span className="font-semibold text-foreground">{fmt(b.guarded)}</span>
                {" / "}
                {fmt(b.total)} guarded
                <span
                  className="ml-2 font-semibold"
                  style={{ color: `hsl(${b.hsl})` }}
                >
                  {b.pct}%
                </span>
              </span>
            </div>
            {/* Outer bar = relative level size; inner fill = guarded share. */}
            <div className="h-3 w-full">
              <div
                className="relative h-full overflow-hidden rounded-full bg-muted/40"
                style={{ width: `${Math.max(trackW, 6)}%` }}
              >
                <div
                  className="h-full rounded-full"
                  style={{ width: `${fillW}%`, background: `hsl(${b.hsl})` }}
                  title={`${b.guarded} of ${b.total} guarded`}
                />
              </div>
            </div>
          </div>
        );
      })}
      <p className="pt-1 text-xs leading-relaxed text-muted-foreground">
        Bar length shows each level&apos;s share of all criteria; the filled portion is the
        guarded fraction. Edge cases (L3) are the thinnest slice of coverage — the exact
        behaviours most likely to break ship almost entirely unguarded.
      </p>
    </div>
  );
}
