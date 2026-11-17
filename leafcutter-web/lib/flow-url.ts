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

/** Request header middleware uses to hand the raw (still-encoded) id to the route. */
export const RAW_FLOW_ID_HEADER = "x-flow-raw-id";

/** The canonical address of a flow, optionally with a step drawer open. */
export function flowHref(flowId: string, stepId?: string | null): string {
  const base = `/flows/${flowId}`;
  return stepId ? `${base}?step=${encodeURIComponent(stepId)}` : base;
}

const FLOWS_PREFIX = "/flows/";
const TWO_SEGMENT_ID = /^[a-z0-9-]+\/[a-z0-9-]+$/;

/** The detail line of the 'Flow not found' notice, chosen by the SHAPE of the id. */
export function flowNotFoundDetail(rawId: string): string {
  const hint = TWO_SEGMENT_ID.test(rawId)
    ? "The link may be mistyped, or the flow was renamed or removed."
    : "A flow link names a product and a flow, for example /flows/leafcutter/deliver-a-feature.";
  return `No flow has the id '${rawId}'. ${hint}`;
}

/** The detail line of the 'Step not found' notice (a known flow, an unknown ?step=). */
export function stepNotFoundDetail(stepId: string): string {
  return `This flow has no step or branch with the id '${stepId}', so it opens without a step drawer.`;
}

function safeDecode(v: string): string {
  const plus = v.replace(/\+/g, " ");
  try {
    return decodeURIComponent(plus);
  } catch {
    return plus;
  }
}

/**
 * Where an old /flows?flow=<id>[&step=<s>] link now lives: the canonical flow
 * address, every other query parameter carried over verbatim and in order. A pure
 * function of the query (no flow lookup — middleware runs on the Edge). Null when
 * there is no usable flow parameter. A value that is not a plain two-segment id
 * is kept as ONE encoded path segment, so it can never add dot segments or leave
 * /flows/ (it then lands on 'Flow not found').
 */
export function legacyFlowLocation(search: string): string | null {
  let flow: string | null = null;
  const rest: string[] = [];
  for (const piece of search.replace(/^\?/, "").split("&")) {
    if (piece === "") continue;
    const eq = piece.indexOf("=");
    const key = safeDecode(eq < 0 ? piece : piece.slice(0, eq));
    if (key !== "flow") {
      rest.push(piece);
    } else if (flow === null) {
      flow = safeDecode(eq < 0 ? "" : piece.slice(eq + 1));
    }
  }
  if (!flow) return null;
  let segment = TWO_SEGMENT_ID.test(flow) ? flow : encodeURIComponent(flow);
  if (/^\.+$/.test(segment)) segment += "%20"; // "." / ".." would be dot segments
  return `${FLOWS_PREFIX}${segment}${rest.length ? `?${rest.join("&")}` : ""}`;
}

/** The 'Flow not found' notice for an id exactly as requested. */
export function flowNotFoundNotice(rawId: string) {
  return {
    title: "Flow not found",
    detail: flowNotFoundDetail(rawId),
    actionLabel: "Open the Flows view",
    actionHref: "/flows",
  };
}
