"use client";

import * as React from "react";
import { FileCode2, Boxes } from "lucide-react";
import { cn, fmt } from "@/lib/utils";
import { riskToneHsl, type ScopeStat } from "./shared";

function StatBlock({
  label,
  untraced,
  total,
  pct,
}: {
  label: string;
  untraced: number;
  total: number;
  pct: number;
}) {
  const hsl = riskToneHsl(pct);
  return (
    <div className="rounded-xl border border-border/70 bg-card/40 p-4">
      <div className="flex items-baseline justify-between">
        <div className="eyebrow">{label}</div>
        <div className="text-2xl font-semibold tabular-nums" style={{ color: `hsl(${hsl})` }}>
          {pct}%
        </div>
      </div>
      <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-muted/50">
        <div
          className="h-full rounded-full transition-all"
          style={{ width: `${Math.max(2, pct)}%`, background: `hsl(${hsl})` }}
        />
      </div>
      <div className="mt-1.5 text-xs text-muted-foreground">
        <span className="font-semibold text-foreground">{fmt(untraced)}</span> of {fmt(total)} untraced
      </div>
    </div>
  );
}

/**
 * Untraced code — source functions/classes living in files that no acceptance
 * criterion (and no traceability-carrying ticket) links to. "The code" is
 * ambiguous, so both scopes are selectable: scripts/ only vs incl. templates/*.py.
 * Shows file- and symbol-level shares plus the heaviest untraced files.
 */
export function UntracedCode({
  scopes,
  ticketsWithTraceability,
  ticketsTotal,
}: {
  scopes: ScopeStat[];
  ticketsWithTraceability: number;
  ticketsTotal: number;
}) {
  const [active, setActive] = React.useState(0);
  const scope = scopes[active] ?? scopes[0];
  const maxSym = Math.max(1, ...scope.topUntraced.map((t) => t.symbols));
  const adoptionPct = ticketsTotal ? Math.round((ticketsWithTraceability / ticketsTotal) * 100) : 0;

  return (
    <div>
      {/* Scope toggle */}
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="inline-flex rounded-lg border border-border/70 bg-card/50 p-0.5 text-xs">
          {scopes.map((s, i) => (
            <button
              key={s.key}
              type="button"
              onClick={() => setActive(i)}
              className={cn(
                "rounded-md px-2.5 py-1 font-medium transition-colors",
                i === active ? "bg-primary/15 text-foreground" : "text-muted-foreground hover:text-foreground",
              )}
            >
              {s.label}
            </button>
          ))}
        </div>
        <span className="text-[11px] text-muted-foreground">
          {fmt(scope.files)} source files scanned
        </span>
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,300px)_1fr]">
        {/* Two stat blocks */}
        <div className="space-y-4">
          <StatBlock
            label="Untraced files"
            untraced={scope.untracedFiles}
            total={scope.files}
            pct={scope.untracedFilePct}
          />
          <StatBlock
            label="Symbols in untraced files"
            untraced={scope.symbolsInUntraced}
            total={scope.symbols}
            pct={scope.symbolsUntracedPct}
          />
          <div className="rounded-xl border border-destructive/25 bg-destructive/[0.06] p-3">
            <p className="text-[11px] leading-relaxed text-muted-foreground">
              Root cause: only{" "}
              <span className="font-semibold text-destructive">
                {fmt(ticketsWithTraceability)}
              </span>{" "}
              of {fmt(ticketsTotal)} tickets ({adoptionPct}%) carry{" "}
              <span className="font-mono text-foreground">ac_traceability</span>, so source→AC
              linkage is thin — most files simply have no path back to a requirement.
            </p>
          </div>
        </div>

        {/* Heaviest untraced files */}
        <div>
          <div className="eyebrow mb-2 flex items-center gap-1.5">
            <FileCode2 className="h-3.5 w-3.5 text-destructive" />
            Heaviest untraced files ({scope.label})
          </div>
          <ul className="space-y-2">
            {scope.topUntraced.map((t) => {
              const w = (t.symbols / maxSym) * 100;
              return (
                <li key={t.path} className="grid grid-cols-[1fr_auto] items-center gap-3">
                  <div className="min-w-0">
                    <div className="mb-1 truncate font-mono text-[11px] text-muted-foreground" title={t.path}>
                      {t.path}
                    </div>
                    <div className="h-2 w-full overflow-hidden rounded-full bg-muted/40">
                      <div
                        className="h-full rounded-full bg-destructive/70"
                        style={{ width: `${Math.max(4, w)}%` }}
                      />
                    </div>
                  </div>
                  <div className="flex items-center gap-1 text-right text-xs tabular-nums text-muted-foreground">
                    <Boxes className="h-3 w-3 text-muted-foreground/60" />
                    <span className="font-semibold text-foreground">{fmt(t.symbols)}</span>
                  </div>
                </li>
              );
            })}
          </ul>
          <p className="mt-3 text-[11px] leading-relaxed text-muted-foreground/80">
            Symbol count = functions + classes defined in a file no AC links to. These are the
            largest blind spots — logic shipped with no requirement pointing at it.
          </p>
        </div>
      </div>
    </div>
  );
}
