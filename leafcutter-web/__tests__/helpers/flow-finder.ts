/**
 * Shared helpers for the UXP-617-1 finder tests (pure core side). Not a test
 * file (no .test suffix); vitest does not collect it.
 *
 * Planned design pinned here (IT-PO 2026-10-14, ticket UXP-617-1 "Delivers To"):
 *  - leafcutter-web/lib/flow-finder/ is one pure, isomorphic module set. Which
 *    file inside it exports what is the coder's choice, so every export is
 *    looked up across ALL files of the folder.
 *  - buildFinderIndex(flows) -> { flows: [...], nodes: [...] }
 *  - runFinder(index, { q, facets: { product, actor, kind, realization, level,
 *    uses, produces, io, entity, screen: string[] } }) -> { statusText,
 *    resultCount: { flows, steps }, results, facetCounts, appliedChips,
 *    clearAllHref, emptyState }
 *  - Replay tests compare against the dataset's FlowFinderQuery records. The
 *    nested field names inside results / chips / empty state follow the
 *    FlowFinderQuery shape; normalizeRun() reads camelCase or snake_case so
 *    the casing is not what these tests pin.
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
export const WEB_ROOT = path.resolve(HERE, "../..");
export const REPO_ROOT = path.resolve(WEB_ROOT, "..");
export const DATASET_PATH = path.join(
  REPO_ROOT,
  "docs/product-truth/mock-data/leafcutter/atlas-flows.mock.json",
);
export const FLOWS_DIR = path.join(REPO_ROOT, "docs/product-truth/flows");
export const FIXTURE_DIR = path.join(WEB_ROOT, "fixtures/flow-finder");

/**
 * A literal import() of an absent module makes vite fail the WHOLE test file at
 * transform time ("no tests"). import.meta.glob yields no entry for an absent
 * folder instead, so each test reports its own red state (module absent).
 */
const coreModules = import.meta.glob("../../lib/flow-finder/*.ts") as Record<
  string,
  () => Promise<Record<string, unknown>>
>;

export async function core(): Promise<Record<string, any>> {
  const keys = Object.keys(coreModules);
  if (keys.length === 0) {
    throw new Error("module absent: leafcutter-web/lib/flow-finder/ does not exist yet");
  }
  const merged: Record<string, any> = {};
  for (const k of keys) Object.assign(merged, await coreModules[k]());
  return merged;
}

export async function coreFn<T extends (...a: any[]) => any = (...a: any[]) => any>(
  name: string,
): Promise<T> {
  const c = await core();
  if (typeof c[name] !== "function") {
    throw new Error(`absent: leafcutter-web/lib/flow-finder/ does not export ${name}()`);
  }
  return c[name] as T;
}

export const FACETS = [
  "product",
  "actor",
  "kind",
  "realization",
  "level",
  "uses",
  "produces",
  "io",
  "entity",
  "screen",
] as const;
export type FacetName = (typeof FACETS)[number];
export type FinderState = { q: string | null; facets: Record<FacetName, string[]> };

export function emptyFacets(): Record<FacetName, string[]> {
  return Object.fromEntries(FACETS.map((f) => [f, [] as string[]])) as Record<FacetName, string[]>;
}

export function stateOf(q: string | null, facets: Partial<Record<FacetName, string[]>> = {}): FinderState {
  return { q, facets: { ...emptyFacets(), ...facets } };
}

// ---------------------------------------------------------------- dataset

let datasetCache: any = null;
export function dataset(): any {
  datasetCache ??= JSON.parse(fs.readFileSync(DATASET_PATH, "utf8"));
  return datasetCache;
}

/** One FlowFinderQuery record of the leafcutter/atlas-flows v4 dataset, verbatim. */
export function finderRecord(id: string): any {
  const rec = dataset().entities.FlowFinderQuery.records.find((r: any) => r.id === id);
  if (!rec) throw new Error(`dataset has no FlowFinderQuery '${id}'`);
  return rec;
}

export function stateOfRecord(rec: any): FinderState {
  return stateOf(rec.q ?? null, rec.facets);
}

// ------------------------------------------------------------------ index

/**
 * The index the replays run over: the frozen fixture under
 * fixtures/flow-finder/ when it exists (the measurement-commit index the
 * dataset's numbers were taken from). Without it the index is built from the
 * flow store the repo holds today, through the planned buildFinderIndex().
 */
