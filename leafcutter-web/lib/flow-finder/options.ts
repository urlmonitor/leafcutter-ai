/**
 * The options each facet lists (UXP-617-1-iii): declared options first, then the
 * ones the index supplies. Every option stays listed, zero counts included, so the
 * panel never jumps. Uses and produces list only the chosen fields; the rest are
 * picked by type-ahead (see searchFields).
 */
import { FACET_DEFS, byCodepoint, facetDef, optionLabel, type FacetOption } from "./facets";
import { startsAWord, wordsOf } from "./search";
import type { FacetName, FinderIndex, FinderState } from "./types";

const indexed = (index: FinderIndex, facet: FacetName): string[] => {
  switch (facet) {
    case "product":
      return index.flows.map((f) => f.product);
    case "entity":
      return index.flows.flatMap((f) => f.entities);
    case "screen":
      return index.flows.flatMap((f) => f.screens.map((s) => s.id));
    default:
      return [];
  }
};

export function facetOptions(index: FinderIndex, state: FinderState, facet: FacetName): FacetOption[] {
  const def = facetDef(facet);
  const declared = def.options ?? [];
  if (def.source === "field") {
    return state.facets[facet].map((value) => ({ value, label: optionLabel(index, facet, value) }));
  }
  const known = new Set(declared.map((o) => o.value));
  const extra = [...new Set([...indexed(index, facet), ...state.facets[facet]])].filter((v) => !known.has(v));
  const opts = extra.map((value) => ({ value, label: optionLabel(index, facet, value) }));
  if (def.source === "screen") opts.sort((a, b) => byCodepoint(a.label, b.label) || byCodepoint(a.value, b.value));
  else opts.sort((a, b) => byCodepoint(a.value, b.value));
  return [...declared, ...opts];
}

export function allFacetOptions(index: FinderIndex, state: FinderState): Record<FacetName, FacetOption[]> {
  return Object.fromEntries(FACET_DEFS.map((d) => [d.name, facetOptions(index, state, d.name)])) as Record<
    FacetName,
    FacetOption[]
  >;
}

/** Field keys a step uses or produces whose key or label starts with every typed word. */
export function searchFields(
  index: FinderIndex,
  facet: "uses" | "produces",
  text: string,
  limit = 12,
): FacetOption[] {
  const typed = wordsOf(text);
  if (typed.length === 0) return [];
  const keys = new Set(index.nodes.flatMap((n) => n[facet]));
  return [...keys]
    .filter((k) => startsAWord(typed, wordsOf(k)) || startsAWord(typed, wordsOf(index.fields[k] ?? k)))
    .sort(byCodepoint)
    .slice(0, limit)
    .map((value) => ({ value, label: optionLabel(index, facet, value) }));
}
