import "server-only";
import { loadAcs, loadAcComponents } from "./ac-store";
import { loadTickets } from "./tickets";
import { loadComponents } from "./components";
import { loadRoadmap } from "./roadmap";
import { loadAgents } from "./agents";
import { loadCoverage, totalTestFiles } from "./tests";
import { enrichBacklog, computeNextUp } from "./backlog";
import { computeActivity } from "./activity";
import { computeTraceability } from "./traceability";
import type {
  AC,
  AcLevel,
  AtlasSnapshot,
  Counts,
  CoverageStats,
  Ticket,
} from "./types";

const LEVELS: AcLevel[] = ["L0", "L1", "L2", "L3"];

function tally<T>(items: T[], key: (t: T) => string): Record<string, number> {
  const out: Record<string, number> = {};
  for (const it of items) {
    const k = key(it);
    out[k] = (out[k] ?? 0) + 1;
  }
  return out;
}

function acCounts(acs: AC[]): Counts {
  return {
    total: acs.length,
    byStatus: tally(acs, (a) => a.workStatus),
    byLevel: tally(acs, (a) => a.level),
    byPriority: tally(acs, (a) => a.priority),
    byReadiness: tally(acs, (a) => a.readiness),
    byComponent: tally(acs, (a) => a.component),
  };
}

/** Build the whole-store test-coverage summary. */
function coverageStats(acs: AC[]): CoverageStats {
  const guarded = acs.filter((a) => (a.testCount ?? 0) > 0).length;
  const rolledUpGuarded = acs.filter((a) => (a.testRolledUpCount ?? 0) > 0).length;
  const hist = { "0": 0, "1": 0, "2": 0, "3+": 0 };
  for (const a of acs) {
    const c = a.testCount ?? 0;
    if (c === 0) hist["0"]++;
    else if (c === 1) hist["1"]++;
    else if (c === 2) hist["2"]++;
    else hist["3+"]++;
  }
  const byLevel = LEVELS.map((level) => {
    const inLevel = acs.filter((a) => a.level === level);
    return { level, total: inLevel.length, guarded: inLevel.filter((a) => (a.testCount ?? 0) > 0).length };
  });
  const comps = Array.from(new Set(acs.map((a) => a.component)));
  const byComponent = comps
    .map((component) => {
      const inC = acs.filter((a) => a.component === component);
      return { component, total: inC.length, guarded: inC.filter((a) => (a.testCount ?? 0) > 0).length };
    })
    .sort((a, b) => b.total - a.total);
  return {
    totalAcs: acs.length,
    guarded,
    guardedPct: acs.length ? Math.round((guarded / acs.length) * 100) : 0,
    rolledUpGuarded,
    histogram: Object.entries(hist).map(([bucket, count]) => ({ bucket, count })),
    byLevel,
    byComponent,
    totalTestFiles: totalTestFiles(),
  };
}

/**
 * The single aggregate loader every view consumes. Server-only; call from a
 * Server Component and pass the slices you need into client components.
 *
 * Enriches each AC with test coverage + honest backlog classification, and
 * derives the true "/build-ac" next-up queue, the built-but-unflipped list,
 * coverage stats, and live activity. Loaders are cached per-process.
 */
export function getAtlas(): AtlasSnapshot {
  const acs = loadAcs();
  const tickets = loadTickets();

  // 1. attach test coverage to each AC
  const coverage = loadCoverage();
  for (const ac of acs) {
    const cov = coverage.get(ac.id);
    ac.testCount = cov?.count ?? 0;
    ac.testRefs = cov?.testRefs ?? [];
    ac.testRolledUpCount = cov?.rolledUpCount ?? 0;
  }

  // 2. classify backlog (mutates acs: isLeaf, bucket, blockedBy, derivedDone)
  const backlog = enrichBacklog(acs, tickets);

  return {
    generatedAt: new Date().toISOString(),
    acs,
    acComponents: loadAcComponents(),
    tickets,
    components: loadComponents(),
    roadmap: loadRoadmap(),
    agents: loadAgents(),
    acCounts: acCounts(acs),
    ticketCounts: {
      total: tickets.length,
      byStatus: tally(tickets, (t: Ticket) => t.status),
      byLifecycle: tally(tickets, (t: Ticket) => t.lifecycle),
    },
    backlog: {
      byBucket: backlog.byBucket,
      waterfall: backlog.waterfall,
      buildableLeaves: backlog.buildableLeaves,
    },
    nextUp: backlog.nextUp,
    builtUnflipped: backlog.builtUnflipped,
    coverage: coverageStats(acs),
    traceability: computeTraceability(acs, tickets),
    activity: computeActivity(tickets),
  };
}

/**
 * "What's next" = the TRUE /build-ac queue: eligible LEAF ACs (active, todo,
 * approved, and UNBLOCKED — every dependency done), ranked exactly as the real
 * scanner + ac_prioritizer do (complexity-derived priority, then file path).
 * This is far smaller than "all approved not-done" because most such ACs are
 * blocked by dependencies or are composite parents. Delegates to computeNextUp.
 */
export function nextAcs(acs: AC[], limit = 25): AC[] {
  return computeNextUp(acs, limit);
}
