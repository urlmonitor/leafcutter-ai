/**
 * Pure flow impl-summary derivation — no fs / no network / no server-only import.
 * Safe to run client-side and unit-testable in isolation.
 *
 * Extracted from flows.ts (server-only) per UXP-600 it_requirements:
 *   "Derivation must be a pure function (no fs / no network) safe for client use."
 */
import type { FlowBranch, FlowImplSummary, FlowStep, WorkStatus } from "./types";

/**
 * Derive the implementation summary from a flow's steps and branches.
 *
 * Deduplicates AC ids across steps and branches: an AC referenced by multiple
 * steps counts once in acTotal / acDone, mirroring the seenAc logic in graph.ts.
 *
 * @param flow  - object with `steps` and `branches` arrays (accepts a full Flow or a subset)
 * @param asof  - optional as-of timestamp to carry through to the summary
 */
export function deriveImplSummary(
  flow: { steps: FlowStep[]; branches: FlowBranch[] },
  asof: string | null = null,
): FlowImplSummary {
  const { steps, branches } = flow;

  const all: WorkStatus[] = [
    ...steps.map((s) => s.implStatus),
    ...branches.map((b) => b.implStatus),
  ];

  // Deduped AC-level rollup: iterate all steps+branches, count each AC id once.
  // An AC referenced by multiple steps counts once (mirrors seenAc in graph.ts).
  const seenAcId = new Set<string>();
  let acDone = 0;
  let acTotal = 0;
  for (const item of [...steps, ...branches]) {
    for (const ac of item.acs) {
      if (seenAcId.has(ac.id)) continue;
      seenAcId.add(ac.id);
      acTotal++;
      if (ac.workStatus === "done") acDone++;
    }
  }

  return {
    done: all.filter((s) => s === "done").length,
    in_progress: all.filter((s) => s === "in_progress").length,
    not_started: all.filter((s) => s !== "done" && s !== "in_progress").length,
    total: all.length,
    asof,
    acDone,
    acTotal,
  };
}
