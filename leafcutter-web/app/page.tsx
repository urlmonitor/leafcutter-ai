import Link from "next/link";
import {
  ListChecks,
  CircleCheckBig,
  Ticket,
  PackageCheck,
  Boxes,
  Bot,
  ArrowUpRight,
  Sparkles,
  Leaf,
} from "lucide-react";
import { getAtlas, nextAcs } from "@/lib/data/atlas";
import {
  WORK_STATUS_TONE,
  LEVEL_TONE,
  PRIORITY_TONE,
  type Tone,
} from "@/lib/status";
import type { WorkStatus, AcLevel } from "@/lib/data/types";
import { cn, fmt, pct, humanize } from "@/lib/utils";
import {
  Panel,
  SectionHeader,
  Badge,
  StatCard,
  Legend,
  Meter,
  EmptyState,
  PageHeader,
} from "@/components/ui/kit";
import { Reveal } from "@/components/pulse/reveal";
import { StatusDonut } from "@/components/pulse/status-donut";
import { LevelsBar } from "@/components/pulse/levels-bar";
import { LifecycleBar } from "@/components/pulse/lifecycle-bar";
import type { ChartDatum } from "@/components/pulse/chart-primitives";

// Fixed, semantic orderings — color follows the entity, never its rank.
const STATUS_ORDER: WorkStatus[] = [
  "done",
  "in_progress",
  "todo",
  "not_started",
  "blocked",
  "unknown",
];
const LEVEL_ORDER: AcLevel[] = ["L0", "L1", "L2", "L3"];

const LIFECYCLE_META: { key: string; label: string; hsl: string }[] = [
  { key: "done", label: "Done", hsl: "150 60% 48%" },
  { key: "epic", label: "In epics", hsl: "265 60% 66%" },
  { key: "inbox", label: "Inbox", hsl: "205 78% 60%" },
  { key: "other", label: "Other", hsl: "150 8% 45%" },
];

function phaseTone(status: string): Tone {
  if (status === "done") return WORK_STATUS_TONE.done;
  if (status === "active") return WORK_STATUS_TONE.in_progress;
  return WORK_STATUS_TONE.unknown;
}

