import "server-only";
import path from "node:path";
import matter from "gray-matter";
import { repoPath, walk, readFileSafe, rel } from "./repo";
import type { Priority, Ticket } from "./types";

const TICKETS_DIR = "tickets";

function normPriority(v: unknown): Priority {
  const s = String(v ?? "").toLowerCase();
  return (["critical", "high", "medium", "low"] as readonly string[]).includes(s)
    ? (s as Priority)
    : "unknown";
}

function asArray(v: unknown): string[] {
  if (Array.isArray(v)) return v.map((x) => String(x)).filter(Boolean);
  if (v == null || v === "") return [];
  return [String(v)];
}

function classify(relPath: string): { lifecycle: Ticket["lifecycle"]; epic: string | null } {
  const parts = relPath.split("/");
  const epicIdx = parts.findIndex((p) => p.startsWith("EPIC-"));
  const epic = epicIdx >= 0 ? parts[epicIdx] : null;
  if (relPath.includes("/99_done/") || parts.includes("done")) {
    return { lifecycle: "done", epic };
  }
  if (epic) return { lifecycle: "epic", epic };
  if (relPath.includes("/00_inbox/")) return { lifecycle: "inbox", epic: null };
  return { lifecycle: "other", epic: null };
}

function normAgents(v: unknown): { name: string; status: string }[] {
  if (!v || typeof v !== "object" || Array.isArray(v)) return [];
  return Object.entries(v as Record<string, unknown>).map(([name, status]) => ({
    name,
    status: String(status ?? ""),
  }));
}

function normTraceability(v: unknown): Ticket["acTraceability"] {
  if (!v || typeof v !== "object") return null;
  const o = v as Record<string, unknown>;
  return {
    l0: asArray(o.l0),
    l1: asArray(o.l1),
    l2: asArray(o.l2),
    l3: asArray(o.l3),
    acPath: o.ac_path ? String(o.ac_path) : null,
  };
}

let _ticketCache: Ticket[] | null = null;

/** Load every ticket markdown file (frontmatter only; body is not retained). */
export function loadTickets(): Ticket[] {
  if (_ticketCache) return _ticketCache;
  const dir = repoPath(TICKETS_DIR);
  const files = walk(dir, ".md").filter(
    (f) => path.basename(f).toUpperCase() !== "README.MD",
  );
  const tickets: Ticket[] = [];
  for (const file of files) {
    const raw = readFileSafe(file);
    if (!raw) continue;
    let fm: Record<string, unknown>;
    try {
      fm = matter(raw).data as Record<string, unknown>;
    } catch {
      continue;
    }
    const relPath = rel(file);
    const { lifecycle, epic } = classify(relPath);
    const slug = path.basename(file, ".md");
    tickets.push({
      slug,
      title: String(fm.title ?? slug),
      status: String(fm.status ?? "unknown"),
      lifecycle,
      epic,
      components: asArray(fm.components),
      created: fm.created ? String(fm.created) : null,
      dependsOn: asArray(fm.depends_on),
      priority: normPriority(fm.priority),
      roadmapPhase: fm.roadmap_phase ? String(fm.roadmap_phase) : null,
      advancesOutcome: Boolean(fm.advances_current_outcome),
      requiresDiagram: Boolean(fm.requires_diagram),
      requiresAdr: Boolean(fm.requires_adr),
      filesTouched: asArray(fm.files_touched),
      agents: normAgents(fm.agents),
      acTraceability: normTraceability(fm.ac_traceability),
      filePath: relPath,
    });
  }
  tickets.sort((a, b) => (b.created ?? "").localeCompare(a.created ?? ""));
  _ticketCache = tickets;
  return tickets;
}

/** Group tickets by their epic folder (null epic excluded). */
export function ticketsByEpic(): Record<string, Ticket[]> {
  const out: Record<string, Ticket[]> = {};
  for (const t of loadTickets()) {
    if (!t.epic) continue;
    (out[t.epic] ??= []).push(t);
  }
  return out;
}
