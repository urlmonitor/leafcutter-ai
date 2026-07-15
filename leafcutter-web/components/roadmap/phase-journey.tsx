"use client";

import * as React from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  ChevronDown,
  Target,
  Ticket as TicketIcon,
  Sprout,
  CircleDot,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { fmt } from "@/lib/utils";
import { Badge } from "@/components/ui/kit";
import type { Tone } from "@/lib/status";
import type { RoadmapPhase } from "@/lib/data/types";

type PhaseStat = { total: number; open: number; advancing: number };

function phaseTone(status: string): Tone {
  switch (status) {
    case "done":
      return {
        label: "Done",
        hsl: "150 40% 50%",
        text: "text-success",
        bg: "bg-success/10",
        border: "border-success/30",
        dot: "bg-success",
      };
    case "active":
      return {
        label: "Active",
        hsl: "150 64% 52%",
        text: "text-primary",
        bg: "bg-primary/10",
        border: "border-primary/40",
        dot: "bg-primary",
      };
    default:
      return {
        label: "Planned",
        hsl: "150 8% 60%",
        text: "text-muted-foreground",
        bg: "bg-muted/40",
        border: "border-border",
        dot: "bg-muted-foreground",
      };
  }
}

/* ---------- Desktop rail (stepper markers + connectors) ---------- */
function Rail({ phases }: { phases: RoadmapPhase[] }) {
  return (
    <ol className="mb-6 hidden items-start lg:flex" aria-hidden>
      {phases.map((p, i) => {
        const tone = phaseTone(p.status);
        const active = p.status === "active";
        const done = p.status === "done";
        const last = i === phases.length - 1;
        return (
          <li key={p.id} className="flex flex-1 flex-col items-center">
            <div className="flex w-full items-center">
              <span
                className={cn(
                  "h-px flex-1",
                  i === 0 ? "opacity-0" : done ? "bg-success/40" : "bg-border",
                )}
              />
              <span
                className={cn(
                  "relative flex h-9 w-9 shrink-0 items-center justify-center rounded-full border text-sm font-semibold tabular-nums",
                  tone.text,
                  tone.bg,
                  tone.border,
                  active && "animate-pulse-ring",
                )}
                style={active ? { boxShadow: "0 0 0 0 hsl(var(--primary) / 0.5)" } : undefined}
              >
                {i + 1}
              </span>
              <span
                className={cn(
                  "h-px flex-1",
                  last ? "opacity-0" : "bg-border",
                )}
              />
            </div>
            <div className="mt-2 flex flex-col items-center gap-1 px-2 text-center">
              <span
                className={cn(
                  "text-xs font-medium",
                  active ? "text-foreground" : "text-muted-foreground",
                )}
              >
                {p.title}
              </span>
              <span className="eyebrow text-[10px]">{tone.label}</span>
            </div>
          </li>
        );
      })}
    </ol>
  );
}

