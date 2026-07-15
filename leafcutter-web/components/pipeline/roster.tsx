"use client";

import * as React from "react";
import { Search, Cpu, Sparkles } from "lucide-react";
import type { AgentDef } from "@/lib/data/types";
import { CATEGORY_ORDER, CATEGORY_TONE, catKey } from "./shared";
import { cn } from "@/lib/utils";

const MODEL_LABEL: Record<string, string> = { opus: "Opus", sonnet: "Sonnet", haiku: "Haiku" };

function AgentRow({ agent }: { agent: AgentDef }) {
  const tone = CATEGORY_TONE[catKey(agent)];
  return (
    <div className="flex items-center gap-3 rounded-lg border border-border/60 bg-card/50 px-3 py-2 transition-colors hover:border-primary/30 hover:bg-card/80">
      <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: `hsl(${tone.hsl})` }} />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span
            className={cn(
              "truncate text-sm font-medium",
              agent.deprecated ? "text-muted-foreground line-through" : "text-foreground",
            )}
          >
            {agent.name}
          </span>
          {agent.isTicketPhase && (
            <Sparkles className="h-3 w-3 shrink-0 text-primary" aria-label="ticket phase" />
          )}
        </div>
        <div className="truncate font-mono text-[10px] text-muted-foreground">{agent.id}</div>
      </div>
      <span className="hidden w-24 shrink-0 truncate text-xs text-muted-foreground sm:block">
        {agent.role ?? "—"}
      </span>
      <span className="hidden w-16 shrink-0 text-[10px] uppercase tracking-wide text-muted-foreground md:block">
        {agent.tier ?? "—"}
      </span>
      <span
        className={cn(
          "inline-flex shrink-0 items-center gap-1 rounded-md border px-1.5 py-0.5 text-[10px] font-medium",
          agent.model === "opus"
            ? "border-chart-4/30 bg-chart-4/10 text-chart-4"
            : agent.model === "haiku"
              ? "border-chart-2/30 bg-chart-2/10 text-chart-2"
              : "border-border/70 bg-secondary/40 text-muted-foreground",
        )}
      >
        <Cpu className="h-2.5 w-2.5" />
        {MODEL_LABEL[agent.model ?? ""] ?? "—"}
      </span>
    </div>
  );
}

export function Roster({ agents }: { agents: AgentDef[] }) {
  const [query, setQuery] = React.useState("");
  const [cat, setCat] = React.useState<string | null>(null);

  const filtered = React.useMemo(() => {
    const q = query.trim().toLowerCase();
    return agents.filter((a) => {
      if (cat && catKey(a) !== cat) return false;
      if (!q) return true;
      return (
        a.name.toLowerCase().includes(q) ||
        a.id.toLowerCase().includes(q) ||
        (a.role ?? "").toLowerCase().includes(q) ||
        (a.description ?? "").toLowerCase().includes(q)
      );
    });
  }, [agents, query, cat]);

  const counts = React.useMemo(() => {
    const m: Record<string, number> = {};
    for (const a of agents) {
      const k = catKey(a);
      m[k] = (m[k] ?? 0) + 1;
    }
    return m;
  }, [agents]);

  const grouped = React.useMemo(() => {
    return CATEGORY_ORDER.map((c) => ({
      cat: c,
      items: filtered
        .filter((a) => catKey(a) === c)
        .sort((a, b) => a.name.localeCompare(b.name)),
    })).filter((g) => g.items.length > 0);
  }, [filtered]);

  return (
    <div>
      {/* controls */}
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search agents by name, id, role…"
            className="w-full rounded-lg border border-border bg-secondary/50 py-2 pl-9 pr-3 text-sm text-foreground outline-none transition-colors placeholder:text-muted-foreground/70 hover:border-primary/40 focus:border-primary/60"
          />
        </div>
        <div className="text-xs text-muted-foreground">
          <span className="font-medium text-foreground">{filtered.length}</span> / {agents.length} agents
        </div>
      </div>

      {/* category filter chips */}
      <div className="mb-4 flex flex-wrap gap-1.5">
        <button
          onClick={() => setCat(null)}
          className={cn(
            "rounded-full border px-2.5 py-1 text-xs font-medium transition-colors",
            cat === null
              ? "border-primary/50 bg-primary/10 text-foreground"
              : "border-border/70 text-muted-foreground hover:text-foreground",
          )}
        >
          All {agents.length}
        </button>
        {CATEGORY_ORDER.filter((c) => counts[c]).map((c) => {
          const tone = CATEGORY_TONE[c];
          const on = cat === c;
          return (
            <button
              key={c}
              onClick={() => setCat(on ? null : c)}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium transition-colors",
                on ? "text-foreground" : "border-border/70 text-muted-foreground hover:text-foreground",
              )}
              style={
                on
                  ? { borderColor: `hsl(${tone.hsl} / 0.5)`, background: `hsl(${tone.hsl} / 0.12)` }
                  : undefined
              }
            >
              <span className="h-1.5 w-1.5 rounded-full" style={{ background: `hsl(${tone.hsl})` }} />
              {tone.label} {counts[c]}
            </button>
          );
        })}
      </div>

      {/* grouped grid */}
      {grouped.length === 0 ? (
        <div className="rounded-xl border border-dashed border-border/70 py-12 text-center text-sm text-muted-foreground">
          No agents match “{query}”.
        </div>
      ) : (
        <div className="space-y-6">
          {grouped.map((g) => {
            const tone = CATEGORY_TONE[g.cat];
            return (
              <div key={g.cat}>
                <div className="mb-2 flex items-center gap-2">
                  <span className="h-2.5 w-2.5 rounded-[3px]" style={{ background: `hsl(${tone.hsl})` }} />
                  <h3 className="text-sm font-semibold text-foreground">{tone.label}</h3>
                  <span className="text-xs text-muted-foreground">{g.items.length}</span>
                </div>
                <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
                  {g.items.map((a) => (
                    <AgentRow key={a.id} agent={a} />
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
