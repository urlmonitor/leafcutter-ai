import "server-only";
import path from "node:path";
import { parse as parseYaml } from "yaml";
import { repoPath, walk, readFileSafe, rel } from "./repo";
import type {
  AC,
  AcComponent,
  AcLevel,
  Complexity,
  Priority,
  Readiness,
  WorkStatus,
} from "./types";

const AC_DIR = "docs/acceptance-criteria";

function normLevel(v: unknown): AcLevel {
  const s = String(v ?? "").toUpperCase();
  return (["L0", "L1", "L2", "L3"] as readonly string[]).includes(s)
    ? (s as AcLevel)
    : "L2";
}

function normWorkStatus(v: unknown): WorkStatus {
  const s = String(v ?? "").toLowerCase().replace(/[\s-]+/g, "_");
  if (s === "done" || s === "complete" || s === "completed") return "done";
  if (s === "in_progress" || s === "wip" || s === "building") return "in_progress";
  if (s === "blocked") return "blocked";
  if (s === "todo" || s === "ready" || s === "pending") return "todo";
  if (s === "not_started" || s === "" ) return s === "" ? "unknown" : "not_started";
  return "unknown";
}

function normReadiness(v: unknown): Readiness {
  const s = String(v ?? "").toLowerCase();
  return (["draft", "reviewed", "approved"] as readonly string[]).includes(s)
    ? (s as Readiness)
    : "unknown";
}

function normPriority(v: unknown): Priority {
  const s = String(v ?? "").toLowerCase();
  return (["critical", "high", "medium", "low"] as readonly string[]).includes(s)
    ? (s as Priority)
    : "unknown";
}

function normComplexity(v: unknown): Complexity {
  const s = String(v ?? "").toUpperCase();
  return (["S", "M", "L", "XL"] as readonly string[]).includes(s)
    ? (s as Complexity)
    : "unknown";
}

function asArray(v: unknown): string[] {
  if (Array.isArray(v)) return v.map((x) => String(x)).filter(Boolean);
  if (v == null || v === "") return [];
  return [String(v)];
}

function normExpectsFrom(v: unknown): { id: string; reason: string }[] {
  if (v == null) return [];
  if (Array.isArray(v)) return v.map((x) => ({ id: String(x), reason: "" }));
  if (typeof v === "object") {
    return Object.entries(v as Record<string, unknown>).map(([id, reason]) => ({
      id,
      reason: String(reason ?? ""),
    }));
  }
  return [];
}

/** Load and parse the AC-store component registry (index.yaml). */
export function loadAcComponents(): AcComponent[] {
  const raw = readFileSafe(repoPath(AC_DIR, "index.yaml"));
  if (!raw) return [];
  try {
    const doc = parseYaml(raw) as { components?: unknown[] };
    const list = Array.isArray(doc?.components) ? doc.components : [];
    return list.map((c) => {
      const o = c as Record<string, unknown>;
      return {
        id: String(o.id ?? ""),
        prefix: String(o.prefix ?? ""),
        description: String(o.description ?? ""),
        owner: o.owner ? String(o.owner) : null,
        directoryPatterns: asArray(o.directory_patterns),
      };
    }).filter((c) => c.id);
  } catch {
    return [];
  }
}

let _acCache: AC[] | null = null;

/** Load every AC YAML file under the store, normalized. Cached per-process. */
export function loadAcs(): AC[] {
  if (_acCache) return _acCache;
  const dir = repoPath(AC_DIR);
  const files = walk(dir, ".yaml").filter(
    (f) => path.basename(f) !== "index.yaml",
  );
  const acs: AC[] = [];
  for (const file of files) {
    const raw = readFileSafe(file);
    if (!raw) continue;
    let doc: Record<string, unknown> | null = null;
    try {
      doc = parseYaml(raw) as Record<string, unknown>;
    } catch {
      continue;
    }
    if (!doc || typeof doc !== "object" || !doc.id) continue;
    acs.push({
      id: String(doc.id),
      title: String(doc.title ?? doc.id),
      component: String(doc.component ?? path.basename(path.dirname(file))),
      level: normLevel(doc.level),
      status: String(doc.status ?? "active"),
      reqStatus: String(doc.req_status ?? ""),
      workStatus: normWorkStatus(doc.work_status),
      workStatusRaw: String(doc.work_status ?? "unknown"),
      readiness: normReadiness(doc.readiness),
      priority: normPriority(doc.priority),
      complexity: normComplexity(doc.estimated_complexity),
      criteria: String(doc.criteria ?? "").trim(),
      dependsOn: asArray(doc.depends_on),
      deliversTo: doc.delivers_to ? String(doc.delivers_to) : null,
      expectsFrom: normExpectsFrom(doc.expects_from),
      docLinks: asArray(doc.doc_links),
      assignedAgent: doc.assigned_agent ? String(doc.assigned_agent) : null,
      itRequirements: String(doc.it_requirements ?? "").trim(),
      originAgent: doc.origin_agent ? String(doc.origin_agent) : null,
      created: doc.created ? String(doc.created) : null,
      createdByTicket: doc.created_by_ticket ? String(doc.created_by_ticket) : null,
      amendedBy: asArray(doc.amended_by),
      supersededBy: doc.superseded_by ? String(doc.superseded_by) : null,
      coveredBy: asArray(doc.covered_by),
      implementedBy: asArray(doc.implemented_by),
      changeTarget: doc.change_target ? String(doc.change_target) : null,
      riskSurface: doc.risk_surface ? String(doc.risk_surface) : null,
      implementsPattern: doc.implements_pattern ? String(doc.implements_pattern) : null,
      filePath: rel(file),
    });
  }
  acs.sort((a, b) => a.id.localeCompare(b.id, undefined, { numeric: true }));
  _acCache = acs;
  return acs;
}

/** Fast lookup of a single AC by id. */
export function acById(id: string): AC | undefined {
  return loadAcs().find((a) => a.id === id);
}