export async function frozenIndex(): Promise<any> {
  if (fs.existsSync(FIXTURE_DIR)) {
    for (const f of fs.readdirSync(FIXTURE_DIR).filter((n) => n.endsWith(".json")).sort()) {
      const parsed = JSON.parse(fs.readFileSync(path.join(FIXTURE_DIR, f), "utf8"));
      const idx = parsed.index ?? parsed;
      if (Array.isArray(idx.flows) && Array.isArray(idx.nodes)) return idx;
    }
  }
  return storeIndex();
}

/** The finder index of the flow store as loaded by the Flows view today. */
export async function storeIndex(): Promise<any> {
  const build = await coreFn("buildFinderIndex");
  const { getFlows } = await import("@/lib/data/flows");
  return build(getFlows());
}

// ------------------------------------------------------- run + normalizing

const snake = (k: string) => k.replace(/[A-Z]/g, (m) => "_" + m.toLowerCase());

function deepSnake(v: any): any {
  if (Array.isArray(v)) return v.map(deepSnake);
  if (v && typeof v === "object") {
    return Object.fromEntries(Object.entries(v).map(([k, x]) => [snake(k), deepSnake(x)]));
  }
  return v;
}

export type FinderRun = {
  status_text: string;
  result_count: { flows: number; steps: number };
  results: Array<{
    flow_id: string;
    flow_name: string;
    href: string;
    flow_match: string | null;
    matching_steps: number;
    more_steps: number;
    step_rows: Array<{
      node_id: string;
      node_kind: string;
      label: string;
      actor_kind: string;
      actor_label: string;
      reason: string;
      href: string;
    }>;
  }>;
  facet_counts: Record<string, Record<string, number>>;
  applied_chips: Array<{ facet: string; value: string; label: string; remove_href: string }>;
  clear_all_href: string | null;
  empty_state: null | {
    title: string;
    detail?: string;
    suggestions: Array<{ label: string; href: string; flows: number }>;
  };
};

/** runFinder() output as the FlowFinderQuery shape: snake_case keys, facet maps untouched. */
export function normalizeRun(out: any): FinderRun {
  const res: Record<string, any> = {};
  for (const [k, v] of Object.entries(out)) {
    res[snake(k)] = snake(k) === "facet_counts" ? v : deepSnake(v);
  }
  return res as FinderRun;
}

export async function run(index: any, state: FinderState): Promise<FinderRun> {
  const runFinder = await coreFn("runFinder");
  return normalizeRun(runFinder(index, state));
}

/** Replay one dataset FlowFinderQuery over an index; returns the record and the run. */
export async function replay(id: string, index?: any): Promise<{ rec: any; out: FinderRun }> {
  const rec = finderRecord(id);
  const idx = index ?? (await frozenIndex());
  return { rec, out: await run(idx, stateOfRecord(rec)) };
}

export const flowIds = (r: FinderRun) => r.results.map((x) => x.flow_id);

/** The record's result list reduced to the fields every replay compares. */
export const cards = (results: any[]) =>
  results.map((r) => ({
    flow_id: r.flow_id,
    flow_name: r.flow_name,
    href: r.href,
    flow_match: r.flow_match,
    matching_steps: r.matching_steps,
    more_steps: r.more_steps,
  }));

export const rowsOf = (results: any[]) =>
  results.map((r) => ({
    flow_id: r.flow_id,
    rows: r.step_rows.map((s: any) => ({
      node_id: s.node_id,
      node_kind: s.node_kind,
      label: s.label,
      actor_kind: s.actor_kind,
      actor_label: s.actor_label,
      reason: s.reason,
      href: s.href,
    })),
  }));

// ----------------------------------------------- raw flow files (real data)

/** Every stored *.flow.json read straight from disk, independent of the loader. */
export function rawFlowFiles(): Array<{ id: string; doc: any }> {
  const out: Array<{ id: string; doc: any }> = [];
  const walk = (dir: string) => {
    for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
      const p = path.join(dir, e.name);
      if (e.isDirectory()) walk(p);
      else if (e.name.endsWith(".flow.json")) {
        const doc = JSON.parse(fs.readFileSync(p, "utf8"));
        out.push({ id: String(doc.id), doc });
      }
    }
  };
  walk(FLOWS_DIR);
  return out;
}
