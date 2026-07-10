import * as React from "react";
import { ListChecks, Layers, GitBranch } from "lucide-react";
import { getAtlas, nextAcs } from "@/lib/data/atlas";
import { PRIORITY_TONE } from "@/lib/status";
import { fmt } from "@/lib/utils";
import { Badge, PageHeader, Panel, SectionHeader } from "@/components/ui/kit";
import { PhaseJourney } from "@/components/roadmap/phase-journey";
import { WhatsNextQueue } from "@/components/roadmap/whats-next-queue";
import {
  BacklogComposition,
  type CompositionDatum,
} from "@/components/roadmap/backlog-composition";
import { PhaseTickets, type PhaseTicketGroup } from "@/components/roadmap/phase-tickets";
import type { BacklogBucket, Priority, Ticket } from "@/lib/data/types";

const PRIO_RANK: Record<string, number> = {
  critical: 0,
  high: 1,
  medium: 2,
  low: 3,
  unknown: 4,
};

const PRIORITY_ORDER: Priority[] = ["critical", "high", "medium", "low", "unknown"];

/**
 * Honest backlog buckets, ordered from "buildable now" to "dead", with the
 * colors + one-line reason we surface. "done" is intentionally excluded — this
 * chart explains why the NOT-done pile is mostly un-buildable.
 */
const BUCKET_META: { bucket: BacklogBucket; label: string; hsl: string; desc: string }[] = [
  { bucket: "ready", label: "Ready", hsl: "150 64% 52%", desc: "triaged, unblocked, todo — buildable now" },
  { bucket: "blocked", label: "Blocked", hsl: "356 72% 56%", desc: "triaged, but a dependency is unfinished" },
  { bucket: "composite", label: "Composite", hsl: "265 60% 66%", desc: "parent roll-up — completion derives from children" },
  { bucket: "built_unflipped", label: "Built · unflipped", hsl: "205 78% 60%", desc: "implemented, but status not flipped to done" },
  { bucket: "untriaged", label: "Untriaged", hsl: "38 92% 58%", desc: "readiness missing — needs triage" },
  { bucket: "draft", label: "Draft", hsl: "168 60% 46%", desc: "readiness draft — not real backlog yet" },
  { bucket: "superseded", label: "Superseded", hsl: "150 8% 45%", desc: "status not active — dead" },
];

function isTicketDone(t: Ticket): boolean {
  return t.status === "done" || t.lifecycle === "done";
}

