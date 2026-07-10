"use client";

import * as React from "react";
import { Search, FileText, GitBranch, X, SlidersHorizontal } from "lucide-react";
import { cn } from "@/lib/utils";
import { componentStatusTone, type ComponentVM, type TypeCluster } from "./lib";
import { ComponentDrawer } from "./component-drawer";

export function ComponentMap({ clusters }: { clusters: TypeCluster[] }) {
  const allTypes = React.useMemo(() => clusters.map((c) => c.type), [clusters]);
  const [active, setActive] = React.useState<Set<string>>(() => new Set(allTypes));
  const [query, setQuery] = React.useState("");
  const [selected, setSelected] = React.useState<ComponentVM | null>(null);

  const q = query.trim().toLowerCase();
  const allOn = active.size === allTypes.length;

  const toggle = (t: string) =>
    setActive((prev) => {
      const next = new Set(prev);
      if (next.has(t)) next.delete(t);
      else next.add(t);
      return next;
    });

  const matches = (c: ComponentVM) =>
    !q ||
    c.name.toLowerCase().includes(q) ||
    c.description.toLowerCase().includes(q) ||
    c.id.toLowerCase().includes(q);

  const visible = clusters
    .filter((cl) => active.has(cl.type))
    .map((cl) => ({ ...cl, components: cl.components.filter(matches) }))
    .filter((cl) => cl.components.length > 0);

  const shown = visible.reduce((n, cl) => n + cl.components.length, 0);
  const selectedCluster = selected ? clusters.find((c) => c.type === selected.type) : null;

  return (
    <div>
      {/* Controls */}
      <div className="mb-5 flex flex-col gap-4 rounded-xl border border-border/70 bg-card/40 p-4 backdrop-blur-sm lg:flex-row lg:items-center lg:justify-between">
        <div className="flex flex-wrap items-center gap-2">
          <span className="eyebrow mr-1 inline-flex items-center gap-1.5">
            <SlidersHorizontal className="h-3.5 w-3.5" />
            Types
          </span>
          {clusters.map((cl) => {
            const on = active.has(cl.type);
            return (
              <button
                key={cl.type}
                onClick={() => toggle(cl.type)}
                aria-pressed={on}
                className={cn(
                  "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium transition-all",
                  on
                    ? "text-foreground"
                    : "border-border/60 text-muted-foreground/60 hover:text-muted-foreground",
                )}
                style={
                  on
                    ? {
                        color: `hsl(${cl.hsl})`,
                        borderColor: `hsl(${cl.hsl} / 0.4)`,
                        background: `hsl(${cl.hsl} / 0.12)`,
                      }
                    : undefined
                }
              >
                <span
                  className="h-2 w-2 rounded-[3px]"
                  style={{ background: on ? `hsl(${cl.hsl})` : "hsl(var(--muted-foreground) / 0.4)" }}
                />
                {cl.label}
                <span className="tabular-nums opacity-70">{cl.total}</span>
              </button>
            );
          })}
          <button
            onClick={() => setActive(new Set(allOn ? [] : allTypes))}
            className="ml-1 rounded-full border border-border/60 px-2.5 py-1 text-xs font-medium text-muted-foreground transition-colors hover:text-foreground"
          >
            {allOn ? "Clear" : "All"}
          </button>
        </div>

        <div className="relative w-full shrink-0 lg:w-64">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground/60" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search components…"
            className="w-full rounded-lg border border-border/70 bg-background/60 py-2 pl-9 pr-8 text-sm text-foreground placeholder:text-muted-foreground/60 outline-none transition-colors focus:border-primary/50"
          />
          {query && (
            <button
              onClick={() => setQuery("")}
              className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-0.5 text-muted-foreground/70 hover:text-foreground"
              aria-label="Clear search"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      </div>

      <div className="mb-4 text-xs text-muted-foreground">
        Showing <span className="tabular-nums text-foreground">{shown}</span> component
        {shown === 1 ? "" : "s"} across{" "}
        <span className="tabular-nums text-foreground">{visible.length}</span> cluster
        {visible.length === 1 ? "" : "s"}
      </div>

      {/* Clustered board */}
      {visible.length ? (
        <div className="grid grid-cols-1 items-start gap-4 md:grid-cols-2 xl:grid-cols-3">
          {visible.map((cl) => (
            <Cluster key={cl.type} cluster={cl} onSelect={setSelected} />
          ))}
        </div>
      ) : (
        <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-border/70 py-16 text-center">
          <p className="text-sm font-medium text-foreground">No components match</p>
          <p className="mt-1 text-xs text-muted-foreground">
            Adjust the type filters or clear the search.
          </p>
        </div>
      )}

      <ComponentDrawer
        component={selected}
        hsl={selectedCluster?.hsl ?? "150 64% 52%"}
        typeLabel={selectedCluster?.label ?? ""}
        onClose={() => setSelected(null)}
      />
    </div>
  );
}

function Cluster({
  cluster,
  onSelect,
}: {
  cluster: TypeCluster;
  onSelect: (c: ComponentVM) => void;
}) {
  return (
    <section
      className="panel overflow-hidden p-0"
      style={{ borderColor: `hsl(${cluster.hsl} / 0.25)` }}
    >
      <header
        className="flex items-center justify-between gap-2 border-b px-4 py-3"
        style={{
          borderColor: `hsl(${cluster.hsl} / 0.2)`,
          background: `linear-gradient(180deg, hsl(${cluster.hsl} / 0.08), transparent)`,
        }}
      >
        <div className="flex items-center gap-2">
          <span className="h-2.5 w-2.5 rounded-[3px]" style={{ background: `hsl(${cluster.hsl})` }} />
          <h3 className="text-sm font-semibold tracking-tight text-foreground">{cluster.label}</h3>
        </div>
        <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
          <span
            className="inline-flex items-center gap-1"
            title={`${cluster.documented} of ${cluster.total} documented`}
          >
            <FileText className="h-3 w-3" />
            {cluster.documented}/{cluster.total}
          </span>
          <span
            className="rounded-full px-1.5 py-0.5 font-medium tabular-nums"
            style={{ color: `hsl(${cluster.hsl})`, background: `hsl(${cluster.hsl} / 0.12)` }}
          >
            {cluster.components.length}
          </span>
        </div>
      </header>

      <div className="grid grid-cols-1 gap-2 p-3 sm:grid-cols-2">
        {cluster.components.map((c) => (
          <Node key={c.id} c={c} hsl={cluster.hsl} onSelect={onSelect} />
        ))}
      </div>
    </section>
  );
}

function Node({
  c,
  hsl,
  onSelect,
}: {
  c: ComponentVM;
  hsl: string;
  onSelect: (c: ComponentVM) => void;
}) {
  const status = componentStatusTone(c.status);
  return (
    <button
      onClick={() => onSelect(c)}
      style={{ ["--tc" as string]: `hsl(${hsl})` }}
      className="group flex w-full items-center gap-2.5 rounded-lg border border-border/60 bg-background/40 px-3 py-2.5 text-left transition-all hover:-translate-y-0.5 hover:[border-color:var(--tc)] hover:bg-card/80"
    >
      <span
        className="h-2 w-2 shrink-0 rounded-full ring-2 ring-transparent transition-all group-hover:ring-[hsl(var(--border))]"
        style={{ background: `hsl(${status.hsl})` }}
        title={status.label}
      />
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-medium text-foreground">{c.name}</span>
      </span>
      <span className="flex shrink-0 items-center gap-1.5 text-muted-foreground/50">
        {c.acLink && (
          <span
            className="inline-flex items-center gap-0.5 text-[10px] font-medium text-muted-foreground/80"
            title={`${c.acLink.acCount} acceptance criteria`}
          >
            <GitBranch className="h-3 w-3" />
            {c.acLink.acCount}
          </span>
        )}
        {c.detailRef && <FileText className="h-3.5 w-3.5 text-primary/70" />}
      </span>
    </button>
  );
}