/* ---------- Expandable phase card ---------- */
function PhaseCard({
  phase,
  step,
  stat,
  defaultOpen,
}: {
  phase: RoadmapPhase;
  step: number;
  stat?: PhaseStat;
  defaultOpen: boolean;
}) {
  const [open, setOpen] = React.useState(defaultOpen);
  const tone = phaseTone(phase.status);
  const active = phase.status === "active";

  return (
    <div
      className={cn(
        "panel flex flex-col p-0",
        active ? "border-primary/40 ring-1 ring-primary/20" : "opacity-95",
      )}
    >
      {active && (
        <div
          className="h-1 w-full rounded-t-xl"
          style={{
            background:
              "linear-gradient(90deg, hsl(var(--primary)/0.9), hsl(var(--accent)/0.5))",
          }}
        />
      )}
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-start gap-3 rounded-t-xl px-5 pt-5 text-left"
        aria-expanded={open}
      >
        <span
          className={cn(
            "mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border text-xs font-semibold tabular-nums lg:hidden",
            tone.text,
            tone.bg,
            tone.border,
          )}
        >
          {step}
        </span>
        <span className="min-w-0 flex-1">
          <span className="eyebrow mb-1 block">Phase {step}</span>
          <span className="flex items-center gap-2">
            <span className="truncate text-base font-semibold tracking-tight text-foreground">
              {phase.title}
            </span>
          </span>
          <span className="mt-2 flex flex-wrap items-center gap-2">
            <Badge tone={tone} dot>
              {tone.label}
            </Badge>
            {stat && stat.total > 0 && (
              <Badge>
                <TicketIcon className="h-3 w-3" />
                {fmt(stat.open)} open · {fmt(stat.total)} tickets
              </Badge>
            )}
          </span>
        </span>
        <ChevronDown
          className={cn(
            "mt-1 h-4 w-4 shrink-0 text-muted-foreground transition-transform duration-200",
            open && "rotate-180",
          )}
        />
      </button>

      <p className="px-5 pt-3 text-sm leading-relaxed text-muted-foreground">
        {phase.description}
      </p>

      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            key="content"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.28, ease: [0.4, 0, 0.2, 1] }}
            className="overflow-hidden"
          >
            <div className="px-5 pb-5 pt-4">
              <div className="mb-2 flex items-center gap-2 text-xs font-medium text-foreground">
                <Target className="h-3.5 w-3.5 text-primary" />
                Exit criteria
              </div>
              <ul className="space-y-2">
                {phase.exitCriteria.map((c, i) => (
                  <li key={i} className="flex items-start gap-2.5 text-sm text-muted-foreground">
                    <Sprout className="mt-0.5 h-3.5 w-3.5 shrink-0 text-accent" />
                    <span className="leading-snug">{c}</span>
                  </li>
                ))}
                {phase.exitCriteria.length === 0 && (
                  <li className="text-sm text-muted-foreground/70">
                    No exit criteria defined yet.
                  </li>
                )}
              </ul>

              {phase.ticketsAdvancingOutcome.length > 0 && (
                <div className="mt-4">
                  <div className="mb-2 flex items-center gap-2 text-xs font-medium text-foreground">
                    <CircleDot className="h-3.5 w-3.5 text-info" />
                    Tickets advancing the outcome
                  </div>
                  <ul className="space-y-1">
                    {phase.ticketsAdvancingOutcome.map((t) => (
                      <li key={t} className="truncate font-mono text-xs text-muted-foreground">
                        {t}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {stat && stat.advancing > 0 && (
                <p className="mt-4 text-xs text-muted-foreground/80">
                  <span className="font-medium text-foreground">{fmt(stat.advancing)}</span>{" "}
                  tickets in the store are flagged as advancing this outcome.
                </p>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export function PhaseJourney({
  phases,
  currentOutcome,
  stats,
}: {
  phases: RoadmapPhase[];
  currentOutcome: string;
  stats: Record<string, PhaseStat>;
}) {
  return (
    <section aria-label="Phase journey">
      {/* Outcome banner */}
      <div className="panel relative mb-8 overflow-hidden p-6">
        <div className="veins pointer-events-none absolute inset-0 opacity-[0.35]" />
        <div className="relative flex items-start gap-4">
          <span className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-primary/30 bg-primary/10">
            <Target className="h-5 w-5 text-primary" />
          </span>
          <div>
            <div className="eyebrow mb-1.5">Current outcome</div>
            <p className="max-w-3xl text-balance text-lg font-medium leading-snug text-foreground">
              {currentOutcome}
            </p>
          </div>
        </div>
      </div>

      <Rail phases={phases} />

      <div className="grid gap-4 lg:grid-cols-3">
        {phases.map((p, i) => (
          <PhaseCard
            key={p.id}
            phase={p}
            step={i + 1}
            stat={stats[p.id]}
            defaultOpen={p.status === "active"}
          />
        ))}
      </div>
    </section>
  );
}
