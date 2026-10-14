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
import type { Flow, MockData } from "@/lib/data/types";
import { FlowExplorer } from "./flow-explorer";
import {
  FlowCrumbs,
  FlowSelector,
  REALIZATION_LABEL,
  SOURCES,
  Segmented,
} from "./parts/flows-view-controls";
import {
  FlowNotice,
  LevelChip,
  RealizationBanner,
  StepNotice,
  StepRollup,
  type FlowsViewNotice,
} from "./parts/flows-view-banners";
import { StepAddressContext } from "./flow-step-view";
import { stepNotFoundDetail } from "@/lib/flow-url";
import { productLabel } from "@/lib/flow-finder/facets";
import { useFlowsViewState } from "./use-flows-view-state";
import type { FlowsViewFilters } from "./flow-view-model";
import { RealizationBadge } from "./realization-badge";
import { Workflow } from "lucide-react";

export type { FlowsViewNotice };

export type { FlowsViewFilters };

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
  const {
    f,
    r,
    entryFlow,
    flow,
    crumbs,
    notice: shownNotice,
    unknownStep,
    stepAddress,
    epoch,
    onSource,
    onKind,
    onRealization,
    onSelectFlow,
    onCrumb,
    onDrill,
  } = useFlowsViewState({ flows, flowId, crumbs: initialCrumbs, filters, step, notice });
  const { kind: effectiveKind, realization: effectiveRealization, filtered } = r;
  const mock = flow ? mocks[flow.id] ?? null : null;

  const flowNames = React.useMemo(() => {
    const names: Record<string, string> = {};
    for (const x of flows) names[x.id] = x.name;
    return names;
  }, [flows]);

  return (
    <div className="flex flex-col">
      <PageHeader
        eyebrow={
          // An architecture-kind map is a cross-cutting schema, not product
          // truth — labelling it so was a category error.
          flow?.kind === "architecture"
            ? "Architecture · type-level schema"
            : flow?.product
              ? `Product truth · ${productLabel(flow.product)}`
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
      {flow && unknownStep !== null && <StepNotice detail={stepNotFoundDetail(unknownStep)} />}

      {/* source + kind controls */}
      <div className="mb-3 flex flex-wrap items-center gap-x-6 gap-y-2">
        <Segmented
          label="Source"
          options={SOURCES}
          value={f.source}
          onChange={onSource}
          render={(opt) => <span>{opt === "mock" ? "Mock" : "Real"}</span>}
        />
        {r.availableKinds.length > 0 && (
          <Segmented
            label="Kind"
            options={r.availableKinds}
            value={effectiveKind}
            onChange={onKind}
            render={(opt) => <span>{humanize(opt)}</span>}
          />
        )}
        {r.availableRealizations.length > 2 && (
          <Segmented
            label="Realization"
            options={r.availableRealizations}
            value={effectiveRealization}
            onChange={onRealization}
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
        <FlowSelector flows={filtered} activeId={entryFlow?.id} onSelect={onSelectFlow} />
      )}

      {flow ? (
        <>
          {crumbs.length > 1 && (
            <FlowCrumbs crumbs={crumbs} onSelect={onCrumb} />
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

          <StepAddressContext.Provider value={stepAddress}>
            <FlowExplorer
              key={`${flow.id}#${epoch}`}
              flow={flow}
              mock={mock}
              flowNames={flowNames}
              screenTitles={screenTitles}
              onDrill={onDrill}
            />
          </StepAddressContext.Provider>
        </>
      ) : shownNotice ? (
        <FlowNotice notice={shownNotice} />
      ) : (
        <EmptyState
          icon={<Workflow className="h-6 w-6" />}
          title={`No ${humanize(effectiveKind)} flows in ${f.source === "mock" ? "Mock" : "Real"} yet`}
          hint="Pick another source or kind above, or add a flow with that kind + source."
        />
      )}
    </div>
  );
}
