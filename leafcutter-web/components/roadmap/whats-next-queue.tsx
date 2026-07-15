import * as React from "react";
import Link from "next/link";
import { Sprout, ArrowUpRight } from "lucide-react";
import { Badge, EmptyState } from "@/components/ui/kit";
import { PRIORITY_TONE, LEVEL_TONE, colorForKey } from "@/lib/status";
import { humanize } from "@/lib/utils";
import type { AC } from "@/lib/data/types";

function AcRow({ ac, rank }: { ac: AC; rank: number }) {
  const prio = PRIORITY_TONE[ac.priority];
  const lvl = LEVEL_TONE[ac.level];
  return (
    <li className="group grid grid-cols-[1.75rem_1fr] items-center gap-3 rounded-lg border border-border/60 bg-card/40 px-3 py-2.5 transition-colors hover:border-primary/30 hover:bg-card/80 sm:grid-cols-[2.25rem_1fr_auto] sm:gap-4 sm:px-4">
      <div className="text-center text-sm font-semibold tabular-nums text-muted-foreground/60 group-hover:text-primary">
        {rank}
      </div>

      <div className="min-w-0">
        <div className="truncate text-sm font-medium text-foreground">{ac.title}</div>
        <div className="mt-1 flex flex-wrap items-center gap-x-2.5 gap-y-1 text-[11px] text-muted-foreground">
          <span className="font-mono text-muted-foreground/80">{ac.id}</span>
          <span className="inline-flex items-center gap-1.5">
            <span
              className="h-1.5 w-1.5 rounded-full"
              style={{ background: `hsl(${colorForKey(ac.component)})` }}
            />
            {humanize(ac.component)}
          </span>
          {/* compact badges surface on mobile where the trailing column is hidden */}
          <span className="inline-flex items-center gap-1.5 sm:hidden">
            <Badge tone={prio} dot>
              {prio.label}
            </Badge>
            <Badge tone={lvl}>{ac.level}</Badge>
          </span>
        </div>
      </div>

      <div className="hidden items-center gap-2 sm:flex">
        <Badge tone={prio} dot>
          {prio.label}
        </Badge>
        <Badge tone={lvl}>{ac.level}</Badge>
        <span className="rounded-md border border-border bg-muted/40 px-1.5 py-0.5 text-[11px] font-medium tabular-nums text-muted-foreground">
          {ac.complexity === "unknown" ? "—" : ac.complexity}
        </span>
        <span
          className="hidden max-w-[9rem] truncate font-mono text-[11px] text-muted-foreground/80 xl:inline"
          title={ac.assignedAgent ?? undefined}
        >
          {ac.assignedAgent ?? "—"}
        </span>
      </div>
    </li>
  );
}

function ColumnHeader() {
  return (
    <div className="hidden grid-cols-[2.25rem_1fr_auto] gap-4 px-4 pb-1 sm:grid">
      <div className="eyebrow text-center">#</div>
      <div className="eyebrow">Acceptance criterion</div>
      <div className="eyebrow flex items-center gap-2">
        <span className="w-[68px]">Priority</span>
        <span className="w-[86px]">Level</span>
        <span>Cx</span>
        <span className="hidden xl:inline">Agent</span>
      </div>
    </div>
  );
}

export function WhatsNextQueue({
  queue,
  readyCount,
  blockedCount,
}: {
  queue: AC[];
  readyCount: number;
  blockedCount: number;
}) {
  if (queue.length > 0) {
    return (
      <div>
        <ColumnHeader />
        <ol className="space-y-2">
          {queue.map((ac, i) => (
            <AcRow key={ac.id} ac={ac} rank={i + 1} />
          ))}
        </ol>
        <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-xs text-muted-foreground">
          <span className="inline-flex items-center gap-1.5">
            <span className="h-1.5 w-1.5 rounded-full bg-primary" />
            {readyCount.toLocaleString("en-US")} ready leaves total
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="h-1.5 w-1.5 rounded-full bg-destructive" />
            {blockedCount.toLocaleString("en-US")} blocked by dependencies
          </span>
          <Link
            href="/now"
            className="inline-flex items-center gap-1 text-primary/90 transition-colors hover:text-primary"
          >
            Full backlog breakdown on Now &amp; Next
            <ArrowUpRight className="h-3 w-3" />
          </Link>
        </div>
      </div>
    );
  }

  return (
    <EmptyState
      icon={<Sprout className="h-8 w-8" />}
      title="Nothing is buildable right now"
      hint="The /build-ac queue is the set of approved leaf ACs whose dependencies are all done. Right now every approved leaf is either blocked by an unfinished dependency or already built — see the full backlog breakdown on Now & Next."
    />
  );
}
