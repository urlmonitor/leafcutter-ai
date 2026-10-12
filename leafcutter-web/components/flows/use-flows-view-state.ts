"use client";

/**
 * State of the Flows view and its browser history. The address opens the view
 * (flowId, crumbs, filters, step); after that:
 *   - selecting a flow, drilling and clicking a breadcrumb PUSH one entry,
 *   - a drawer change, or a filter change that keeps the entry flow, REPLACES,
 *   - a filter change that drops the entry flow re-picks one and REPLACES,
 *   - Back / Forward (popstate) restore the entry as it was left, with no writes.
 * Native history only: a router move would remount the keyed page.
 */
import * as React from "react";
import type { Flow } from "@/lib/data/types";
import { flowNotFoundNotice } from "@/lib/flow-url";
import { pushFlowAddress, replaceFlowAddress, storeViewState } from "./flow-history";
import { resolveFilters, viewForEntry, type FlowsViewFilters } from "./flow-view-model";
import type { FlowsViewNotice } from "./parts/flows-view-banners";

interface Seed {
  /** Graph node id whose drawer the entry opens with (read once at explorer mount). */
  node: string | null;
  /** A `?step=` that named no step or branch on the entry's flow. */
  unknown: string | null;
}
const NO_SEED: Seed = { node: null, unknown: null };

function seedFor(flow: Flow | undefined, step: string | null, report: boolean): Seed {
  if (!flow || step === null) return NO_SEED;
  const known = [...flow.steps, ...flow.branches].some((x) => x.id === step);
  return known ? { node: `step:${step}`, unknown: null } : { node: null, unknown: report ? step : null };
}

export function useFlowsViewState(p: {
  flows: Flow[];
  flowId: string | null;
  crumbs: string[];
  filters: FlowsViewFilters;
  step: string | null;
  notice?: FlowsViewNotice;
}) {
  const { flows } = p;
  const flowById = React.useMemo(() => new Map(flows.map((f) => [f.id, f])), [flows]);

  const [f, setF] = React.useState<FlowsViewFilters>(p.filters);
  const [selectedId, setSelectedId] = React.useState<string>(p.flowId ?? "");
  const [path, setPath] = React.useState<string[]>(p.crumbs);
  const [notice, setNotice] = React.useState<FlowsViewNotice | null>(p.notice ?? null);
  const [seed, setSeed] = React.useState<Seed>(() =>
    seedFor(flowById.get(p.crumbs[p.crumbs.length - 1]), p.step, true),
  );
  // Bumped on Back / Forward so the explorer remounts and re-seeds its drawer.
  const [epoch, setEpoch] = React.useState(0);

  const r = React.useMemo(() => resolveFilters(flows, f), [flows, f]);
  // With nothing selected (not-found address) no flow is drawn — never a fallback.
  const entryFlow = selectedId
    ? r.filtered.find((x) => x.id === selectedId) ?? r.filtered[0] ?? null
    : null;
  const renderedId = path[path.length - 1];
  const flow = (renderedId && flowById.get(renderedId)) || entryFlow;

  const live = { source: f.source, kind: r.kind, realization: r.realization };

  const leaveEntry = (nextPath: string[]) => {
    setPath(nextPath);
    setNotice(null);
    setSeed(NO_SEED);
  };

  const applyFilters = (nf: FlowsViewFilters) => {
    if (nf.source === f.source && nf.kind === f.kind && nf.realization === f.realization) return;
    const nr = resolveFilters(flows, nf);
    const next = { source: nf.source, kind: nr.kind, realization: nr.realization };
    const keep = selectedId !== "" && nr.filtered.some((x) => x.id === selectedId);
    const entry = keep ? selectedId : nr.filtered[0]?.id ?? "";
    setF(nf);
    if (entry === selectedId) {
      if (entry) storeViewState({ crumbs: path, filters: next });
      return;
    }
    // The entry flow dropped out of the filter (or the notice shows): re-pick, replace in place.
    setSelectedId(entry);
    leaveEntry(entry ? [entry] : []);
    if (entry) replaceFlowAddress(entry, null, { crumbs: [entry], filters: next });
  };

  const onSource = (source: FlowsViewFilters["source"]) => {
    const kinds = r.kindsFor(source);
    applyFilters({ ...f, source, kind: kinds.includes(f.kind) ? f.kind : kinds[0] ?? f.kind });
  };

  const push = (nextPath: string[]) => {
    pushFlowAddress(nextPath[nextPath.length - 1], { crumbs: nextPath, filters: live });
    leaveEntry(nextPath);
  };
  const onSelectFlow = (id: string) => {
    if (id === entryFlow?.id && path.length === 1) return;
    setSelectedId(id);
    push([id]);
  };
  const onCrumb = (i: number) => push(path.slice(0, i + 1));
  const onDrill = (childId: string) => {
    if (flowById.has(childId)) push([...path, childId]);
  };

  // A drawer opened, switched or closed: replace the address in place (no Back entry).
  const flowIdNow = flow?.id;
  const onStepChange = (nodeId: string | null) => {
    setSeed(NO_SEED);
    if (flowIdNow) {
      replaceFlowAddress(flowIdNow, nodeId ? nodeId.replace(/^step:/, "") : null, {
        crumbs: path,
        filters: live,
      });
    }
  };
  const stepAddress = { initialId: seed.node, onChange: onStepChange };

  // Back / Forward: restore the entry as it was left. Writes no history.
  React.useEffect(() => {
    const onPop = () => {
      const v = viewForEntry(flows);
      setF(v.filters);
      setSelectedId(v.crumbs[0] ?? "");
      setPath(v.crumbs);
      setNotice(v.flowId ? null : flowNotFoundNotice(v.rawId));
      setSeed(seedFor(v.flowId ? flowById.get(v.flowId) : undefined, v.step, false));
      setEpoch((e) => e + 1);
    };
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, [flows, flowById]);

  return {
    flowById,
    f,
    r,
    entryFlow,
    flow,
    crumbs: path.map((id) => flowById.get(id)).filter((x): x is Flow => Boolean(x)),
    notice,
    unknownStep: seed.unknown,
    stepAddress,
    epoch,
    onSource,
    onKind: (kind: FlowsViewFilters["kind"]) => applyFilters({ ...f, kind }),
    onRealization: (realization: FlowsViewFilters["realization"]) =>
      applyFilters({ ...f, realization }),
    onSelectFlow,
    onCrumb,
    onDrill,
  };
}
