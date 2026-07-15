/**
 * Architecture view — pure, client-safe view-model builders.
 * No fs / no server-only: these run on the server (in page.tsx) to fold the
 * large raw AC list down to small, serializable props, and the resulting types
 * are shared with the client components.
 */
import type { AC, AcComponent, Component } from "@/lib/data/types";
import { CATEGORICAL_HSL, WORK_STATUS_TONE } from "@/lib/status";
import { humanize } from "@/lib/utils";

/* ---------- keys & colors ---------- */

/** Collapse a kebab/snake/spaced id to a comparable token: "ac_store" -> "acstore". */
export function normalizeKey(s: string): string {
  return s.toLowerCase().replace(/[-_\s]+/g, "");
}

/**
 * Deterministic, collision-free color per component type. Assigns palette
 * entries by sorted-type index so 7 types always get 7 distinct hues.
 */
export function typeColorMap(types: string[]): Record<string, string> {
  const out: Record<string, string> = {};
  types.forEach((t, i) => {
    out[t] = CATEGORICAL_HSL[i % CATEGORICAL_HSL.length];
  });
  return out;
}

/** Tone for a component's registry status (active | reviewed | deprecated | …). */
export function componentStatusTone(status: string): { label: string; hsl: string } {
  const s = status.toLowerCase();
  if (s === "active") return { label: "Active", hsl: "150 60% 48%" };
  if (s === "reviewed") return { label: "Reviewed", hsl: "205 78% 60%" };
  if (s === "deprecated" || s === "retired") return { label: humanize(s), hsl: "356 72% 56%" };
  if (s === "draft" || s === "planned") return { label: humanize(s), hsl: "38 92% 58%" };
  return { label: status ? humanize(s) : "Unknown", hsl: "150 8% 55%" };
}

/* ---------- view-model types ---------- */

export interface AcLink {
  nsId: string;
  prefix: string;
  acCount: number;
}

export interface ComponentVM {
  id: string;
  name: string;
  type: string;
  description: string;
  detailRef: string | null;
  status: string;
  primaryCode: string[];
  acLink: AcLink | null;
}

export interface TypeCluster {
  type: string;
  label: string;
  hsl: string;
  documented: number;
  total: number;
  components: ComponentVM[];
}

export interface StatusSlice {
  key: string;
  label: string;
  hsl: string;
  count: number;
}

export interface NamespaceFacet {
  id: string;
  label: string;
  prefix: string;
  description: string;
  owner: string | null;
  directoryPatterns: string[];
  acCount: number;
  byStatus: StatusSlice[];
  mappedComponent: string | null; // component id this namespace maps to, if any
}

export interface TypeStat {
  type: string;
  label: string;
  hsl: string;
  count: number;
  documented: number;
}

export interface OverviewVM {
  totalComponents: number;
  totalTypes: number;
  documented: number;
  totalNamespaces: number;
  totalAcs: number;
  typeStats: TypeStat[];
}

/* ---------- builders (run server-side; return small serializable data) ---------- */

/** Count ACs whose `component` field matches each AC-store namespace id. */
function acCountByNamespace(acs: AC[]): Map<string, AC[]> {
  const m = new Map<string, AC[]>();
  for (const a of acs) {
    const arr = m.get(a.component);
    if (arr) arr.push(a);
    else m.set(a.component, [a]);
  }
  return m;
}

/** Map a component (id or humanized name) to an AC namespace, if one matches. */
function linkFor(
  c: Component,
  nsByKey: Map<string, AcComponent>,
  acsByNs: Map<string, AC[]>,
): AcLink | null {
  const ns =
    nsByKey.get(normalizeKey(c.id)) ?? nsByKey.get(normalizeKey(c.name));
  if (!ns) return null;
  return { nsId: ns.id, prefix: ns.prefix, acCount: acsByNs.get(ns.id)?.length ?? 0 };
}

/** Build the per-type clusters (the component map) with AC cross-links folded in. */
export function buildClusters(
  components: Component[],
  acComponents: AcComponent[],
  acs: AC[],
  colors: Record<string, string>,
): TypeCluster[] {
  const nsByKey = new Map(acComponents.map((n) => [normalizeKey(n.id), n]));
  const acsByNs = acCountByNamespace(acs);

  const byType = new Map<string, ComponentVM[]>();
  for (const c of components) {
    const vm: ComponentVM = {
      id: c.id,
      name: c.name,
      type: c.type,
      description: c.description,
      detailRef: c.detailRef,
      status: c.status,
      primaryCode: c.primaryCode,
      acLink: linkFor(c, nsByKey, acsByNs),
    };
    const arr = byType.get(c.type);
    if (arr) arr.push(vm);
    else byType.set(c.type, [vm]);
  }

  return Array.from(byType.entries())
    .map(([type, comps]) => ({
      type,
      label: humanize(type),
      hsl: colors[type] ?? "150 64% 52%",
      total: comps.length,
      documented: comps.filter((c) => c.detailRef).length,
      components: comps.sort((a, b) => a.name.localeCompare(b.name)),
    }))
    .sort((a, b) => b.total - a.total || a.label.localeCompare(b.label));
}

/** Build the 13 AC-namespace facet cards with per-status bars. */
export function buildNamespaceFacets(
  acComponents: AcComponent[],
  acs: AC[],
  components: Component[],
): NamespaceFacet[] {
  const acsByNs = acCountByNamespace(acs);
  const compByKey = new Map(components.map((c) => [normalizeKey(c.id), c]));

  const order: (keyof typeof WORK_STATUS_TONE)[] = [
    "done",
    "in_progress",
    "todo",
    "not_started",
    "blocked",
    "unknown",
  ];

  return acComponents
    .map((ns) => {
      const list = acsByNs.get(ns.id) ?? [];
      const counts = new Map<string, number>();
      for (const a of list) counts.set(a.workStatus, (counts.get(a.workStatus) ?? 0) + 1);
      const byStatus: StatusSlice[] = order
        .filter((k) => (counts.get(k) ?? 0) > 0)
        .map((k) => ({
          key: k,
          label: WORK_STATUS_TONE[k].label,
          hsl: WORK_STATUS_TONE[k].hsl,
          count: counts.get(k) ?? 0,
        }));
      const mapped = compByKey.get(normalizeKey(ns.id));
      return {
        id: ns.id,
        label: humanize(ns.id),
        prefix: ns.prefix,
        description: ns.description,
        owner: ns.owner,
        directoryPatterns: ns.directoryPatterns,
        acCount: list.length,
        byStatus,
        mappedComponent: mapped?.id ?? null,
      };
    })
    .sort((a, b) => b.acCount - a.acCount);
}

/** Top-level stats: totals, documentation coverage, and per-type breakdown. */
export function buildOverview(
  clusters: TypeCluster[],
  components: Component[],
  acComponents: AcComponent[],
  acs: AC[],
): OverviewVM {
  return {
    totalComponents: components.length,
    totalTypes: clusters.length,
    documented: components.filter((c) => c.detailRef).length,
    totalNamespaces: acComponents.length,
    totalAcs: acs.length,
    typeStats: clusters.map((c) => ({
      type: c.type,
      label: c.label,
      hsl: c.hsl,
      count: c.total,
      documented: c.documented,
    })),
  };
}
