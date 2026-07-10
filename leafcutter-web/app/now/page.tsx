import * as React from "react";
import { Activity, Play, Sprout, FileCheck2, Layers } from "lucide-react";
import { getAtlas } from "@/lib/data/atlas";
import { fmt } from "@/lib/utils";
import { Badge, PageHeader, Panel, SectionHeader, StatCard } from "@/components/ui/kit";
import { WORK_STATUS_TONE } from "@/lib/status";
import { InFlight } from "@/components/now/in-flight";
import { NextUp } from "@/components/now/next-up";
import { BacklogWaterfall } from "@/components/now/backlog-waterfall";
import { BuiltUnflipped } from "@/components/now/built-unflipped";
import type {
  BuiltItem,
  EpicLite,
  FlightItem,
  NextItem,
  PhaseLite,
  WaterfallRow,
} from "@/components/now/types";

export const dynamic = "force-dynamic";

export default function NowPage() {
  const { activity, nextUp, backlog, builtUnflipped, agents } = getAtlas();

  // --- Section 1: in-flight leaf tickets → lean flight items ---
  const flight: FlightItem[] = activity.inProgress.map((a) => {
    const phases: PhaseLite[] = [
      ...a.donePhases.map((n) => ({ name: n, status: "signed_off" as const })),
      ...a.activePhases.map((n) => ({ name: n, status: "needed" as const })),
      ...a.failedPhases.map((n) => ({ name: n, status: "failed" as const })),
    ];
    return {
      slug: a.ticket.slug,
      title: a.ticket.title,
      epic: a.ticket.epic,
      phases,
      filesTouched: a.ticket.filesTouched.length,
      sourceAcs: a.sourceAcs,
    };
  });

  const epics: EpicLite[] = activity.inFlightEpics.map((t) => ({
    slug: t.slug,
    title: t.title,
    epic: t.epic,
  }));

  // --- Section 2: the true /build-ac queue ---
  const queue: NextItem[] = nextUp.map((ac) => ({
    id: ac.id,
    title: ac.title,
    component: ac.component,
    complexity: ac.complexity,
  }));
  const readyCount = backlog.byBucket.ready;

  // --- Section 3: honest backlog waterfall ---
  const rows: WaterfallRow[] = backlog.waterfall.map((w) => ({
    bucket: w.bucket,
    label: w.label,
    count: w.count,
    description: w.description,
  }));

  // --- Section 4: built but not flipped ---
  const unflipped: BuiltItem[] = builtUnflipped.map((ac) => ({
    id: ac.id,
    title: ac.title,
    component: ac.component,
    implementedBy: ac.implementedBy,
  }));

  return (
    <div className="animate-fade-in space-y-14">
      <PageHeader
        eyebrow="Now & Next"
        title="The operational truth of the project"
        description="What the agents are building right now, what the system will build next, and an honest reckoning of the backlog — read live from the repo on every request."
      >
        <Badge tone={WORK_STATUS_TONE.in_progress} dot>
          {fmt(flight.length)} leaf ticket{flight.length === 1 ? "" : "s"} in flight
        </Badge>
      </PageHeader>

      {/* At-a-glance truth strip */}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="In flight (leaf)"
          value={fmt(flight.length)}
          sub="Tickets mid-build with a live phase chain"
          icon={<Activity className="h-4 w-4" />}
          accent="38 92% 58%"
        />
        <StatCard
          label="Next up"
          value={fmt(queue.length)}
          sub="Auto-pickable by /build-ac"
          icon={<Play className="h-4 w-4" />}
          accent="150 64% 52%"
        />
        <StatCard
          label="Genuinely ready"
          value={fmt(readyCount)}
          sub="Triaged, unblocked leaf ACs"
          icon={<Sprout className="h-4 w-4" />}
          accent="150 60% 48%"
        />
        <StatCard
          label="Built, not flipped"
          value={fmt(unflipped.length)}
          sub="Delivered but still flagged todo"
          icon={<FileCheck2 className="h-4 w-4" />}
          accent="38 92% 58%"
        />
      </div>

      {/* 1 — In flight now */}
      <section>
        <SectionHeader
          eyebrow="In flight now"
          title="What the agents are working on"
          description="Leaf tickets flagged in progress, each with its phase-agent chain — signed off, currently engaged, or failed — plus the files it touches and the ACs it traces to."
        />
        <InFlight
          items={flight}
          epics={epics}
          agents={agents}
          telemetryAvailable={activity.telemetryAvailable}
        />
      </section>

      {/* 2 — What the system builds next */}
      <section>
        <SectionHeader
          eyebrow="What the system builds next"
          title="The /build-ac queue"
          description="The exact acceptance criteria the scanner would cut the next tickets from — eligible, unblocked, approved leaves, ranked by complexity."
        />
        <Panel className="p-4 sm:p-6">
          <NextUp queue={queue} readyCount={readyCount} />
        </Panel>
      </section>

      {/* 3 — Backlog reality check */}
      <section>
        <SectionHeader
          eyebrow="Backlog reality check"
          title="From a scary raw number to what's actually buildable"
          description="Every not-done acceptance criterion, with each honest deduction peeled away — roll-up parents, superseded records, drafts, untriaged, and dependency-blocked leaves — down to the real ready-to-build backlog."
          action={
            <span className="hidden items-center gap-1.5 text-xs text-muted-foreground sm:inline-flex">
              <Layers className="h-3.5 w-3.5" />
              mutually-exclusive buckets
            </span>
          }
        />
        <Panel className="p-5 sm:p-7">
          <BacklogWaterfall rows={rows} nextUpCount={queue.length} />
        </Panel>
      </section>

      {/* 4 — Built but not marked done */}
      <section>
        <SectionHeader
          eyebrow="Built but not marked done"
          title="Do we actually switch AC status?"
          description="Leaf ACs that resolve to real delivered source or a done ticket, yet whose work_status was never flipped to done — the honest edge of the pipeline's best-effort mark-done step."
        />
        <BuiltUnflipped items={unflipped} />
      </section>
    </div>
  );
}
