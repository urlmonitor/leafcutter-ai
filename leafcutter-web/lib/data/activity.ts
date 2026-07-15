import "server-only";
import fs from "node:fs";
import { repoPath } from "./repo";
import type { ActivityItem, Ticket } from "./types";

/**
 * "What is being worked on right now."
 *
 * Ground truth: there is NO telemetry log in the repo by default (it's created
 * on-demand during a drive), so the reliable live signal is static ticket state:
 * in-progress LEAF tickets carry an `agents:` phase-chain map. Epic Master_Plan
 * markers also go in-progress but are epic-level and often stale — surfaced
 * separately and clearly.
 */

function isEpicMarker(t: Ticket): boolean {
  return t.lifecycle === "epic" || /master_plan/i.test(t.slug);
}

export function computeActivity(tickets: Ticket[]): {
  inProgress: ActivityItem[];
  inFlightEpics: Ticket[];
  telemetryAvailable: boolean;
} {
  const inProgressTickets = tickets.filter((t) => t.status === "in_progress");

  const inProgress: ActivityItem[] = inProgressTickets
    .filter((t) => !isEpicMarker(t))
    .map((t) => {
      const active = t.agents.filter((a) => a.status === "needed").map((a) => a.name);
      const failed = t.agents.filter((a) => a.status === "failed").map((a) => a.name);
      const done = t.agents.filter((a) => a.status === "signed_off").map((a) => a.name);
      const tr = t.acTraceability;
      const sourceAcs = tr ? [...tr.l0, ...tr.l1, ...tr.l2, ...tr.l3] : [];
      return { ticket: t, activePhases: active, failedPhases: failed, donePhases: done, sourceAcs };
    })
    // Most interesting first: failing, then those with active phases, then rest.
    .sort((a, b) => {
      const score = (x: ActivityItem) => x.failedPhases.length * 2 + (x.activePhases.length > 0 ? 1 : 0);
      return score(b) - score(a);
    });

  const inFlightEpics = inProgressTickets.filter(isEpicMarker);

  let telemetryAvailable = false;
  try {
    const p = repoPath("debugging", "logs", "agent_telemetry.jsonl");
    telemetryAvailable = fs.existsSync(p) && fs.statSync(p).size > 0;
  } catch {
    telemetryAvailable = false;
  }

  return { inProgress, inFlightEpics, telemetryAvailable };
}
