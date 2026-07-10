import "server-only";
import { repoPath, readFileSafe } from "./repo";
import type { Roadmap, RoadmapPhase } from "./types";

const EMPTY: Roadmap = {
  currentPhase: "",
  currentOutcome: "",
  phases: [],
};

/** Load docs/roadmap.json — phases, exit criteria, current outcome. */
export function loadRoadmap(): Roadmap {
  const raw = readFileSafe(repoPath("docs", "roadmap.json"));
  if (!raw) return EMPTY;
  let doc: Record<string, unknown>;
  try {
    doc = JSON.parse(raw);
  } catch {
    return EMPTY;
  }
  const phases: RoadmapPhase[] = Array.isArray(doc.phases)
    ? (doc.phases as unknown[]).map((p) => {
        const o = p as Record<string, unknown>;
        return {
          id: String(o.id ?? ""),
          title: String(o.title ?? o.id ?? ""),
          status: String(o.status ?? "planned"),
          description: String(o.description ?? ""),
          exitCriteria: Array.isArray(o.exit_criteria)
            ? (o.exit_criteria as unknown[]).map((x) => String(x))
            : [],
          ticketsAdvancingOutcome: Array.isArray(o.tickets_advancing_outcome)
            ? (o.tickets_advancing_outcome as unknown[]).map((x) => String(x))
            : [],
        };
      })
    : [];
  return {
    currentPhase: String(doc.current_phase ?? ""),
    currentOutcome: String(doc.current_outcome ?? ""),
    phases,
  };
}
