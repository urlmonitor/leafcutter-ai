"use client";

import type { MouseEvent } from "react";
import type { FinderIndex, FinderState } from "@/lib/flow-finder/types";
import { AppliedChips } from "./applied-chips";
import { FinderEmpty } from "./empty-state";
import { FacetPanel } from "./facet-panel";
import { ResultCard } from "./result-card";
import { SearchBox } from "./search-box";
import { useFinder } from "./use-finder";

/**
 * The Flow finder screen: one search box, the counted Filters, removable chips and
 * the results grouped by flow. The page renders it on the server from the address;
 * edits recompute from `index` in the browser and rewrite the address in place.
 */
export function FinderScreen({
  index,
  initial,
  onOpen,
}: {
  index: FinderIndex;
  initial: FinderState;
  /** Open a result in the app (flow, optional step). Absent: results are plain links. */
  onOpen?: (flowId: string, stepId: string | null) => void;
}) {
  const finder = useFinder(index, initial);
  const { run, state } = finder;
  // A plain click opens the flow in place (after flushing a pending address write);
  // Ctrl / Meta / Shift / Alt and non-primary clicks are left to the browser.
  const open = onOpen
    ? (flowId: string, stepId: string | null) => (e: MouseEvent<HTMLAnchorElement>) => {
        if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
        e.preventDefault();
        finder.flush();
        onOpen(flowId, stepId);
      }
    : undefined;

  return (
    <div className="flex flex-col gap-1">
      <SearchBox value={finder.qText} onChange={finder.setQuery} />
      <p role="status" aria-live="polite" className="mb-1 mt-3 text-sm font-medium text-foreground">
        {run.statusText}
      </p>
      <AppliedChips
        chips={run.appliedChips}
        clearAllHref={run.clearAllHref}
        onRemove={(chip) => finder.followHref(chip.removeHref)}
        onClearAll={(e) => run.clearAllHref && finder.inPlace(run.clearAllHref)(e)}
      />
      <div className="mt-3 grid items-start gap-5 lg:grid-cols-[16rem_minmax(0,1fr)]">
        <FacetPanel index={index} state={state} run={run} onToggle={finder.toggle} />
        <div className="flex flex-col gap-3">
          {run.emptyState ? (
            <FinderEmpty empty={run.emptyState} inPlace={finder.inPlace} />
          ) : (
            run.results.map((result) => <ResultCard key={result.flowId} result={result} open={open} />)
          )}
        </div>
      </div>
    </div>
  );
}
