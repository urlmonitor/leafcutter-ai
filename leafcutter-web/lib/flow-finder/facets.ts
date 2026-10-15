/**
 * The ONE declaration of the finder's facets (UXP-617-1-iii): order, scope,
 * stored values and labels. The facet panel, chips, address builder, counts and
 * empty state all read it; nothing keeps its own copy.
 */
import { ACTOR_KINDS, ACTOR_KIND_LABEL } from "@/lib/data/actor-kind";
import type { FacetName, FinderFacets, FinderIndex, FinderState } from "./types";

export interface FacetOption {
  value: string;
  label: string;
}

export interface FacetDef {
  name: FacetName;
  /** Chip prefix: "<label>: <option label>". */
  label: string;
  /** Heading of the group in the facet panel. */
  title: string;
  /** flow facets test the flow; step facets must all be met by ONE step or branch. */
  scope: "flow" | "step";
  /** Declared options; absent when the options come from the index. */
  options?: FacetOption[];
  /** Where the index supplies the options of a facet with no declared ones. */
  source?: "product" | "entity" | "screen" | "field";
}

export const FACET_DEFS: FacetDef[] = [
  {
    name: "product",
    label: "Product",
    title: "Product",
    scope: "flow",
    options: [
      { value: "leafcutter", label: "Leafcutter" },
      { value: "fern-and-fig", label: "Fern & Fig" },
    ],
    source: "product",
  },
  {
    name: "actor",
    label: "Actor",
    title: "Actor",
    scope: "step",
    options: ACTOR_KINDS.map((value) => ({ value, label: ACTOR_KIND_LABEL[value] })),
  },
  {
    name: "kind",
    label: "Kind",
    title: "Kind",
    scope: "flow",
    options: [
      { value: "user", label: "User" },
      { value: "data", label: "Data" },
      { value: "architecture", label: "Architecture" },
    ],
  },
  {
    name: "realization",
    label: "Realization",
    title: "Realization",
    scope: "flow",
    options: [
      { value: "built", label: "Built" },
      { value: "spec", label: "Spec" },
      { value: "mock", label: "Sample" },
    ],
  },
  {
    name: "level",
    label: "Level",
    title: "Level",
    scope: "flow",
    options: [
      { value: "journey", label: "Journey" },
      { value: "pipeline", label: "Pipeline" },
      { value: "agent", label: "Agent" },
    ],
  },
  { name: "uses", label: "Uses field", title: "Uses field (input)", scope: "step", source: "field" },
  { name: "produces", label: "Produces field", title: "Produces field (output)", scope: "step", source: "field" },
  {
    name: "io",
    label: "I/O",
    title: "I/O not yet defined",
    scope: "step",
    options: [{ value: "gap", label: "I/O not yet defined" }],
  },
  { name: "entity", label: "Entity", title: "Entity", scope: "flow", source: "entity" },
  { name: "screen", label: "Screen", title: "Screen", scope: "step", source: "screen" },
];

export const FACET_NAMES: FacetName[] = FACET_DEFS.map((d) => d.name);

export const facetDef = (name: FacetName): FacetDef => FACET_DEFS.find((d) => d.name === name)!;

export function emptyFacets(): FinderFacets {
  return Object.fromEntries(FACET_NAMES.map((n) => [n, [] as string[]])) as unknown as FinderFacets;
}

export const emptyState = (q: string | null = null): FinderState => ({ q, facets: emptyFacets() });

/** Codepoint order, so "PR" sorts before "Payment" as the dataset lists them. */
export const byCodepoint = (a: string, b: string) => (a < b ? -1 : a > b ? 1 : 0);

/** A product slug's display name ("fern-and-fig" -> "Fern & Fig"); an unknown value shows as stored. */
export const productLabel = (slug: string): string =>
  facetDef("product").options?.find((o) => o.value === slug)?.label ?? slug;

export function screenTitle(index: FinderIndex, id: string): string {
  for (const f of index.flows) {
    const hit = f.screens.find((s) => s.id === id);
    if (hit) return hit.title;
  }
  return id;
}

/** Display label of one stored value. Unknown values show as stored. */
export function optionLabel(index: FinderIndex, facet: FacetName, value: string): string {
  const def = facetDef(facet);
  const declared = def.options?.find((o) => o.value === value);
  if (declared) return declared.label;
  if (def.source === "field") return index.fields[value] ?? value;
  if (def.source === "screen") return screenTitle(index, value);
  return value;
}

/** A facet with exactly one option labels its chip with that option alone. */
export function chipLabel(index: FinderIndex, facet: FacetName, value: string): string {
  const def = facetDef(facet);
  const label = optionLabel(index, facet, value);
  return def.options?.length === 1 ? label : `${def.label}: ${label}`;
}

/** Sort values into the facet's option order (declared order, else by value). */
export function sortValues(facet: FacetName, values: string[]): string[] {
  const declared = facetDef(facet).options;
  const rank = (v: string) => declared?.findIndex((o) => o.value === v) ?? -1;
  return [...new Set(values)].sort((a, b) => {
    const ra = rank(a);
    const rb = rank(b);
    if (ra >= 0 && rb >= 0) return ra - rb;
    if (ra >= 0) return -1;
    if (rb >= 0) return 1;
    return byCodepoint(a, b);
  });
}