export default function PulseHome() {
  const atlas = getAtlas();
  const { acs, tickets, components, agents, roadmap, acCounts, ticketCounts } = atlas;

  const acDone = acCounts.byStatus.done ?? 0;
  const ticketsDone = ticketCounts.byLifecycle.done ?? 0;

  // ---- chart data (plain-serializable) ----
  const statusData: ChartDatum[] = STATUS_ORDER.map((s) => ({
    key: s,
    label: WORK_STATUS_TONE[s].label,
    value: acCounts.byStatus[s] ?? 0,
    hsl: WORK_STATUS_TONE[s].hsl,
  })).filter((d) => d.value > 0);

  const levelData: ChartDatum[] = LEVEL_ORDER.map((l) => ({
    key: l,
    label: l,
    value: acCounts.byLevel[l] ?? 0,
    hsl: LEVEL_TONE[l].hsl,
  }));

  const lifecycleData: ChartDatum[] = LIFECYCLE_META.map((m) => ({
    ...m,
    value: ticketCounts.byLifecycle[m.key] ?? 0,
  })).filter((d) => d.value > 0);

  const upcoming = nextAcs(acs, 6);

  const activePhase = roadmap.phases.find((p) => p.id === roadmap.currentPhase);
  const readTime = atlas.generatedAt.slice(0, 16).replace("T", " ") + " UTC";

  const stats = [
    {
      label: "Acceptance criteria",
      value: fmt(acCounts.total),
      sub: `${acCounts.byLevel.L2 ?? 0} behavioral (L2)`,
      icon: <ListChecks className="h-4 w-4" />,
      accent: "150 64% 52%",
    },
    {
      label: "ACs done",
      value: fmt(acDone),
      sub: `${pct(acDone, acCounts.total)}% of all criteria`,
      icon: <CircleCheckBig className="h-4 w-4" />,
      accent: "150 60% 48%",
    },
    {
      label: "Tickets",
      value: fmt(ticketCounts.total),
      sub: `${ticketCounts.byLifecycle.epic ?? 0} inside epics`,
      icon: <Ticket className="h-4 w-4" />,
      accent: "205 78% 60%",
    },
    {
      label: "Tickets done",
      value: fmt(ticketsDone),
      sub: `${pct(ticketsDone, ticketCounts.total)}% shipped`,
      icon: <PackageCheck className="h-4 w-4" />,
      accent: "168 60% 46%",
    },
    {
      label: "Components",
      value: fmt(components.length),
      sub: "architecture map",
      icon: <Boxes className="h-4 w-4" />,
      accent: "265 60% 66%",
    },
    {
      label: "Agents",
      value: fmt(agents.length),
      sub: "in the build pipeline",
      icon: <Bot className="h-4 w-4" />,
      accent: "38 92% 58%",
    },
  ];

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Pulse · mission control"
        title="Project pulse"
        description="A calm, live read of the whole Leafcutter project — acceptance criteria, delivery, and the road ahead."
      >
        <span className="inline-flex items-center gap-2 rounded-full border border-border/70 bg-card/60 px-3 py-1 text-[11px] text-muted-foreground">
          <span className="h-1.5 w-1.5 rounded-full bg-success animate-pulse" />
          Read {readTime}
        </span>
      </PageHeader>

      {/* ---- Hero strip ---- */}
      <Reveal>
        <div className="panel relative overflow-hidden p-8 sm:p-11">
          <div className="veins pointer-events-none absolute inset-0 opacity-60" />
          <div
            className="pointer-events-none absolute -right-24 -top-28 h-80 w-80 rounded-full blur-3xl"
            style={{ background: "hsl(150 64% 52% / 0.10)" }}
          />
          <div
            className="pointer-events-none absolute -bottom-32 -left-20 h-72 w-72 rounded-full blur-3xl"
            style={{ background: "hsl(168 60% 46% / 0.08)" }}
          />
          <div className="relative max-w-3xl">
            <div className="eyebrow mb-3 flex items-center gap-2">
              <Leaf className="h-3.5 w-3.5 text-primary" />
              {activePhase ? activePhase.title : humanize(roadmap.currentPhase)}
            </div>
            <h2 className="text-balance text-4xl font-semibold tracking-tight text-foreground sm:text-5xl">
              Leaf<span className="text-primary">cutter</span>
            </h2>
            <p className="text-balance mt-4 text-lg leading-relaxed text-muted-foreground">
              {roadmap.currentOutcome}
            </p>
            <div className="mt-6 flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-muted-foreground">
              <span className="inline-flex items-center gap-2">
                <span className="h-1.5 w-1.5 rounded-full bg-success animate-pulse" />
                Live — every figure is read from the repo on each request
              </span>
              <span className="hidden h-3 w-px bg-border sm:inline-block" />
              <span className="tabular-nums">
                {fmt(acCounts.total)} criteria · {fmt(ticketCounts.total)} tickets · {fmt(components.length)} components
              </span>
            </div>
          </div>
        </div>
      </Reveal>

      {/* ---- Stat cards ---- */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
        {stats.map((s, i) => (
          <Reveal key={s.label} delay={0.04 * i} className="h-full">
            <StatCard
              className="h-full"
              label={s.label}
              value={s.value}
              sub={s.sub}
              icon={s.icon}
              accent={s.accent}
            />
          </Reveal>
        ))}
      </div>

      {/* ---- AC status + levels ---- */}
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-5">
        <Reveal delay={0.05} className="lg:col-span-2">
          <Panel className="h-full">
            <SectionHeader
              eyebrow="Acceptance criteria"
              title="Work status"
              description="Where every criterion sits today."
            />
            <StatusDonut data={statusData} total={acCounts.total} />
            <Legend
              className="mt-5 justify-center"
              items={statusData.map((d) => ({ label: `${d.label} · ${fmt(d.value)}`, hsl: d.hsl }))}
            />
          </Panel>
        </Reveal>

        <Reveal delay={0.1} className="lg:col-span-3">
          <Panel className="h-full">
            <SectionHeader
              eyebrow="Acceptance criteria"
              title="The specification pyramid"
              description="From customer value (L0) down to edge cases (L3) — behaviors (L2) carry the weight."
            />
            <LevelsBar data={levelData} />
            <Legend
              className="mt-5"
              items={LEVEL_ORDER.map((l) => ({ label: LEVEL_TONE[l].label, hsl: LEVEL_TONE[l].hsl }))}
            />
          </Panel>
        </Reveal>
      </div>

      {/* ---- Delivery throughput + roadmap ---- */}
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <Reveal delay={0.05}>
          <Panel className="h-full">
            <SectionHeader
              eyebrow="Delivery"
              title="Throughput by lifecycle"
              description="Tickets grouped by where they live in the pipeline."
            />
            {lifecycleData.length ? (
              <LifecycleBar data={lifecycleData} />
            ) : (
              <EmptyState title="No tickets yet" hint="Nothing has been captured in the ticket store." />
            )}
          </Panel>
        </Reveal>

        <Reveal delay={0.1}>
          <Panel className="h-full">
            <SectionHeader
              eyebrow="Roadmap"
              title="Phase progress"
              description="The current phase and what follows."
            />
            <div className="space-y-4">
              {roadmap.phases.map((phase) => {
                const inPhase = tickets.filter((t) => t.roadmapPhase === phase.id);
                const doneInPhase = inPhase.filter((t) => t.lifecycle === "done").length;
                const hasTickets = inPhase.length > 0;
                const meterVal = hasTickets
                  ? pct(doneInPhase, inPhase.length)
                  : phase.status === "done"
                    ? 100
                    : phase.status === "active"
                      ? 8
                      : 0;
                const tone = phaseTone(phase.status);
                const isCurrent = phase.id === roadmap.currentPhase;
                return (
                  <div
                    key={phase.id}
                    className={cn(
                      "rounded-lg border p-4",
                      isCurrent ? "border-primary/30 bg-primary/[0.04]" : "border-border/70",
                    )}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div className="min-w-0">
                        <div className="truncate text-sm font-medium text-foreground">{phase.title}</div>
                        <div className="mt-0.5 text-[11px] text-muted-foreground">
                          {phase.exitCriteria.length} exit criteria
                          {hasTickets ? ` · ${doneInPhase}/${inPhase.length} tickets done` : ""}
                        </div>
                      </div>
                      <Badge tone={tone} dot>
                        {phase.status === "active" ? "Active" : humanize(phase.status)}
                      </Badge>
                    </div>
                    <Meter className="mt-3" value={meterVal} color={tone.hsl} />
                  </div>
                );
              })}
            </div>
          </Panel>
        </Reveal>
      </div>

      {/* ---- What's next ---- */}
      <Reveal delay={0.05}>
        <Panel>
          <SectionHeader
            eyebrow="What's next"
            title="Approved & ready to build"
            description="The highest-priority approved criteria not yet done — ranked like the build scanner."
            action={
              <Link
                href="/roadmap"
                className="inline-flex items-center gap-1 text-xs font-medium text-primary transition-colors hover:text-primary/80"
              >
                Open roadmap <ArrowUpRight className="h-3.5 w-3.5" />
              </Link>
            }
          />
          {upcoming.length ? (
            <ul className="divide-y divide-border/60">
              {upcoming.map((ac) => (
                <li key={ac.id}>
                  <Link
                    href="/roadmap"
                    className="group -mx-2 flex items-center gap-4 rounded-lg px-2 py-3 transition-colors hover:bg-secondary/50"
                  >
                    <span className="w-24 shrink-0 truncate font-mono text-xs text-muted-foreground">
                      {ac.id}
                    </span>
                    <span className="min-w-0 flex-1 truncate text-sm text-foreground">
                      {ac.title}
                    </span>
                    <span className="hidden shrink-0 text-[11px] text-muted-foreground sm:inline">
                      {humanize(ac.component)}
                    </span>
                    <Badge tone={PRIORITY_TONE[ac.priority]} dot>
                      {PRIORITY_TONE[ac.priority].label}
                    </Badge>
                    <ArrowUpRight className="h-4 w-4 shrink-0 text-muted-foreground/40 transition-colors group-hover:text-primary" />
                  </Link>
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState
              icon={<Sparkles className="h-6 w-6" />}
              title="Nothing approved & waiting"
              hint="Most criteria are still at readiness: reviewed — they need a final approval pass before they enter the build queue."
            />
          )}
        </Panel>
      </Reveal>
    </div>
  );
}
