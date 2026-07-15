"use client";

import * as React from "react";
import {
  Search,
  ShieldCheck,
  ShieldAlert,
  ChevronRight,
  ArrowUpDown,
  FlaskConical,
  X,
} from "lucide-react";
import { cn, fmt, humanize } from "@/lib/utils";
import { LEVEL_TONE, WORK_STATUS_TONE } from "@/lib/status";
import { Badge, EmptyState } from "@/components/ui/kit";
import type { AcLevel } from "@/lib/data/types";
import type { CoverageRow } from "./shared";

const LEVELS: AcLevel[] = ["L0", "L1", "L2", "L3"];
const RENDER_CAP = 300;

type SortMode = "guard-asc" | "guard-desc" | "id";

/** Count pill showing direct test count, coloured by guarded / unguarded. */
function TestCountPill({ count }: { count: number }) {
  if (count === 0) {
    return (
      <span className="inline-flex items-center gap-1 rounded-md border border-destructive/30 bg-destructive/10 px-1.5 py-0.5 text-xs font-semibold tabular-nums text-destructive">
        <ShieldAlert className="h-3 w-3" />0
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 rounded-md border border-success/30 bg-success/10 px-1.5 py-0.5 text-xs font-semibold tabular-nums text-success">
      <ShieldCheck className="h-3 w-3" />
      {count}
    </span>
  );
}

function Row({ r }: { r: CoverageRow }) {
  const [open, setOpen] = React.useState(false);
  const lvl = LEVEL_TONE[r.level];
  const ws = WORK_STATUS_TONE[r.workStatus] ?? WORK_STATUS_TONE.unknown;
  const rolledExtra = r.testRolledUpCount > r.testCount;

  return (
    <li className="border-b border-border/50 last:border-0">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="grid w-full grid-cols-[1fr_auto] items-center gap-3 px-2 py-2.5 text-left transition-colors hover:bg-secondary/40 sm:grid-cols-[minmax(0,1fr)_5.5rem_5rem_4.5rem_4.5rem_1.25rem] sm:gap-4"
      >
        {/* AC identity */}
        <div className="min-w-0">
          <div className="truncate text-sm text-foreground">{r.title}</div>
          <div className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[11px] text-muted-foreground">
            <span className="font-mono text-muted-foreground/80">{r.id}</span>
            <span>·</span>
            <span>{humanize(r.component)}</span>
            {/* compact meta on mobile where trailing columns collapse */}
            <span className="inline-flex items-center gap-1.5 sm:hidden">
              <Badge tone={lvl}>{r.level}</Badge>
              <Badge tone={ws} dot>{ws.label}</Badge>
              <TestCountPill count={r.testCount} />
            </span>
          </div>
        </div>

        {/* level */}
        <div className="hidden sm:block">
          <Badge tone={lvl}>{r.level}</Badge>
        </div>
        {/* work status */}
        <div className="hidden sm:block">
          <Badge tone={ws} dot>{ws.label}</Badge>
        </div>
        {/* direct test count */}
        <div className="hidden justify-start sm:flex">
          <TestCountPill count={r.testCount} />
        </div>
        {/* rolled-up */}
        <div className="hidden items-center justify-end tabular-nums text-xs text-muted-foreground sm:flex">
          {rolledExtra ? (
            <span title="tests including descendant ACs">{fmt(r.testRolledUpCount)}</span>
          ) : (
            <span className="text-muted-foreground/40">—</span>
          )}
        </div>
        {/* chevron */}
        <ChevronRight
          className={cn(
            "hidden h-4 w-4 shrink-0 text-muted-foreground/50 transition-transform sm:block",
            open && "rotate-90 text-primary",
          )}
        />
      </button>

      {open && (
        <div className="animate-fade-in px-2 pb-3.5 pl-2 sm:pl-3">
          {r.testCount > 0 ? (
            <div className="rounded-lg border border-border/60 bg-card/40 p-3">
              <div className="eyebrow mb-2 flex items-center gap-1.5">
                <FlaskConical className="h-3 w-3" />
                Guarding tests ({fmt(r.testRefs.length)})
              </div>
              <ul className="space-y-1">
                {r.testRefs.map((ref) => (
                  <li key={ref} className="truncate font-mono text-[11px] text-muted-foreground" title={ref}>
                    {ref}
                  </li>
                ))}
              </ul>
              {rolledExtra && (
                <p className="mt-2 border-t border-border/50 pt-2 text-[11px] text-muted-foreground">
                  {fmt(r.testRolledUpCount)} tests guard this criterion or its descendants (rolled up).
                </p>
              )}
            </div>
          ) : (
            <div className="flex items-start gap-2.5 rounded-lg border border-destructive/25 bg-destructive/[0.06] p-3">
              <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0 text-destructive" />
              <div className="text-xs text-muted-foreground">
                <span className="font-medium text-destructive">Unguarded.</span> No test names this
                AC id.
                {r.testRolledUpCount > 0
                  ? ` It is covered indirectly (${fmt(r.testRolledUpCount)} test${r.testRolledUpCount === 1 ? "" : "s"} on descendant criteria), but nothing guards it directly.`
                  : r.workStatus === "done"
                    ? " It is marked done — a regression here would pass CI silently."
                    : " Nothing in the suite exercises this behaviour yet."}
              </div>
            </div>
          )}
        </div>
      )}
    </li>
  );
}

export function CoverageExplorer({
  rows,
  components,
}: {
  rows: CoverageRow[];
  components: string[];
}) {
  const [q, setQ] = React.useState("");
  const [level, setLevel] = React.useState<AcLevel | "all">("all");
  const [component, setComponent] = React.useState<string>("all");
  const [unguardedOnly, setUnguardedOnly] = React.useState(false);
  const [doneUnguarded, setDoneUnguarded] = React.useState(false);
  const [sort, setSort] = React.useState<SortMode>("guard-asc");

  const filtered = React.useMemo(() => {
    const needle = q.trim().toLowerCase();
    let out = rows.filter((r) => {
      if (level !== "all" && r.level !== level) return false;
      if (component !== "all" && r.component !== component) return false;
      if (unguardedOnly && r.testCount !== 0) return false;
      if (doneUnguarded && !(r.workStatus === "done" && r.testCount === 0)) return false;
      if (needle) {
        const hay = `${r.id} ${r.title} ${r.component}`.toLowerCase();
        if (!hay.includes(needle)) return false;
      }
      return true;
    });
    out = [...out].sort((a, b) => {
      if (sort === "id") return a.id.localeCompare(b.id);
      const d = sort === "guard-asc" ? a.testCount - b.testCount : b.testCount - a.testCount;
      if (d !== 0) return d;
      return a.id.localeCompare(b.id);
    });
    return out;
  }, [rows, q, level, component, unguardedOnly, doneUnguarded, sort]);

  const shown = filtered.slice(0, RENDER_CAP);
  const anyFilter = q || level !== "all" || component !== "all" || unguardedOnly || doneUnguarded;

  const cycleSort = () =>
    setSort((s) => (s === "guard-asc" ? "guard-desc" : s === "guard-desc" ? "id" : "guard-asc"));
  const sortLabel =
    sort === "guard-asc" ? "Tests ↑" : sort === "guard-desc" ? "Tests ↓" : "By id";

  return (
    <div>
      {/* ---- Controls ---- */}
      <div className="mb-4 space-y-3">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground/60" />
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Search id, title, or component…"
              className="w-full rounded-lg border border-border/70 bg-card/50 py-2 pl-9 pr-8 text-sm text-foreground placeholder:text-muted-foreground/60 focus:border-primary/50 focus:outline-none focus:ring-1 focus:ring-primary/40"
            />
            {q && (
              <button
                type="button"
                onClick={() => setQ("")}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground/60 hover:text-foreground"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>
          <select
            value={component}
            onChange={(e) => setComponent(e.target.value)}
            className="rounded-lg border border-border/70 bg-card/50 px-3 py-2 text-sm text-foreground focus:border-primary/50 focus:outline-none"
          >
            <option value="all">All components</option>
            {components.map((c) => (
              <option key={c} value={c}>
                {humanize(c)}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={cycleSort}
            className="inline-flex items-center justify-center gap-1.5 rounded-lg border border-border/70 bg-card/50 px-3 py-2 text-sm font-medium text-foreground transition-colors hover:border-primary/40"
          >
            <ArrowUpDown className="h-3.5 w-3.5" />
            {sortLabel}
          </button>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {/* level segmented */}
          <div className="inline-flex rounded-lg border border-border/70 bg-card/50 p-0.5 text-xs">
            <button
              type="button"
              onClick={() => setLevel("all")}
              className={cn(
                "rounded-md px-2.5 py-1 font-medium transition-colors",
                level === "all" ? "bg-primary/15 text-foreground" : "text-muted-foreground hover:text-foreground",
              )}
            >
              All
            </button>
            {LEVELS.map((l) => (
              <button
                key={l}
                type="button"
                onClick={() => setLevel(l)}
                className={cn(
                  "rounded-md px-2.5 py-1 font-medium transition-colors",
                  level === l ? "bg-primary/15 text-foreground" : "text-muted-foreground hover:text-foreground",
                )}
              >
                {l}
              </button>
            ))}
          </div>

          <Toggle active={unguardedOnly} onClick={() => setUnguardedOnly((v) => !v)}>
            <ShieldAlert className="h-3.5 w-3.5" />
            Unguarded only
          </Toggle>
          <Toggle
            active={doneUnguarded}
            onClick={() => setDoneUnguarded((v) => !v)}
            danger
          >
            <ShieldAlert className="h-3.5 w-3.5" />
            Done but unguarded
          </Toggle>

          {anyFilter && (
            <button
              type="button"
              onClick={() => {
                setQ("");
                setLevel("all");
                setComponent("all");
                setUnguardedOnly(false);
                setDoneUnguarded(false);
              }}
              className="ml-auto text-xs font-medium text-muted-foreground hover:text-foreground"
            >
              Reset
            </button>
          )}
        </div>
      </div>

      {/* ---- Count + column header ---- */}
      <div className="mb-1 flex items-center justify-between px-2 text-xs text-muted-foreground">
        <span>
          Showing{" "}
          <span className="font-semibold text-foreground">{fmt(shown.length)}</span>
          {filtered.length !== shown.length && <> of {fmt(filtered.length)}</>} criteria
          {filtered.length !== rows.length && <> · {fmt(rows.length)} total</>}
        </span>
      </div>
      <div className="hidden grid-cols-[minmax(0,1fr)_5.5rem_5rem_4.5rem_4.5rem_1.25rem] gap-4 border-b border-border/70 px-2 pb-2 sm:grid">
        <div className="eyebrow">Acceptance criterion</div>
        <div className="eyebrow">Level</div>
        <div className="eyebrow">Status</div>
        <div className="eyebrow">Tests</div>
        <div className="eyebrow text-right">Rolled</div>
        <div />
      </div>

      {/* ---- Rows ---- */}
      {shown.length > 0 ? (
        <ul>
          {shown.map((r) => (
            <Row key={r.id} r={r} />
          ))}
        </ul>
      ) : (
        <EmptyState
          icon={<Search className="h-7 w-7" />}
          title="No criteria match these filters"
          hint="Try clearing the search or toggles to widen the set."
        />
      )}

      {filtered.length > RENDER_CAP && (
        <p className="mt-4 border-t border-border/60 pt-3 text-center text-xs text-muted-foreground">
          Rendering the first {fmt(RENDER_CAP)} of {fmt(filtered.length)} matches for speed —
          narrow with search or filters to see the rest.
        </p>
      )}
    </div>
  );
}

function Toggle({
  active,
  onClick,
  danger,
  children,
}: {
  active: boolean;
  onClick: () => void;
  danger?: boolean;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs font-medium transition-colors",
        active
          ? danger
            ? "border-destructive/40 bg-destructive/10 text-destructive"
            : "border-primary/40 bg-primary/10 text-primary"
          : "border-border/70 bg-card/50 text-muted-foreground hover:text-foreground",
      )}
    >
      {children}
    </button>
  );
}
