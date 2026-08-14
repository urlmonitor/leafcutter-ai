"use client";

/**
 * Client shell for the Flows view. Owns the filter + selection state:
 *   - a SOURCE toggle (Mock / Real),
 *   - a KIND chooser (User / Data / Architecture) showing only kinds that have
 *     ≥1 flow for the current source,
 *   - a per-flow selector listing only flows matching source + kind, each with a
 *     live "done/total" badge.
 * Everything is a pure client swap (no route change). <FlowExplorer> is remounted
 * (via key) whenever the selected flow changes, so the canvas refits and the step
 * drawer resets. Empty source+kind combos render a small empty state.
 */
import * as React from "react";
import { PageHeader, Badge, EmptyState } from "@/components/ui/kit";
import { cn, humanize } from "@/lib/utils";
import { WORK_STATUS_TONE } from "@/lib/status";
import type {
  Flow,
  FlowKind,
  FlowLevel,
  FlowRealization,
  FlowSource,
  MockData,
} from "@/lib/data/types";
import { FlowExplorer } from "./flow-explorer";
import { RealizationBadge, realizationMeta } from "./realization-badge";
import { Workflow, ChevronRight, Layers } from "lucide-react";

const SOURCES: FlowSource[] = ["mock", "real"];
const KINDS: FlowKind[] = ["user", "data", "architecture"];
// "all" plus the three realizations, in built→spec→mock order (most→least real).
type RealizationFilter = "all" | FlowRealization;
const REALIZATIONS: FlowRealization[] = ["built", "spec", "mock"];
const REALIZATION_LABEL: Record<RealizationFilter, string> = {
  all: "All",
  built: "Built",
  spec: "Spec",
  mock: "Sample",
};
const DEFAULT_ENTRY = "leafcutter/deliver-a-feature";

// HSL accents for the flow-level chip (journey → pipeline → agent = drill deeper).
const LEVEL_HSL: Record<FlowLevel, string> = {
  journey: "205 78% 60%",
  pipeline: "150 64% 52%",
  agent: "265 60% 66%",
};

