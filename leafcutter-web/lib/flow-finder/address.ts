/**
 * The finder address (UXP-617-1): /flows?q=...&<facet>=<stored value>... The query
 * string IS the finder state, so a search can be shared. q comes first, then one
 * parameter per chosen value: facets in declaration order, values in option order.
 */
import { FACET_DEFS, FACET_NAMES, emptyFacets, sortValues } from "./facets";
import type { FacetName, FinderFacets, FinderState } from "./types";

export const FINDER_PATH = "/flows";

type ParamValue = string | string[] | undefined;

const all = (v: ParamValue): string[] => (Array.isArray(v) ? v : v === undefined ? [] : [v]);

/** The search text as it is kept: trimmed; null when empty. */
export const normalizeQ = (q: string | null | undefined): string | null => {
  const t = (q ?? "").trim();
  return t === "" ? null : t;
};

/**
 * State from Next's searchParams object or a URLSearchParams. Unknown parameters
 * are ignored, and so is a value a closed vocabulary does not declare.
 */
export function parseFinderQuery(params: Record<string, ParamValue> | URLSearchParams): FinderState {
  const get = (key: string): string[] =>
    params instanceof URLSearchParams ? params.getAll(key) : all(params[key]);
  const facets = emptyFacets();
  for (const def of FACET_DEFS) {
    const closed = def.options && !def.source ? def.options.map((o) => o.value) : null;
    const values = get(def.name).filter((v) => v !== "" && (!closed || closed.includes(v)));
    facets[def.name] = sortValues(def.name, values);
  }
  return { q: normalizeQ(get("q")[0]), facets };
}

/** The canonical address of a finder state. */
export function buildFinderHref(state: FinderState): string {
  const qs = new URLSearchParams();
  const q = normalizeQ(state.q);
  if (q) qs.set("q", q);
  for (const name of FACET_NAMES) {
    for (const v of sortValues(name, state.facets[name])) qs.append(name, v);
  }
  const s = qs.toString();
  return s ? `${FINDER_PATH}?${s}` : FINDER_PATH;
}

export const hasFacets = (facets: FinderFacets) => FACET_NAMES.some((n) => facets[n].length > 0);

/** The state with one facet value removed (q and every other value kept). */
export function withoutValue(state: FinderState, facet: FacetName, value: string): FinderState {
  return { q: state.q, facets: { ...state.facets, [facet]: state.facets[facet].filter((v) => v !== value) } };
}

/** The state with the value added (or removed when it is already chosen). */
export function toggleValue(state: FinderState, facet: FacetName, value: string): FinderState {
  const on = state.facets[facet].includes(value);
  const next = on ? state.facets[facet].filter((v) => v !== value) : [...state.facets[facet], value];
  return { q: state.q, facets: { ...state.facets, [facet]: sortValues(facet, next) } };
}

/** The state with every facet removed and q kept. */
export const withoutFacets = (state: FinderState): FinderState => ({ q: state.q, facets: emptyFacets() });
