import "server-only";
import { repoPath, walk, readFileSafe, rel } from "./repo";
import { acById } from "./ac-store";
import type {
  AcRef,
  Flow,
  FlowAppearance,
  FlowBranch,
  FlowImplSummary,
  FlowKind,
  FlowLevel,
  FlowScenario,
  FlowSource,
  FlowStep,
  MockData,
  MockEntity,
  MockField,
  WorkStatus,
} from "./types";

const PT_DIR = "docs/product-truth";
const FLOWS_DIR = "docs/product-truth/flows";
const MOCK_DIR = "docs/product-truth/mock-data";

function asArray(v: unknown): string[] {
  if (Array.isArray(v)) return v.map((x) => String(x)).filter(Boolean);
  if (v == null || v === "") return [];
  return [String(v)];
}

/** Normalize a raw work/impl-status string to the canonical enum. */
function normWork(v: unknown): WorkStatus {
  const s = String(v ?? "").toLowerCase().replace(/[\s-]+/g, "_");
  if (s === "done" || s === "complete" || s === "completed") return "done";
  if (s === "in_progress" || s === "wip" || s === "building") return "in_progress";
  if (s === "blocked") return "blocked";
  if (s === "todo" || s === "ready" || s === "pending") return "todo";
  if (s === "not_started") return "not_started";
  return "unknown";
}

/** Normalize the flow `kind` field (defaults to "user"). */
function normKind(v: unknown): FlowKind {
  const s = String(v ?? "").toLowerCase();
  return s === "data" || s === "architecture" ? (s as FlowKind) : "user";
}

/** Normalize the flow `source` field (defaults to "mock"). */
function normSource(v: unknown): FlowSource {
  const s = String(v ?? "").toLowerCase();
  return s === "real" ? "real" : "mock";
}

/** Normalize the flow `level` field (defaults to "journey"). */
function normLevel(v: unknown): FlowLevel {
  const s = String(v ?? "").toLowerCase();
  return s === "pipeline" || s === "agent" ? (s as FlowLevel) : "journey";
}

/** Resolve each implements AC id to its LIVE store status. */
function resolveAcs(implementsIds: string[], fallback: WorkStatus): AcRef[] {
  return implementsIds.map((id) => {
    const ac = acById(id);
    if (ac) {
      return {
        id,
        title: ac.title,
        level: ac.level,
        workStatus: ac.workStatus,
        resolved: true,
      };
    }
    return { id, title: id, level: "L2", workStatus: fallback, resolved: false };
  });
}

/**
 * Roll a step's AC statuses up into a single live implementation status.
 *   - no implements, or every status is todo/not_started/unknown -> "not_started"
 *   - every status is "done"                                       -> "done"
 *   - otherwise                                                    -> "in_progress"
 * Unresolved AC ids fall back to the flow's own declared impl_status.
 */
function rollupStatus(acs: AcRef[], fallback: WorkStatus): WorkStatus {
  if (acs.length === 0) return "not_started";
  const statuses = acs.map((a) => (a.resolved ? a.workStatus : fallback));
  if (statuses.every((s) => s === "done")) return "done";
  const dormant: WorkStatus[] = ["todo", "not_started", "unknown"];
  if (statuses.every((s) => dormant.includes(s))) return "not_started";
  return "in_progress";
}

function parseStep(raw: Record<string, unknown>): FlowStep {
  const implementsIds = asArray(raw.implements);
  const fallbackStatus = normWork(raw.impl_status);
  const acs = resolveAcs(implementsIds, fallbackStatus);
  return {
    id: String(raw.id ?? ""),
    label: String(raw.label ?? raw.id ?? ""),
    human: String(raw.human ?? ""),
    order: Number(raw.order ?? 0),
    screen: raw.screen ? String(raw.screen) : null,
    agent: raw.agent ? String(raw.agent) : null,
    produces: asArray(raw.produces),
    consumes: asArray(raw.consumes),
    reads: asArray(raw.reads),
    writes: asArray(raw.writes),
    implements: implementsIds,
    implStatus: rollupStatus(acs, fallbackStatus),
    fallbackStatus,
    acs,
    expandsTo: raw.expands_to ? String(raw.expands_to) : null,
  };
}

function parseBranch(raw: Record<string, unknown>): FlowBranch {
  const implementsIds = asArray(raw.implements);
  const fallbackStatus = normWork(raw.impl_status);
  const acs = resolveAcs(implementsIds, fallbackStatus);
  return {
    id: String(raw.id ?? ""),
    from: String(raw.from ?? ""),
    condition: String(raw.condition ?? ""),
    label: String(raw.label ?? raw.id ?? ""),
    human: String(raw.human ?? ""),
    screen: raw.screen ? String(raw.screen) : null,
    agent: raw.agent ? String(raw.agent) : null,
    produces: asArray(raw.produces),
    consumes: asArray(raw.consumes),
    reads: asArray(raw.reads),
    writes: asArray(raw.writes),
    implements: implementsIds,
    implStatus: rollupStatus(acs, fallbackStatus),
    fallbackStatus,
    acs,
    expandsTo: raw.expands_to ? String(raw.expands_to) : null,
  };
}

function parseScenarios(v: unknown): FlowScenario[] {
  if (!Array.isArray(v)) return [];
  return v.map((s) => {
    const o = s as Record<string, unknown>;
    return {
      for: String(o.for ?? ""),
      given: String(o.given ?? ""),
      when: String(o.when ?? ""),
      then: String(o.then ?? ""),
    };
  });
}