function LevelChip({ level }: { level: FlowLevel }) {
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

function Segmented<T extends string>({
  label,
  options,
  value,
  onChange,
  render,
}: {
  label: string;
  options: T[];
  value: T;
  onChange: (next: T) => void;
  render: (opt: T) => React.ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground/80">
        {label}
      </span>
      <div className="inline-flex flex-wrap gap-1 rounded-lg border border-border/70 bg-card/60 p-1">
        {options.map((opt) => {
          const active = opt === value;
          return (
            <button
              key={opt}
              type="button"
              onClick={() => onChange(opt)}
              className={cn(
                "inline-flex items-center gap-2 rounded-md px-3 py-1.5 text-sm transition-colors",
                active
                  ? "bg-primary/15 font-medium text-foreground"
                  : "text-muted-foreground hover:bg-secondary/60 hover:text-foreground",
              )}
            >
              {render(opt)}
            </button>
          );
        })}
      </div>
    </div>
  );
}

export function FlowsView({
  flows,
  mocks,
  screenTitles = {},
}: {
  flows: Flow[];
  mocks: Record<string, MockData | null>;
  screenTitles?: Record<string, string>;
}) {
  const [source, setSource] = React.useState<FlowSource>("real");
  const [kind, setKind] = React.useState<FlowKind>("user");
  const [realization, setRealization] = React.useState<RealizationFilter>("all");
  const [selectedId, setSelectedId] = React.useState<string>(() =>
    flows.some((f) => f.id === DEFAULT_ENTRY) ? DEFAULT_ENTRY : "",
  );
  // Drill path (flow ids) from the entry flow down into sub-flows.
  const [path, setPath] = React.useState<string[]>([]);

  const flowById = React.useMemo(() => {
    const m = new Map<string, Flow>();
    for (const f of flows) m.set(f.id, f);
    return m;
  }, [flows]);

  const flowNames = React.useMemo(() => {
    const r: Record<string, string> = {};
    for (const f of flows) r[f.id] = f.name;
    return r;
  }, [flows]);

  // Kinds that actually have a flow for the current source.
  const kindsForSource = React.useCallback(
    (src: FlowSource) => KINDS.filter((k) => flows.some((f) => f.source === src && f.kind === k)),
    [flows],
  );
  const availableKinds = kindsForSource(source);
  // If the chosen kind has no flows for this source, fall back to the first that does.
  const effectiveKind = availableKinds.includes(kind) ? kind : availableKinds[0] ?? kind;

  // Realizations actually present in the current source+kind scope. Powers the
  // realization filter so a reviewer can isolate real (built) flows from
  // spec/sample seeds. Only offered when >1 realization is present (else noise).
  const realizationsInScope = React.useMemo(() => {
    const present = new Set<FlowRealization>();
    for (const f of flows) {
      if (f.source === source && f.kind === effectiveKind) present.add(f.realization);
    }
    return present;
  }, [flows, source, effectiveKind]);
  const availableRealizations = React.useMemo<RealizationFilter[]>(
    () => ["all", ...REALIZATIONS.filter((r) => realizationsInScope.has(r))],
    [realizationsInScope],
  );
  // Fall back to "all" if the chosen realization has no flows in the current scope.
  const effectiveRealization: RealizationFilter =
    realization === "all" || realizationsInScope.has(realization) ? realization : "all";

  const filtered = React.useMemo(
    () =>
      flows.filter(
        (f) =>
          f.source === source &&
          f.kind === effectiveKind &&
          (effectiveRealization === "all" || f.realization === effectiveRealization),
      ),
    [flows, source, effectiveKind, effectiveRealization],
  );

  // The ENTRY flow (top-level selector), falling back to the first match in scope.
  const entryFlow = filtered.find((f) => f.id === selectedId) ?? filtered[0] ?? null;

  // Reset the drill path to the entry whenever the entry flow changes
  // (selector click, source/kind switch). Drilling pushes onto path without
  // touching the entry, so this does not fire on drill.
  React.useEffect(() => {
    setPath(entryFlow ? [entryFlow.id] : []);
  }, [entryFlow?.id]);

  // The flow actually rendered = deepest crumb, or the entry before the effect runs.
  const renderedId = path[path.length - 1];
  const flow = (renderedId && flowById.get(renderedId)) || entryFlow;
  const mock = flow ? mocks[flow.id] ?? null : null;

  const onSelectSource = (next: FlowSource) => {
    setSource(next);
    // Auto-select the first kind that has flows in the new source, if the current one doesn't.
    const kinds = kindsForSource(next);
    if (!kinds.includes(kind)) setKind(kinds[0] ?? kind);
  };

  const drillTo = React.useCallback(
    (childId: string) => {
      if (flowById.has(childId)) setPath((p) => [...p, childId]);
    },
    [flowById],
  );

  const crumbs = path.map((id) => flowById.get(id)).filter((f): f is Flow => Boolean(f));

  const s = flow?.implSummary;

  return (
    <div className="flex flex-col">
      <PageHeader
        eyebrow={
          // An architecture-kind map is a cross-cutting schema, not product
          // truth — labelling it so was a category error.
          flow?.kind === "architecture"
            ? "Architecture · type-level schema"
            : flow?.product
              ? `Product truth · ${flow.product}`
              : "Product truth"
        }
        title={flow?.name ?? "Flows"}
        description={
          flow?.summary ??
          "Interactive maps of how a product actually behaves, step by step."
        }
      >
        {/* Step rollup is meaningless for a stepless architecture map — it
            rendered "0 done · 0 in progress · 0 not started of 0 steps", a
            fabricated progress claim. Suppress it for architecture kinds. */}
        {flow && s && flow.kind !== "architecture" && (
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
        )}
      </PageHeader>

      {/* Realization banner — never let a reviewer read a spec/sample flow as a live map.
          Excluded for architecture maps: the banner asserts "the system it maps
          does not exist yet", which is false for a schema of the live repo. */}
      {flow && flow.realization !== "built" && flow.kind !== "architecture" && (() => {
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
      })()}

      {/* source + kind controls */}
      <div className="mb-3 flex flex-wrap items-center gap-x-6 gap-y-2">
        <Segmented
          label="Source"
          options={SOURCES}
          value={source}
          onChange={onSelectSource}
          render={(opt) => <span>{opt === "mock" ? "Mock" : "Real"}</span>}
        />
        {availableKinds.length > 0 && (
          <Segmented
            label="Kind"
            options={availableKinds}
            value={effectiveKind}
            onChange={setKind}
            render={(opt) => <span>{humanize(opt)}</span>}
          />
        )}
        {availableRealizations.length > 2 && (
          <Segmented
            label="Realization"
            options={availableRealizations}
            value={effectiveRealization}
            onChange={setRealization}
            render={(opt) =>
              opt === "all" || opt === "built" ? (
                <span>{REALIZATION_LABEL[opt]}</span>
              ) : (
                <RealizationBadge realization={opt} size="sm" />
              )
            }
          />
        )}
      </div>

      {/* per-flow selector (only flows matching source + kind) */}
      {filtered.length > 0 && (
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <span className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground/80">
            Flow
          </span>
          <div className="inline-flex flex-wrap gap-1 rounded-lg border border-border/70 bg-card/60 p-1">
            {filtered.map((f) => {
              const active = f.id === entryFlow?.id;
              return (
                <button
                  key={f.id}
                  type="button"
                  onClick={() => setSelectedId(f.id)}
                  className={cn(
                    "inline-flex items-center gap-2 rounded-md px-3 py-1.5 text-sm transition-colors",
                    active
                      ? "bg-primary/15 font-medium text-foreground"
                      : "text-muted-foreground hover:bg-secondary/60 hover:text-foreground",
                  )}
                >
                  <span>{f.name}</span>
                  {f.realization !== "built" && (
                    <RealizationBadge realization={f.realization} size="sm" />
                  )}
                  <span
                    className={cn(
                      "rounded px-1.5 py-0.5 font-mono text-[10px] tabular-nums",
                      active
                        ? "bg-success/15 text-success"
                        : "bg-muted/50 text-muted-foreground",
                    )}
                  >
                    {f.implSummary.done}/{f.implSummary.total} done
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {flow ? (
        <>
          {/* breadcrumb drill path — click a crumb to zoom back out to that level */}
          {crumbs.length > 1 && (
            <nav className="mb-3 flex flex-wrap items-center gap-1 text-sm">
              {crumbs.map((c, i) => {
                const last = i === crumbs.length - 1;
                return (
                  <React.Fragment key={c.id}>
                    {i > 0 && (
                      <ChevronRight className="h-3.5 w-3.5 text-muted-foreground/60" />
                    )}
                    <button
                      type="button"
                      disabled={last}
                      onClick={() => setPath(path.slice(0, i + 1))}
                      className={cn(
                        "rounded-md px-2 py-1 transition-colors",
                        last
                          ? "font-medium text-foreground"
                          : "text-muted-foreground hover:bg-secondary/60 hover:text-foreground",
                      )}
                    >
                      {c.name}
                    </button>
                  </React.Fragment>
                );
              })}
            </nav>
          )}

          <div className="mb-3 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <LevelChip level={flow.level} />
            {flow.entities.length > 0 && (
              <>
                <span className="ml-1 font-medium text-foreground">Entities:</span>
                {flow.entities.map((e) => (
                  <span
                    key={e}
                    className="rounded-md border border-border/70 bg-card/60 px-2 py-0.5 font-mono text-[11px]"
                  >
                    {e}
                  </span>
                ))}
              </>
            )}
            {mock && (
              <span className="ml-1">
                · mock data{" "}
                <span className="font-mono text-foreground">
                  {humanize(mock.id.split("/").pop() ?? mock.id)}
                </span>
              </span>
            )}
          </div>

          <FlowExplorer
            key={flow.id}
            flow={flow}
            mock={mock}
            flowNames={flowNames}
            screenTitles={screenTitles}
            onDrill={drillTo}
          />
        </>
      ) : (
        <EmptyState
          icon={<Workflow className="h-6 w-6" />}
          title={`No ${humanize(effectiveKind)} flows in ${source === "mock" ? "Mock" : "Real"} yet`}
          hint="Pick another source or kind above, or add a flow with that kind + source."
        />
      )}
    </div>
  );
}
