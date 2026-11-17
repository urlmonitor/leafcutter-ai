/**
 * runFinder(index, state): everything the finder screen shows for one state, in
 * the FlowFinderQuery shapes of the leafcutter/atlas-flows dataset. Pure: the
 * server renders it for the first paint and the client recomputes it on each edit.
 */
import { ACTOR_KINDS, ACTOR_KIND_LABEL } from "@/lib/data/actor-kind";
import { flowHref } from "@/lib/flow-url";
import { buildFinderHref, hasFacets, normalizeQ, withoutFacets, withoutValue } from "./address";
import { FACET_NAMES, chipLabel, facetDef, optionLabel, sortValues } from "./facets";
import { listFlows, type Listed } from "./listing";
import { allFacetOptions } from "./options";
import type {
  FacetCounts,
  FacetName,
  FinderChip,
  FinderEmptyState,
  FinderIndex,
  FinderResult,
  FinderRun,
  FinderState,
} from "./types";

const MAX_ROWS = 3;
const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;

function toResult(index: FinderIndex, item: Listed): FinderResult {
  const { flow } = item;
  const rows = item.matches.slice(0, MAX_ROWS);
  const mine = index.nodes.filter((n) => n.flowId === flow.id);
  return {
    flowId: flow.id,
    flowName: flow.name,
    href: flowHref(flow.id),
    flowMatch: item.flowMatch,
    matchingSteps: item.matches.length,
    moreSteps: item.matches.length - rows.length,
    stepRows: rows.map(({ node, reason }) => ({
      nodeId: node.nodeId,
      nodeKind: node.nodeKind,
      label: node.label,
      actorKind: node.actorKind,
      actorLabel: node.actorKind ? ACTOR_KIND_LABEL[node.actorKind] : null,
      reason,
      href: flowHref(flow.id, node.nodeId),
    })),
    meta: {
      productLabel: optionLabel(index, "product", flow.product),
      kind: optionLabel(index, "kind", flow.kind),
      realization: optionLabel(index, "realization", flow.realization),
      level: optionLabel(index, "level", flow.level),
      stepCount: flow.stepCount,
      branchCount: flow.branchCount,
      actorMix: ACTOR_KINDS.map((actorKind) => ({
        actorKind,
        actorLabel: ACTOR_KIND_LABEL[actorKind],
        count: mine.filter((n) => n.actorKind === actorKind).length,
      })).filter((m) => m.count > 0),
      ioGapNodes: mine.filter((n) => n.ioGap).length,
    },
  };
}

function statusText(state: FinderState, flows: number, steps: number, stepFacet: boolean): string {
  if (flows === 0) return "No flows match";
  if (state.q || stepFacet) return `${plural(flows, "flow", "flows")}, ${plural(steps, "step", "steps")} match`;
  return hasFacets(state.facets) ? `${plural(flows, "flow", "flows")} match` : plural(flows, "flow", "flows");
}

function emptyStateOf(index: FinderIndex, state: FinderState, chips: FinderChip[]): FinderEmptyState {
  const searched = state.q !== null;
  const filtered = chips.length > 0;
  return {
    title: searched ? `No flows match '${state.q}'` : "No flows match these filters",
    detail:
      searched && filtered
        ? "Nothing matches the search together with the filters you chose. Remove a filter to widen the search."
        : searched
          ? "Nothing matches the search. Check the spelling or try fewer words."
          : "No flow meets all of the filters you chose. Remove a filter to widen the list.",
    suggestions: chips.map((c) => ({
      label: `Remove ${c.label}`,
      href: c.removeHref,
      flows: listFlows(index, withoutValue(state, c.facet, c.value)).length,
    })),
  };
}

export function runFinder(index: FinderIndex, input: FinderState): FinderRun {
  const state: FinderState = { q: normalizeQ(input.q), facets: input.facets };
  const listed = listFlows(index, state);
  const results = listed.map((item) => toResult(index, item));
  const steps = results.reduce((n, r) => n + r.matchingSteps, 0);
  const stepFacet = FACET_NAMES.some((n) => facetDef(n).scope === "step" && state.facets[n].length > 0);

  const options = allFacetOptions(index, state);
  const facetCounts = {} as FacetCounts;
  for (const name of FACET_NAMES) {
    facetCounts[name] = {};
    for (const opt of options[name]) {
      facetCounts[name][opt.value] = flowsWithOption(index, state, name, opt.value);
    }
  }

  const appliedChips: FinderChip[] = FACET_NAMES.flatMap((facet) =>
    sortValues(facet, state.facets[facet]).map((value) => ({
      facet,
      value,
      label: chipLabel(index, facet, value),
      removeHref: buildFinderHref(withoutValue(state, facet, value)),
    })),
  );

  return {
    statusText: statusText(state, results.length, steps, stepFacet),
    resultCount: { flows: results.length, steps },
    results,
    facetCounts,
    facetOptions: options,
    appliedChips,
    clearAllHref: hasFacets(state.facets) ? buildFinderHref(withoutFacets(state)) : null,
    emptyState: results.length === 0 ? emptyStateOf(index, state, appliedChips) : null,
  };
}

/** Flows the finder would list if `value` alone were chosen in `facet` (q and the other facets kept). */
export function flowsWithOption(index: FinderIndex, state: FinderState, facet: FacetName, value: string): number {
  const alone = { q: normalizeQ(state.q), facets: { ...state.facets, [facet]: [value] } };
  return listFlows(index, alone).length;
}
