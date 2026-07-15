"use client";

import * as React from "react";
import { motion } from "framer-motion";
import { CheckCircle2, Circle, XCircle, MinusCircle, ChevronRight } from "lucide-react";
import type { AgentDef, Ticket } from "@/lib/data/types";
import {
  PHASE_STATUS_TONE,
  phaseTone,
  phaseRank,
  isActivePhase,
  agentLabel,
} from "./shared";
import { cn } from "@/lib/utils";
import { Legend } from "@/components/ui/kit";

/** Minimal shape the visualizer needs (a serializable ticket slice). */
export type ChainTicket = Pick<Ticket, "slug" | "title" | "epic" | "agents">;

const STATUS_ICON: Record<string, React.ComponentType<{ className?: string }>> = {
  signed_off: CheckCircle2,
  needed: Circle,
  failed: XCircle,
  skip: MinusCircle,
  not_needed: MinusCircle,
};

function PhaseNode({
  name,
  status,
  agents,
  index,
}: {
  name: string;
  status: string;
  agents: AgentDef[];
  index: number;
}) {
  const tone = phaseTone(status);
  const Icon = STATUS_ICON[status] ?? Circle;
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.3, delay: index * 0.04 }}
      className="flex shrink-0 flex-col items-center gap-2"
      style={{ width: 108 }}
    >
      <div
        className="flex h-11 w-11 items-center justify-center rounded-full border"
        style={{
          borderColor: `hsl(${tone.hsl} / 0.5)`,
          background: `hsl(${tone.hsl} / 0.12)`,
          color: `hsl(${tone.hsl})`,
        }}
      >
        <Icon className="h-5 w-5" />
      </div>
      <div className="text-center">
        <div className="text-[11px] font-medium leading-tight text-foreground">
          {agentLabel(agents, name)}
        </div>
        <div className={cn("mt-0.5 text-[10px]", tone.text)}>{tone.label}</div>
      </div>
    </motion.div>
  );
}

export function PhaseChain({
  tickets,
  agents,
}: {
  tickets: ChainTicket[];
  agents: AgentDef[];
}) {
  const [slug, setSlug] = React.useState(tickets[0]?.slug ?? "");
  const [showSkipped, setShowSkipped] = React.useState(false);

  const ticket = tickets.find((t) => t.slug === slug) ?? tickets[0];

  const ordered = React.useMemo(() => {
    if (!ticket) return [];
    return [...ticket.agents].sort((a, b) => phaseRank(a.name) - phaseRank(b.name));
  }, [ticket]);

  const active = ordered.filter((a) => isActivePhase(a.status));
  const shown = showSkipped ? ordered : active;
  const skippedCount = ordered.length - active.length;

  if (!ticket) return null;

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <label className="relative">
          <select
            value={slug}
            onChange={(e) => setSlug(e.target.value)}
            className="max-w-[22rem] appearance-none truncate rounded-lg border border-border bg-secondary/50 py-2 pl-3 pr-9 text-sm text-foreground outline-none transition-colors hover:border-primary/40 focus:border-primary/60"
          >
            {tickets.map((t) => (
              <option key={t.slug} value={t.slug}>
                {t.title.length > 54 ? t.title.slice(0, 54) + "…" : t.title}
              </option>
            ))}
          </select>
          <ChevronRight className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 rotate-90 text-muted-foreground" />
        </label>

        {ticket.epic && (
          <span className="rounded-full border border-border/70 bg-secondary/40 px-2.5 py-0.5 font-mono text-[11px] text-muted-foreground">
            {ticket.epic}
          </span>
        )}

        <button
          type="button"
          onClick={() => setShowSkipped((v) => !v)}
          className="ml-auto rounded-lg border border-border/70 px-2.5 py-1 text-xs text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground"
        >
          {showSkipped ? "Hide" : "Show"} {skippedCount} not-needed
        </button>
      </div>

      {/* horizontal scrollable timeline with connecting rail */}
      <div className="relative overflow-x-auto pb-3">
        <div className="relative flex min-w-max items-start gap-0 px-1 pt-1">
          {/* rail behind the nodes */}
          <div
            className="absolute left-6 right-6 top-[22px] h-px"
            style={{
              background:
                "linear-gradient(to right, hsl(var(--border)), hsl(var(--primary) / 0.4), hsl(var(--border)))",
            }}
          />
          {shown.map((a, i) => (
            <React.Fragment key={a.name}>
              <div className="relative z-10">
                <PhaseNode name={a.name} status={a.status} agents={agents} index={i} />
              </div>
            </React.Fragment>
          ))}
        </div>
      </div>

      <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
        <Legend
          items={Object.values(PHASE_STATUS_TONE).map((t) => ({ label: t.label, hsl: t.hsl }))}
        />
        <div className="text-xs text-muted-foreground">
          <span className="font-medium text-foreground">{active.length}</span> phases engaged of{" "}
          {ordered.length} available
        </div>
      </div>
    </div>
  );
}
