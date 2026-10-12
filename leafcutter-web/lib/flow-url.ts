/**
 * Canonical Atlas flow address (UXP-591). The ONLY place a flow address is
 * produced or classified. Edge-safe on purpose: middleware imports it, so no
 * node:fs, no server-only, no flow store.
 *
 *   /flows/<product>/<flow>[?step=<stepId>]
 *
 * The slash between product and flow is literal (never %2F) and the flow is
 * never carried in a query string.
 */

/** The flow the bare /flows address opens. Single definition. */
export const DEFAULT_ENTRY_FLOW_ID = "leafcutter/deliver-a-feature";

/** Request header middleware uses to hand the raw (still-encoded) id to the route. */
export const RAW_FLOW_ID_HEADER = "x-flow-raw-id";

/** The canonical address of a flow, optionally with a step drawer open. */
export function flowHref(flowId: string, stepId?: string | null): string {
  const base = `/flows/${flowId}`;
  return stepId ? `${base}?step=${encodeURIComponent(stepId)}` : base;
}

const TWO_SEGMENT_ID = /^[a-z0-9-]+\/[a-z0-9-]+$/;

/** The detail line of the 'Flow not found' notice, chosen by the SHAPE of the id. */
export function flowNotFoundDetail(rawId: string): string {
  const hint = TWO_SEGMENT_ID.test(rawId)
    ? "The link may be mistyped, or the flow was renamed or removed."
    : "A flow link names a product and a flow, for example /flows/leafcutter/deliver-a-feature.";
  return `No flow has the id '${rawId}'. ${hint}`;
}
