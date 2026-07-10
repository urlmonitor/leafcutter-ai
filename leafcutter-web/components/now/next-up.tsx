"use client";

import * as React from "react";
import { motion } from "framer-motion";
import { Play, ArrowRight, Sprout } from "lucide-react";
import { EmptyState } from "@/components/ui/kit";
import { colorForKey } from "@/lib/status";
import { humanize } from "@/lib/utils";
import type { NextItem } from "./types";

const CX_LABEL: Record<string, string> = { S: "Small", M: "Medium", L: "Large", XL: "X-Large" };

function ComplexityChip({ cx }: { cx: string }) {
  return (
    <span className="rounded-md border border-border bg-muted/40 px-1.5 py-0.5 text-[11px] font-medium tabular-nums text-muted-foreground">
      {cx === "unknown" ? "—" : `${cx} · ${CX_LABEL[cx] ?? cx}`}
    </span>
  );
}

function ComponentDot({ component }: { component: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span
        className="h-1.5 w-1.5 rounded-full"
        style={{ background: `hsl(${colorForKey(component)})` }}
      />
      {humanize(component)}
    </span>
  );
}

function Hero({ ac }: { ac: NextItem }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
      className="relative overflow-hidden rounded-xl border border-primary/30 bg-primary/[0.06] p-6"
    >
      <div className="veins pointer-events-none absolute inset-0 opacity-40" />
      <div className="relative">
        <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-primary/40 bg-primary/10 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-primary">
          <Play className="h-3 w-3 fill-current" />
          Next up
        </div>
        <div className="flex items-baseline gap-2.5">
          <span className="font-mono text-sm text-primary/90">{ac.id}</span>
        </div>
        <h3 className="mt-1 text-balance text-xl font-semibold leading-tight tracking-tight text-foreground sm:text-2xl">
          {ac.title}
        </h3>
        <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-muted-foreground">
          <ComponentDot component={ac.component} />
          <ComplexityChip cx={ac.complexity} />
        </div>
        <p className="mt-4 max-w-2xl text-sm text-muted-foreground">
          <span className="font-medium text-foreground">Why this one:</span> the{" "}
          <span className="font-mono text-primary/90">/build-ac</span> scanner picks eligible,
          unblocked, approved leaf ACs and ranks them by complexity — this is the exact record it
          would generate the next ticket for.
        </p>
      </div>
    </motion.div>
  );
}

function QueueRow({ ac, rank }: { ac: NextItem; rank: number }) {
  return (
    <li className="group grid grid-cols-[1.75rem_1fr] items-center gap-3 rounded-lg border border-border/60 bg-card/40 px-3 py-2.5 transition-colors hover:border-primary/30 hover:bg-card/80 sm:grid-cols-[2rem_1fr_auto] sm:gap-4 sm:px-4">
      <div className="text-center text-sm font-semibold tabular-nums text-muted-foreground/60 group-hover:text-primary">
        {rank}
      </div>
      <div className="min-w-0">
        <div className="truncate text-sm font-medium text-foreground">{ac.title}</div>
        <div className="mt-1 flex flex-wrap items-center gap-x-2.5 gap-y-1 text-[11px] text-muted-foreground">
          <span className="font-mono text-muted-foreground/80">{ac.id}</span>
          <ComponentDot component={ac.component} />
          <span className="sm:hidden">
            <ComplexityChip cx={ac.complexity} />
          </span>
        </div>
      </div>
      <div className="hidden sm:flex sm:items-center">
        <ComplexityChip cx={ac.complexity} />
      </div>
    </li>
  );
}

export function NextUp({
  queue,
  readyCount,
}: {
  queue: NextItem[];
  readyCount: number;
}) {
  if (queue.length === 0) {
    return (
      <EmptyState
        icon={<Sprout className="h-8 w-8" />}
        title="Nothing is eligible for the next ticket"
        hint="An AC only becomes auto-pickable once it is an approved, unblocked leaf. Promote reviewed ACs to approved, or clear a dependency, to fill the queue."
      />
    );
  }

  const [first, ...rest] = queue;

  return (
    <div className="space-y-5">
      <Hero ac={first} />

      {rest.length > 0 && (
        <div>
          <div className="mb-2 flex items-center gap-2 px-1 text-[11px] text-muted-foreground">
            <ArrowRight className="h-3.5 w-3.5" />
            Then, in order:
          </div>
          <ol className="space-y-2">
            {rest.map((ac, i) => (
              <QueueRow key={ac.id} ac={ac} rank={i + 2} />
            ))}
          </ol>
        </div>
      )}

      <div className="rounded-lg border border-border/70 bg-secondary/30 px-3.5 py-2.5 text-xs text-muted-foreground">
        These <span className="font-medium text-foreground">{queue.length}</span> are exactly what{" "}
        <span className="font-mono text-primary/90">/build-ac</span> would cut a ticket from next —
        approved <em>and</em> auto-pickable. That is a subset of the{" "}
        <span className="font-medium text-foreground">{readyCount}</span> triaged, unblocked{" "}
        <span className="font-medium">ready</span> leaves in the backlog: the rest are unblocked but
        not yet promoted to <span className="font-medium">approved</span>.
      </div>
    </div>
  );
}