export default function RoadmapPage() {
  const { roadmap, acs, tickets, backlog } = getAtlas();

  // --- The TRUE /build-ac queue: approved, unblocked leaf ACs, ranked. ---
  const queue = nextAcs(acs, 25);

  const byBucket = backlog.byBucket;
  const ready = byBucket.ready ?? 0;
  const blocked = byBucket.blocked ?? 0;

  // --- Backlog reality: honest bucket classification (not-done ACs). ---
  const bucketData: CompositionDatum[] = BUCKET_META.map((m) => ({
    label: m.label,
    value: byBucket[m.bucket] ?? 0,
    hsl: m.hsl,
    desc: m.desc,
  })).filter((d) => d.value > 0);

  // --- Open ACs by priority (context, not "buildable"). ---
  const notDone = acs.filter(
    (a) => a.status !== "deprecated" && a.workStatus !== "done",
  );
  const priorityData: CompositionDatum[] = PRIORITY_ORDER.map((p) => ({
    label: PRIORITY_TONE[p].label,
    value: notDone.filter((a) => a.priority === p).length,
    hsl: PRIORITY_TONE[p].hsl,
  })).filter((d) => d.value > 0);

  // --- Phase-aligned tickets ---
  const groups: PhaseTicketGroup[] = roadmap.phases.map((p) => {
    const ts = tickets.filter((t) => t.roadmapPhase === p.id);
    const done = ts.filter(isTicketDone).length;
    const open = ts.filter((t) => !isTicketDone(t));
    const advancing = ts.filter((t) => t.advancesOutcome).length;
    const samples = open
      .filter((t) => t.advancesOutcome)
      .sort((a, b) => PRIO_RANK[a.priority] - PRIO_RANK[b.priority])
      .slice(0, 5);
    return {
      id: p.id,
      title: p.title,
      status: p.status,
      total: ts.length,
      done,
      open: open.length,
      advancing,
      samples,
    };
  });

  const journeyStats: Record<string, { total: number; open: number; advancing: number }> =
    Object.fromEntries(
      groups.map((g) => [g.id, { total: g.total, open: g.open, advancing: g.advancing }]),
    );

  const activePhase = roadmap.phases.find((p) => p.id === roadmap.currentPhase);

  return (
    <div className="animate-fade-in space-y-12">
      <PageHeader
        eyebrow="Roadmap / What's next"
        title="Where the project is headed"
        description="The delivery plan, its exit criteria, and the acceptance criteria the system would actually build next — read live from the repo."
      >
        {activePhase && (
          <div className="flex flex-col items-end gap-1.5">
            <Badge tone={PRIORITY_TONE.high} className="!border-primary/40 !bg-primary/10 !text-primary" dot>
              {activePhase.title}
            </Badge>
            <span className="eyebrow">Active phase</span>
          </div>
        )}
      </PageHeader>

      {/* 1 + 2 — Phase journey with expandable exit criteria */}
      <PhaseJourney
        phases={roadmap.phases}
        currentOutcome={roadmap.currentOutcome}
        stats={journeyStats}
      />

      {/* 3 — The true /build-ac queue */}
      <section>
        <SectionHeader
          eyebrow="What's next"
          title="The /build-ac queue"
          description={
            queue.length > 0
              ? `The ACs the system would build next: ${fmt(queue.length)} approved, unblocked leaf criteria — the auto-picked subset of ${fmt(ready)} triaged-and-ready leaves — ranked exactly as the scanner selects them.`
              : "Nothing is buildable right now: every approved leaf AC is either blocked by an unfinished dependency or already built."
          }
          action={
            <Badge className="!border-primary/40 !bg-primary/10 !text-primary" dot={false}>
              <ListChecks className="h-3 w-3" />
              {fmt(queue.length)} auto-picked next
            </Badge>
          }
        />
        <Panel className="p-4 sm:p-5">
          <WhatsNextQueue queue={queue} readyCount={ready} blockedCount={blocked} />
        </Panel>
      </section>

      {/* 4 — Backlog reality (honest bucket classification) */}
      <section>
        <SectionHeader
          eyebrow="Backlog reality"
          title="Why the queue is small"
          description="Not-done acceptance criteria classified by why they are — or are not — buildable. Only Ready leaves can enter the queue; most of the pile is composite parents, blocked leaves, or already-built work awaiting a status flip."
          action={
            <span className="hidden items-center gap-1.5 text-xs text-muted-foreground sm:inline-flex">
              <Layers className="h-3.5 w-3.5" />
              {fmt(notDone.length)} open ACs
            </span>
          }
        />
        <Panel>
          <BacklogComposition
            bucketData={bucketData}
            priorityData={priorityData}
            buildableLeaves={backlog.buildableLeaves}
            readyCount={ready}
          />
        </Panel>
      </section>

      {/* 5 — Phase-aligned tickets */}
      <section>
        <SectionHeader
          eyebrow="Delivery"
          title="Tickets by phase"
          description="How work in the ticket store maps onto the roadmap, and how much of it is flagged as advancing the current outcome."
          action={
            <span className="hidden items-center gap-1.5 text-xs text-muted-foreground sm:inline-flex">
              <GitBranch className="h-3.5 w-3.5" />
              {fmt(tickets.length)} tickets
            </span>
          }
        />
        <PhaseTickets groups={groups} />
      </section>
    </div>
  );
}
