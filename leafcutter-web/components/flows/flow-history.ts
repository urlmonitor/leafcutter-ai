/**
 * Writes the Flows view's address with native history.replaceState (never the
 * router: a router navigation re-renders the keyed page and would remount the
 * view, wiping its state). The view state sits beside the App Router's own
 * history.state keys, which are preserved.
 */
import { flowHref } from "@/lib/flow-url";

/** Namespaced history.state key holding the entry's view state. */
export const FLOW_VIEW_STATE_KEY = "leafcutter:flows-view";

export interface FlowViewState {
  crumbs: string[];
  filters: { source: string; kind: string; realization: string };
}

/** Replace the current entry's address with a flow's address (step drawer open, or none). */
export function replaceFlowAddress(
  flowId: string,
  stepId: string | null,
  viewState: FlowViewState,
): void {
  const state = { ...(window.history.state ?? {}), [FLOW_VIEW_STATE_KEY]: viewState };
  window.history.replaceState(state, "", flowHref(flowId, stepId));
}
