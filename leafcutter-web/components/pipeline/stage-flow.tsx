"use client";

import * as React from "react";
import { motion } from "framer-motion";
import { Sprout, ListChecks, Hammer, PackageCheck, ArrowRight } from "lucide-react";
import type { AgentDef } from "@/lib/data/types";
import { STAGES, agentLabel, type Stage } from "./shared";

const STAGE_ICON: Record<string, React.ComponentType<{ className?: string }>> = {
  plan: Sprout,
  select: ListChecks,
  build: Hammer,
  finalize: PackageCheck,
};

/** A connector with a chlorophyll pulse that travels along the flow direction. */
function Connector({ hslFrom, hslTo, vertical }: { hslFrom: string; hslTo: string; vertical?: boolean }) {
  if (vertical) {
    return (
      <div className="relative mx-auto my-1 h-8 w-px overflow-hidden">
        <div
          className="absolute inset-0"
          style={{ background: `linear-gradient(to bottom, hsl(${hslFrom} / 0.5), hsl(${hslTo} / 0.5))` }}
        />
        <motion.span
          className="absolute left-1/2 h-3 w-1 -translate-x-1/2 rounded-full"
          style={{ background: `hsl(${hslTo})`, boxShadow: `0 0 8px hsl(${hslTo})` }}
          initial={{ top: "-20%" }}
          animate={{ top: "120%" }}
          transition={{ duration: 1.8, repeat: Infinity, ease: "easeInOut" }}
        />
      </div>
    );
  }
  return (
    <div className="relative hidden h-px min-w-8 flex-1 items-center self-center overflow-visible lg:flex">
      <div
        className="h-px w-full"
        style={{ background: `linear-gradient(to right, hsl(${hslFrom} / 0.5), hsl(${hslTo} / 0.5))` }}
      />
      <motion.span
        className="absolute top-1/2 h-1 w-4 -translate-y-1/2 rounded-full"
        style={{ background: `hsl(${hslTo})`, boxShadow: `0 0 10px hsl(${hslTo})` }}
        initial={{ left: "-8%" }}
        animate={{ left: "108%" }}
        transition={{ duration: 1.8, repeat: Infinity, ease: "easeInOut" }}
      />
      <ArrowRight
        className="absolute -right-1 top-1/2 h-3 w-3 -translate-y-1/2"
        style={{ color: `hsl(${hslTo})` }}
      />
    </div>
  );
}

function StageCard({
  stage,
  agents,
  delay,
}: {
  stage: Stage;
  agents: AgentDef[];
  delay: number;
}) {
  const Icon = STAGE_ICON[stage.key] ?? Sprout;
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-40px" }}
      transition={{ duration: 0.45, delay }}
      className="group relative flex flex-1 flex-col overflow-hidden rounded-xl border border-border/80 bg-card/70 p-4 backdrop-blur-sm transition-colors hover:border-primary/30"
      style={{ minWidth: 0 }}
    >
      {/* accent glow */}
      <div
        className="pointer-events-none absolute -right-8 -top-10 h-28 w-28 rounded-full opacity-20 blur-2xl transition-opacity group-hover:opacity-40"
        style={{ background: `hsl(${stage.hsl})` }}
      />
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <span
            className="flex h-9 w-9 items-center justify-center rounded-lg border"
            style={{
              borderColor: `hsl(${stage.hsl} / 0.35)`,
              background: `hsl(${stage.hsl} / 0.12)`,
              color: `hsl(${stage.hsl})`,
            }}
          >
            <Icon className="h-5 w-5" />
          </span>
          <div>
            <div className="eyebrow" style={{ color: `hsl(${stage.hsl})` }}>
              Stage {stage.index}
            </div>
            <div className="text-base font-semibold tracking-tight text-foreground">{stage.title}</div>
          </div>
        </div>
        <span
          className="tabular-nums text-2xl font-bold opacity-25"
          style={{ color: `hsl(${stage.hsl})` }}
        >
          0{stage.index}
        </span>
      </div>

      <code
        className="mb-2 inline-flex w-fit items-center rounded-md border px-2 py-0.5 font-mono text-xs"
        style={{
          borderColor: `hsl(${stage.hsl} / 0.3)`,
          background: `hsl(${stage.hsl} / 0.08)`,
          color: `hsl(${stage.hsl})`,
        }}
      >
        {stage.command}
      </code>

      <p className="mb-1 text-xs font-medium text-foreground/90">{stage.tagline}</p>
      <p className="mb-3 text-xs leading-relaxed text-muted-foreground">{stage.purpose}</p>

      <div className="mt-auto">
        <div className="mb-1.5 flex flex-wrap gap-1">
          {stage.agents.map((sa) => (
            <span
              key={sa.id}
              title={sa.note}
              className="inline-flex items-center gap-1 rounded-full border border-border/70 bg-secondary/40 px-1.5 py-0.5 text-[10px] font-medium text-foreground/80"
            >
              <span className="h-1 w-1 rounded-full" style={{ background: `hsl(${stage.hsl})` }} />
              {agentLabel(agents, sa.id)}
            </span>
          ))}
        </div>
        <p
          className="mt-2 border-t border-border/50 pt-2 text-[11px] italic leading-snug"
          style={{ color: `hsl(${stage.hsl} / 0.9)` }}
        >
          {stage.output}
        </p>
      </div>
    </motion.div>
  );
}

export function StageFlow({ agents }: { agents: AgentDef[] }) {
  return (
    <div>
      {/* Desktop: horizontal flow with animated connectors */}
      <div className="flex flex-col gap-2 lg:flex-row lg:items-stretch">
        {STAGES.map((stage, i) => (
          <React.Fragment key={stage.key}>
            <StageCard stage={stage} agents={agents} delay={i * 0.08} />
            {i < STAGES.length - 1 && (
              <>
                <Connector
                  hslFrom={stage.hsl}
                  hslTo={STAGES[i + 1].hsl}
                />
                <div className="lg:hidden">
                  <Connector hslFrom={stage.hsl} hslTo={STAGES[i + 1].hsl} vertical />
                </div>
              </>
            )}
          </React.Fragment>
        ))}
      </div>
    </div>
  );
}
