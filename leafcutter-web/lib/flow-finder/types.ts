/**
 * Finder types (UXP-617-1). Pure and isomorphic: the server page and the client
 * finder share them, so nothing here may touch node:fs, server-only or React.
 */
import type { ActorKind } from "@/lib/data/actor-kind";
import type { FacetOption } from "./facets";

export type FacetName =
  | "product"
  | "actor"
  | "kind"
  | "realization"
  | "level"
  | "uses"
  | "produces"
  | "io"
  | "entity"
  | "screen";

/** The chosen STORED values per facet (never labels). */
export type FinderFacets = Record<FacetName, string[]>;

/** The whole finder state: the query string IS this object. */
export interface FinderState {
  q: string | null;
  facets: FinderFacets;
}

export interface FinderScreen {
  id: string;
  title: string;
}

export interface FinderFlow {
  id: string;
  name: string;
  product: string;
  kind: string;
  realization: string;
  level: string;
  /** Declared entities plus every entity a step or branch reads or writes, sorted by name. */
  entities: string[];
  /** The entities the flow itself declares (its own search targets). */
  declaredEntities: string[];
  screens: FinderScreen[];
  stepCount: number;
  branchCount: number;
}

export interface FinderNode {
  flowId: string;
  nodeId: string;
  nodeKind: "step" | "branch";
  order: number | null;
  label: string;
  text: string;
  condition: string | null;
  actorKind: ActorKind | null;
  acIds: string[];
  uses: string[];
  produces: string[];
  screen: FinderScreen | null;
  entities: string[];
  ioGap: boolean;
}

export interface FinderIndex {
  flows: FinderFlow[];
  nodes: FinderNode[];
  /** Field key -> display label, for every field any node uses or produces. */
  fields: Record<string, string>;
}

export interface FinderStepRow {
  nodeId: string;
  nodeKind: "step" | "branch";
  label: string;
  actorKind: ActorKind | null;
  actorLabel: string | null;
  reason: string;
  href: string;
}

export interface FinderResult {
  flowId: string;
  flowName: string;
  href: string;
  flowMatch: string | null;
  matchingSteps: number;
  moreSteps: number;
  stepRows: FinderStepRow[];
  /** Card meta: product label, kind, realization, level, size and actor mix. */
  meta: {
    productLabel: string;
    kind: string;
    realization: string;
    level: string;
    stepCount: number;
    branchCount: number;
    actorMix: Array<{ actorKind: ActorKind; actorLabel: string; count: number }>;
    ioGapNodes: number;
  };
}

export interface FinderChip {
  facet: FacetName;
  value: string;
  label: string;
  removeHref: string;
}

export interface FinderEmptyState {
  title: string;
  detail: string;
  suggestions: Array<{ label: string; href: string; flows: number }>;
}

export type FacetCounts = Record<FacetName, Record<string, number>>;

export interface FinderRun {
  statusText: string;
  resultCount: { flows: number; steps: number };
  results: FinderResult[];
  facetCounts: FacetCounts;
  /** The options each facet lists, in display order, labels applied once here. */
  facetOptions: Record<FacetName, FacetOption[]>;
  appliedChips: FinderChip[];
  clearAllHref: string | null;
  emptyState: FinderEmptyState | null;
}
