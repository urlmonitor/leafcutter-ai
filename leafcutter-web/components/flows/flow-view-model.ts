/**
 * Pure model of the Flows view: how the filters resolve to a flow list, and how
 * a history entry (stored view state, or just its URL) maps back to a view.
 */
import type { Flow, FlowKind, FlowRealization, FlowSource } from "@/lib/data/types";
import { FLOW_VIEW_STATE_KEY, type FlowViewState } from "./flow-history";
import { KINDS, REALIZATIONS, type RealizationFilter } from "./parts/flows-view-controls";

export interface FlowsViewFilters {
  source: FlowSource;
  kind: FlowKind;
  realization: RealizationFilter;
}

export const DEFAULT_FILTERS: FlowsViewFilters = { source: "real", kind: "user", realization: "all" };

/** The filters as the user sees them, and the flows they list. */
export function resolveFilters(flows: Flow[], f: FlowsViewFilters) {
  const kindsFor = (src: FlowSource) =>
    KINDS.filter((k) => flows.some((x) => x.source === src && x.kind === k));
  const availableKinds = kindsFor(f.source);
  // If the chosen kind has no flows for this source, fall back to the first that does.
  const kind = availableKinds.includes(f.kind) ? f.kind : availableKinds[0] ?? f.kind;
  // Realizations present in the current source+kind scope.
  const present = new Set<FlowRealization>();
  for (const x of flows) if (x.source === f.source && x.kind === kind) present.add(x.realization);
  const availableRealizations: RealizationFilter[] = [
    "all",
    ...REALIZATIONS.filter((r) => present.has(r)),
  ];
  const realization: RealizationFilter =
    f.realization === "all" || present.has(f.realization) ? f.realization : "all";
  const filtered = flows.filter(
    (x) =>
      x.source === f.source &&
      x.kind === kind &&
      (realization === "all" || x.realization === realization),
  );
  return { kind, realization, filtered, availableKinds, availableRealizations, kindsFor };
}

/** A history entry as the view shows it. flowId null = the 'Flow not found' state. */
export interface ViewEntry {
  /** True when the entry's path is exactly /flows: the finder, no flow drawn. */
  finder?: boolean;
  flowId: string | null;
  crumbs: string[];
  filters: FlowsViewFilters;
  step: string | null;
  rawId: string;
}

/** The entry under the cursor: its URL says what it shows, its stored view state the crumbs and filters. */
export function viewForEntry(flows: Flow[]): ViewEntry {
  const { pathname, search } = window.location;
  const step = new URLSearchParams(search).get("step");
  const stored = (window.history.state ?? {})[FLOW_VIEW_STATE_KEY] as FlowViewState | undefined;
  if (pathname.replace(/\/$/, "") === "/flows") {
    return { finder: true, flowId: null, crumbs: [], filters: DEFAULT_FILTERS, step: null, rawId: "" };
  }
  if (stored && stored.crumbs.length > 0) {
    return {
      flowId: stored.crumbs[stored.crumbs.length - 1],
      crumbs: stored.crumbs,
      filters: stored.filters as FlowsViewFilters,
      step,
      rawId: "",
    };
  }
  const rawId = pathname.startsWith("/flows/") ? pathname.slice("/flows/".length) : "";
  const flow = flows.find((f) => f.id === rawId);
  // An unknown id keeps the filters the entry was left with, not the boundary's server defaults.
  if (!flow) {
    const filters = (stored?.filters as FlowsViewFilters | undefined) ?? DEFAULT_FILTERS;
    return { flowId: null, crumbs: [], filters, step: null, rawId };
  }
  return {
    flowId: flow.id,
    crumbs: [flow.id],
    filters: { source: flow.source, kind: flow.kind, realization: "all" },
    step,
    rawId,
  };
}
