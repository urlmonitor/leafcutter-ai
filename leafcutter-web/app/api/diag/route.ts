import { NextResponse } from "next/server";
import { getAtlas } from "@/lib/data/atlas";

// Diagnostic endpoint: sanity-check the phase-2 aggregates against the real store.
export async function GET() {
  const a = getAtlas();
  return NextResponse.json({
    acs: a.acs.length,
    backlogByBucket: a.backlog.byBucket,
    buildableLeaves: a.backlog.buildableLeaves,
    nextUpCount: a.nextUp.length,
    nextUpTop: a.nextUp.slice(0, 5).map((x) => ({ id: x.id, cx: x.complexity, comp: x.component })),
    builtUnflipped: a.builtUnflipped.length,
    builtUnflippedSample: a.builtUnflipped.slice(0, 8).map((x) => x.id),
    coverage: {
      guarded: a.coverage.guarded,
      guardedPct: a.coverage.guardedPct,
      rolledUpGuarded: a.coverage.rolledUpGuarded,
      histogram: a.coverage.histogram,
      byLevel: a.coverage.byLevel,
      totalTestFiles: a.coverage.totalTestFiles,
    },
    activity: {
      inProgress: a.activity.inProgress.length,
      inFlightEpics: a.activity.inFlightEpics.length,
      telemetryAvailable: a.activity.telemetryAvailable,
      sample: a.activity.inProgress.slice(0, 5).map((x) => ({
        slug: x.ticket.slug,
        active: x.activePhases,
        failed: x.failedPhases,
      })),
    },
  });
}