/** Derive the impl summary from the LIVE per-step/branch status. */
function deriveImplSummary(
  steps: FlowStep[],
  branches: FlowBranch[],
  asof: string | null,
): FlowImplSummary {
  const all: WorkStatus[] = [
    ...steps.map((s) => s.implStatus),
    ...branches.map((b) => b.implStatus),
  ];
  return {
    done: all.filter((s) => s === "done").length,
    in_progress: all.filter((s) => s === "in_progress").length,
    not_started: all.filter((s) => s !== "done" && s !== "in_progress").length,
    total: all.length,
    asof,
  };
}

function parseFlow(raw: Record<string, unknown>, file: string): Flow | null {
  if (!raw || typeof raw !== "object" || !raw.id) return null;
  const steps = (Array.isArray(raw.steps) ? raw.steps : [])
    .map((s) => parseStep(s as Record<string, unknown>))
    .filter((s) => s.id);
  const branches = (Array.isArray(raw.branches) ? raw.branches : [])
    .map((b) => parseBranch(b as Record<string, unknown>))
    .filter((b) => b.id);
  const summaryRaw = raw.impl_summary as Record<string, unknown> | undefined;
  const asof = summaryRaw?.asof ? String(summaryRaw.asof) : null;
  return {
    id: String(raw.id),
    component: String(raw.component ?? ""),
    product: raw.product ? String(raw.product) : null,
    name: String(raw.name ?? raw.id),
    summary: String(raw.summary ?? ""),
    kind: normKind(raw.kind),
    source: normSource(raw.source),
    level: normLevel(raw.level),
    status: String(raw.status ?? "active"),
    readiness: String(raw.readiness ?? "unknown"),
    entities: asArray(raw.entities),
    mockDataRef: raw.mock_data_ref ? String(raw.mock_data_ref) : null,
    steps,
    branches,
    scenarios: parseScenarios(raw.acceptance_scenarios),
    implSummary: deriveImplSummary(steps, branches, asof),
    filePath: rel(file),
  };
}

function parseMockEntities(v: unknown): MockEntity[] {
  if (!v || typeof v !== "object") return [];
  return Object.entries(v as Record<string, unknown>).map(([name, body]) => {
    const o = (body ?? {}) as Record<string, unknown>;
    const fieldsObj = (o.fields ?? {}) as Record<string, unknown>;
    const fields: MockField[] = Object.entries(fieldsObj).map(([fname, spec]) => ({
      name: fname,
      spec: String(spec ?? ""),
    }));
    const records = Array.isArray(o.records)
      ? (o.records as Record<string, unknown>[])
      : [];
    return { name, fields, records };
  });
}

function parseMock(raw: Record<string, unknown>, file: string): MockData | null {
  if (!raw || typeof raw !== "object" || !raw.id) return null;
  return {
    id: String(raw.id),
    component: String(raw.component ?? ""),
    entities: parseMockEntities(raw.entities),
    filePath: rel(file),
  };
}

let _flowCache: Flow[] | null = null;
let _mockCache: MockData[] | null = null;

/** Load every *.flow.json under the product-truth store, normalized. Cached. */
export function getFlows(): Flow[] {
  if (_flowCache) return _flowCache;
  const flows: Flow[] = [];
  for (const file of walk(repoPath(FLOWS_DIR), ".flow.json")) {
    const rawStr = readFileSafe(file);
    if (!rawStr) continue;
    let doc: Record<string, unknown> | null = null;
    try {
      doc = JSON.parse(rawStr) as Record<string, unknown>;
    } catch {
      continue;
    }
    const flow = parseFlow(doc, file);
    if (flow) flows.push(flow);
  }
  flows.sort((a, b) => a.id.localeCompare(b.id));
  _flowCache = flows;
  return flows;
}

/** Load every *.mock.json under the product-truth store, normalized. Cached. */
export function getMockData(): MockData[] {
  if (_mockCache) return _mockCache;
  const mocks: MockData[] = [];
  for (const file of walk(repoPath(MOCK_DIR), ".mock.json")) {
    const rawStr = readFileSafe(file);
    if (!rawStr) continue;
    let doc: Record<string, unknown> | null = null;
    try {
      doc = JSON.parse(rawStr) as Record<string, unknown>;
    } catch {
      continue;
    }
    const mock = parseMock(doc, file);
    if (mock) mocks.push(mock);
  }
  _mockCache = mocks;
  return mocks;
}

/** Fast lookup of a single flow by id. */
export function flowById(id: string): Flow | undefined {
  return getFlows().find((f) => f.id === id);
}

/** Fast lookup of a single mock-data artifact by id. */
export function mockById(id: string): MockData | undefined {
  return getMockData().find((m) => m.id === id);
}

/**
 * Reverse index: AC id -> the flow steps/branches that implement it.
 * Powers the "Appears in flows" section of the AC detail drawer.
 */
export function flowAppearancesByAc(): Record<string, FlowAppearance[]> {
  const index: Record<string, FlowAppearance[]> = {};
  const add = (
    acId: string,
    flow: Flow,
    stepId: string,
    stepLabel: string,
  ) => {
    (index[acId] ??= []).push({
      flowId: flow.id,
      flowName: flow.name,
      stepId,
      stepLabel,
    });
  };
  for (const flow of getFlows()) {
    for (const s of flow.steps) {
      for (const id of s.implements) add(id, flow, s.id, s.label);
    }
    for (const b of flow.branches) {
      for (const id of b.implements) add(id, flow, b.id, b.label);
    }
  }
  return index;
}

// Referenced to keep the product-truth root path documented alongside the loader.
export const PRODUCT_TRUTH_DIR = PT_DIR;
