import * as React from "react";
import { Ticket as TicketIcon, TrendingUp } from "lucide-react";
import { Meter } from "@/components/ui/kit";
import { PRIORITY_TONE } from "@/lib/status";
import { fmt, pct } from "@/lib/utils";
import type { Ticket } from "@/lib/data/types";

export type PhaseTicketGroup = {
  id: string;
  title: string;
  status: string;
  total: number;
  done: number;
  open: number;
  advancing: number;
  samples: Ticket[];
};

function statusAccent(status: string): string {
  if (status === "active") return "150 64% 52%";
  if (status === "done") return "150 40% 50%";
  return "150 8% 45%";
}

function GroupCard({ g }: { g: PhaseTicketGroup }) {
  const active = g.status === "active";
  const done = g.total ? pct(g.done, g.total) : 0;
  return (
    <div
      className={cardClass(active)}
    >
      <div className="mb-3 flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="eyebrow mb-1">{g.id}</div>
          <h3 className="truncate text-sm font-semibold tracking-tight text-foreground">
            {g.title}
          </h3>
        </div>
        <span
          className="mt-0.5 inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium tabular-nums"
          style={{
            color: `hsl(${statusAccent(g.status)})`,
            borderColor: `hsl(${statusAccent(g.status)} / 0.3)`,
            background: `hsl(${statusAccent(g.status)} / 0.1)`,
          }}
        >
          <TicketIcon className="h-3 w-3" />
          {fmt(g.total)}
        </span>
      </div>

      {g.total > 0 ? (
        <>
          <div className="mb-1.5 flex items-center justify-between text-[11px] text-muted-foreground">
            <span className="inline-flex items-center gap-1">
              <TrendingUp className="h-3 w-3 text-primary" />
              {fmt(g.advancing)} advancing
            </span>
            <span className="tabular-nums">
              {done}% done · {fmt(g.open)} open
            </span>
          </div>
          <Meter value={done} color={statusAccent(g.status)} />

          {g.samples.length > 0 && (
            <ul className="mt-4 space-y-1.5">
              {g.samples.map((t) => {
                const prio = PRIORITY_TONE[t.priority];
                return (
                  <li
                    key={t.filePath}
                    className="flex items-center gap-2 text-xs"
                  >
                    <span
                      className="h-1.5 w-1.5 shrink-0 rounded-full"
                      style={{ background: `hsl(${prio.hsl})` }}
                    />
                    <span className="truncate text-muted-foreground" title={t.title}>
                      {t.title}
                    </span>
                  </li>
                );
              })}
            </ul>
          )}
        </>
      ) : (
        <p className="text-xs text-muted-foreground/70">No tickets scheduled yet.</p>
      )}
    </div>
  );
}

function cardClass(active: boolean): string {
  return [
    "panel p-5",
    active ? "border-primary/30" : "",
  ]
    .filter(Boolean)
    .join(" ");
}

export function PhaseTickets({ groups }: { groups: PhaseTicketGroup[] }) {
  const anyTickets = groups.some((g) => g.total > 0);
  if (!anyTickets) {
    return (
      <p className="text-sm text-muted-foreground">
        No tickets are tagged with a roadmap phase yet.
      </p>
    );
  }
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {groups.map((g) => (
        <GroupCard key={g.id} g={g} />
      ))}
    </div>
  );
}
