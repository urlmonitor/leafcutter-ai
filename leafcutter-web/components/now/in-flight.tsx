"use client";

import * as React from "react";
import { motion } from "framer-motion";
import {
  CheckCircle2,
  Circle,
  XCircle,
  FileCode2,
  Layers,
  Radio,
  Info,
} from "lucide-react";
import type { AgentDef } from "@/lib/data/types";
import { agentLabel, phaseRank, phaseTone, PHASE_STATUS_TONE } from "@/components/pipeline/shared";
import { EmptyState, Legend } from "@/components/ui/kit";
import { cn } from "@/lib/utils";
import type { EpicLite, FlightItem, PhaseLite } from "./types";

const STATUS_ICON: Record<string, React.ComponentType<{ className?: string }>> = {
  signed_off: CheckCircle2,
  needed: Circle,
  failed: XCircle,
};

function orderPhases(phases: PhaseLite[]): PhaseLite[] {
  return [...phases].sort((a, b) => phaseRank(a.name) - phaseRank(b.name));
}

/** A compact horizontal chain of phase pills for one ticket. */
function PhaseStrip({ phases, agents }: { phases: PhaseLite[]; agents: AgentDef[] }) {
  if (phases.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-border/60 px-3 py-2 text-[11px] text-muted-foreground">
        No phase-chain data on this ticket — it is flagged in progress without a live agent map.
      </div>
    );
  }
  const ordered = orderPhases(phases);
  return (
    <div className="relative overflow-x-auto pb-1">
      <div className="flex min-w-max flex-wrap items-center gap-1.5">
        {ordered.map((p, i) => {
          const tone = phaseTone(p.status);
          const Icon = STATUS_ICON[p.status] ?? Circle;
          return (
            <motion.span
              key={p.name}
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.25, delay: i * 0.03 }}
              className="inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-medium"
              style={{
                borderColor: `hsl(${tone.hsl} / 0.4)`,
                background: `hsl(${tone.hsl} / 0.1)`,
                color: `hsl(${tone.hsl})`,
              }}
            >
              <Icon className={cn("h-3 w-3", p.status === "needed" && "animate-pulse")} />
              {agentLabel(agents, p.name)}
            </motion.span>
          );
        })}
      </div>
    </div>
  );
}

function FlightCard({
  item,
  agents,
  index,
}: {
  item: FlightItem;
  agents: AgentDef[];
  index: number;
}) {
  const done = item.phases.filter((p) => p.status === "signed_off").length;
  const active = item.phases.filter((p) => p.status === "needed").length;
  const failed = item.phases.filter((p) => p.status === "failed").length;

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, delay: index * 0.06, ease: [0.22, 1, 0.36, 1] }}
      className={cn(
        "panel panel-hover p-5",
        failed > 0 && "border-destructive/40",
      )}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <h3 className="text-balance text-base font-semibold leading-snug tracking-tight text-foreground">
            {item.title}
          </h3>
          <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-muted-foreground">
            <span className="font-mono text-muted-foreground/80">{item.slug}</span>
            {item.epic && (
              <span className="rounded-full border border-border/70 bg-secondary/40 px-2 py-0.5 font-mono text-muted-foreground">
                {item.epic}
              </span>
            )}
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-2 text-[11px] tabular-nums">
          {failed > 0 && (
            <span className="inline-flex items-center gap-1 text-destructive">
              <XCircle className="h-3 w-3" /> {failed}
            </span>
          )}
          {active > 0 && (
            <span className="inline-flex items-center gap-1 text-warning">
              <Circle className="h-3 w-3" /> {active}
            </span>
          )}
          <span className="inline-flex items-center gap-1 text-success">
            <CheckCircle2 className="h-3 w-3" /> {done}
          </span>
        </div>
      </div>

      <div className="mt-4">
        <PhaseStrip phases={item.phases} agents={agents} />
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-border/60 pt-3 text-[11px] text-muted-foreground">
        <span className="inline-flex items-center gap-1.5">
          <FileCode2 className="h-3.5 w-3.5 text-muted-foreground/70" />
          {item.filesTouched} file{item.filesTouched === 1 ? "" : "s"} touched
        </span>
        {item.sourceAcs.length > 0 ? (
          <span className="inline-flex flex-wrap items-center gap-1.5">
            <Layers className="h-3.5 w-3.5 text-muted-foreground/70" />
            {item.sourceAcs.slice(0, 6).map((ac) => (
              <span
                key={ac}
                className="rounded-md border border-border/70 bg-muted/40 px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground"
              >
                {ac}
              </span>
            ))}
            {item.sourceAcs.length > 6 && (
              <span className="text-muted-foreground/70">+{item.sourceAcs.length - 6}</span>
            )}
          </span>
        ) : (
          <span className="text-muted-foreground/60">No AC traceability recorded</span>
        )}
      </div>
    </motion.div>
  );
}

export function InFlight({
  items,
  epics,
  agents,
  telemetryAvailable,
}: {
  items: FlightItem[];
  epics: EpicLite[];
  agents: AgentDef[];
  telemetryAvailable: boolean;
}) {
  return (
    <div className="space-y-5">
      {/* Honest provenance note */}
      <div className="flex items-start gap-2.5 rounded-lg border border-border/70 bg-secondary/30 px-3.5 py-2.5 text-xs text-muted-foreground">
        <Info className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground/70" />
        <p>
          {telemetryAvailable ? (
            <>An agent-telemetry log is present — this reflects live drive events.</>
          ) : (
            <>
              No live agent-telemetry log is present — this reflects{" "}
              <span className="font-medium text-foreground">static ticket state</span>, refreshed on
              every request. It is the honest answer to &ldquo;what are the agents working on&rdquo;:
              the tickets flagged <span className="font-medium">in&nbsp;progress</span> and the phase
              agents their frontmatter still marks as needed.
            </>
          )}
        </p>
      </div>

      {items.length > 0 ? (
        <div className="grid gap-4 lg:grid-cols-2">
          {items.map((item, i) => (
            <FlightCard key={item.slug} item={item} agents={agents} index={i} />
          ))}
        </div>
      ) : (
        <EmptyState
          icon={<Radio className="h-8 w-8" />}
          title="No leaf tickets are mid-build right now"
          hint="Nothing in the ticket store is flagged in progress with a live phase chain. Work is either queued (see below) or already merged."
        />
      )}

      {items.length > 0 && (
        <Legend
          className="px-1"
          items={[
            PHASE_STATUS_TONE.signed_off,
            PHASE_STATUS_TONE.needed,
            PHASE_STATUS_TONE.failed,
          ].map((t) => ({ label: t.label, hsl: t.hsl }))}
        />
      )}

      {/* Epic-level markers — coarse, possibly stale */}
      {epics.length > 0 && (
        <div className="rounded-xl border border-border/70 bg-card/40 p-4">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <div className="eyebrow">Epic-level — may be stale</div>
            <span className="text-[11px] text-muted-foreground">
              {epics.length} epic Master_Plan marker{epics.length === 1 ? "" : "s"} still flagged in
              progress
            </span>
          </div>
          <div className="flex flex-wrap gap-2">
            {epics.map((e) => (
              <span
                key={e.slug}
                className="inline-flex items-center gap-1.5 rounded-full border border-border/70 bg-secondary/40 px-2.5 py-1 text-[11px] text-muted-foreground"
                title={e.title}
              >
                <span className="h-1.5 w-1.5 rounded-full bg-warning/70" />
                <span className="font-mono">{e.epic ?? e.slug}</span>
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
