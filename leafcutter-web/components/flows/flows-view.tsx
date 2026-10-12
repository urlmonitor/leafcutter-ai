"use client";

/**
 * Client shell for the Flows view. Owns the filter + selection state:
 *   - a SOURCE toggle (Mock / Real),
 *   - a KIND chooser (User / Data / Architecture) showing only kinds that have
 *     ≥1 flow for the current source,
 *   - a per-flow selector listing only flows matching source + kind, each with a
 *     live "done/total" badge.
 * Initial selection comes from the route as flat props (flowId, crumbs, filters,
 * step). Everything after that is a pure client swap. <FlowExplorer> is remounted
 * (via key) whenever the selected flow changes, so the canvas refits and the step
 * drawer resets. Empty source+kind combos render a small empty state.
 */
import * as React from "react";
import { PageHeader, EmptyState } from "@/components/ui/kit";
import { humanize } from "@/lib/utils";
import type { Flow, FlowKind, FlowRealization, FlowSource, MockData } from "@/lib/data/types";
import { FlowExplorer } from "./flow-explorer";
import {
  FlowCrumbs,
  FlowSelector,
  KINDS,
  REALIZATIONS,
  REALIZATION_LABEL,
  SOURCES,
  Segmented,
  type RealizationFilter,
} from "./flows-view-controls";
import {
  FlowNotice,
  LevelChip,
  RealizationBanner,
  StepNotice,
  StepRollup,
  type FlowsViewNotice,
} from "./flows-view-banners";
import { InitialStepContext } from "./flow-step-view";
import { stepNotFoundDetail } from "@/lib/flow-url";
import { RealizationBadge } from "./realization-badge";
import { Workflow } from "lucide-react";

export type { FlowsViewNotice };

export interface FlowsViewFilters {
  source: FlowSource;
  kind: FlowKind;
  realization: RealizationFilter;
}

export function FlowsView({
  flows,
  mocks,
  screenTitles = {},
  flowId,
  crumbs: initialCrumbs,
  filters,
  step,
  notice,
}: {
  flows: Flow[];
  mocks: Record<string, MockData | null>;
  screenTitles?: Record<string, string>;
  /** The flow the address selected; null draws no flow. */
  flowId: string | null;
  /** Drill path (flow ids) the address opens with. */
  crumbs: string[];
  filters: FlowsViewFilters;
  /** The step or branch whose drawer the address opens (`?step=`), if any. */
  step: string | null;
  notice?: FlowsViewNotice;
}) {
  const [source, setSource] = React.useState<FlowSource>(filters.source);
  const [kind, setKind] = React.useState<FlowKind>(filters.kind);
  const [realization, setRealization] = React.useState<RealizationFilter>(filters.realization);
  const [selectedId, setSelectedId] = React.useState<string>(flowId ?? "");
  // Drill path (flow ids) from the entry flow down into sub-flows.
  const [path, setPath] = React.useState<string[]>(initialCrumbs);

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
  // With nothing selected (not-found address) no flow is drawn — never a fallback.
  const entryFlow = selectedId
    ? filtered.find((f) => f.id === selectedId) ?? filtered[0] ?? null
    : null;

  // Reset the drill path to the entry whenever the entry flow changes
  // (selector click, source/kind switch). Drilling pushes onto path without
  // touching the entry, so this does not fire on drill. The first run keeps the
  // path the address opened with.
  const entryId = entryFlow?.id;
  const mounted = React.useRef(false);
  React.useEffect(() => {
    if (!mounted.current) {
      mounted.current = true;
      return;
    }
    setPath(entryId ? [entryId] : []);
  }, [entryId]);

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

  // The address's step only applies to the flow it was opened on. A step naming
  // nothing opens that flow with a notice and no drawer (not a 404).
  const stepFlow = initialCrumbs[initialCrumbs.length - 1];
  const stepKnown =
    step !== null && flow?.id === stepFlow
      ? [...flow.steps, ...flow.branches].some((x) => x.id === step)
      : false;
  const initialStep = stepKnown ? `step:${step}` : null;
  const stepNotice = step !== null && flow?.id === stepFlow && !stepKnown;

  const crumbs = path.map((id) => flowById.get(id)).filter((f): f is Flow => Boolean(f));

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
        {flow && <StepRollup flow={flow} />}
      </PageHeader>

      {flow && <RealizationBanner flow={flow} />}
      {stepNotice && <StepNotice detail={stepNotFoundDetail(step)} />}

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

      {filtered.length > 0 && (
        <FlowSelector flows={filtered} activeId={entryFlow?.id} onSelect={setSelectedId} />
      )}

      {flow ? (
        <>
          {crumbs.length > 1 && (
            <FlowCrumbs crumbs={crumbs} onSelect={(i) => setPath(path.slice(0, i + 1))} />
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

          <InitialStepContext.Provider value={initialStep}>
            <FlowExplorer
              key={flow.id}
              flow={flow}
              mock={mock}
              flowNames={flowNames}
              screenTitles={screenTitles}
              onDrill={drillTo}
            />
          </InitialStepContext.Provider>
        </>
      ) : notice ? (
        <FlowNotice notice={notice} />
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
