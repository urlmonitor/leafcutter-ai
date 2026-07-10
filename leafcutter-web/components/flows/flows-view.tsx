"use client";

/**
 * Client shell for the Flows view. Owns the filter + selection state:
 *   - a SOURCE toggle (Mock / Real),
 *   - a KIND chooser (User / Data / Architecture) showing only kinds that have
 *     ≥1 flow for the current source,
 *   - a per-flow selector listing only flows matching source + kind, each with a
 *     live "done/total" badge.
 * Everything is a pure client swap (no route change). <FlowExplorer> is remounted
 * (via key) whenever the selected flow changes, so the canvas refits and the step
 * drawer resets. Empty source+kind combos render a small empty state.
 */
import * as React from "react";
import { PageHeader, Badge, EmptyState } from "@/components/ui/kit";
import { cn, humanize } from "@/lib/utils";
import { WORK_STATUS_TONE } from "@/lib/status";
import type { Flow, FlowKind, FlowSource, MockData } from "@/lib/data/types";
import { FlowExplorer } from "./flow-explorer";
import { Workflow } from "lucide-react";

const SOURCES: FlowSource[] = ["mock", "real"];
const KINDS: FlowKind[] = ["user", "data", "architecture"];

function Segmented<T extends string>({
  label,
  options,
  value,
  onChange,
  render,
}: {
  label: string;
  options: T[];
  value: T;
  onChange: (next: T) => void;
  render: (opt: T) => React.ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground/80">
        {label}
      </span>
      <div className="inline-flex flex-wrap gap-1 rounded-lg border border-border/70 bg-card/60 p-1">
        {options.map((opt) => {
          const active = opt === value;
          return (
            <button
              key={opt}
              type="button"
              onClick={() => onChange(opt)}
              className={cn(
                "inline-flex items-center gap-2 rounded-md px-3 py-1.5 text-sm transition-colors",
                active
                  ? "bg-primary/15 font-medium text-foreground"
                  : "text-muted-foreground hover:bg-secondary/60 hover:text-foreground",
              )}
            >
              {render(opt)}
            </button>
          );
        })}
      </div>
    </div>
  );
}

export function FlowsView({
  flows,
  mocks,
}: {
  flows: Flow[];
  mocks: Record<string, MockData | null>;
}) {
  const [source, setSource] = React.useState<FlowSource>("real");
  const [kind, setKind] = React.useState<FlowKind>("user");
  const [selectedId, setSelectedId] = React.useState<string>("");

  // Kinds that actually have a flow for the current source.
  const kindsForSource = React.useCallback(
    (src: FlowSource) => KINDS.filter((k) => flows.some((f) => f.source === src && f.kind === k)),
    [flows],
  );
  const availableKinds = kindsForSource(source);
  // If the chosen kind has no flows for this source, fall back to the first that does.
  const effectiveKind = availableKinds.includes(kind) ? kind : availableKinds[0] ?? kind;

  const filtered = React.useMemo(
    () => flows.filter((f) => f.source === source && f.kind === effectiveKind),
    [flows, source, effectiveKind],
  );

  // Selected flow, falling back to the first match when the current pick is out of scope.
  const flow = filtered.find((f) => f.id === selectedId) ?? filtered[0] ?? null;
  const mock = flow ? mocks[flow.id] ?? null : null;

  const onSelectSource = (next: FlowSource) => {
    setSource(next);
    // Auto-select the first kind that has flows in the new source, if the current one doesn't.
    const kinds = kindsForSource(next);
    if (!kinds.includes(kind)) setKind(kinds[0] ?? kind);
  };

  const s = flow?.implSummary;

  return (
    <div className="flex flex-col">
      <PageHeader
        eyebrow={
          flow?.product ? `Product truth · ${flow.product}` : "Product truth"
        }
        title={flow?.name ?? "Flows"}
        description={
          flow?.summary ??
          "Interactive maps of how a product actually behaves, step by step."
        }
      >
        {flow && s && (
          <div className="flex flex-wrap items-center justify-end gap-1.5">
            <Badge tone={WORK_STATUS_TONE.done} dot>
              {s.done} done
            </Badge>
            <Badge tone={WORK_STATUS_TONE.in_progress} dot>
              {s.in_progress} in progress
            </Badge>
            <Badge tone={WORK_STATUS_TONE.not_started} dot>
              {s.not_started} not started
            </Badge>
            <span className="ml-1 text-xs text-muted-foreground">
              of <span className="font-mono tabular-nums text-foreground">{s.total}</span> steps
            </span>
          </div>
        )}
      </PageHeader>

      {/* source + kind controls */}
      <div className="mb-3 flex flex-wrap items-center gap-x-6 gap-y-2">
        <Segmented
          label="Source"
          options={SOURCES}
          value={source}
          onChange={onSelectSource}
          render={(opt) => <span>{opt === "mock" ? "Mock" : "Real"}</span>}
        />
        {availableKinds.length > 0 && (
          <Segmented
            label="Kind"
            options={availableKinds}
            value={effectiveKind}
            onChange={setKind}
            render={(opt) => <span>{humanize(opt)}</span>}
          />
        )}
      </div>

      {/* per-flow selector (only flows matching source + kind) */}
      {filtered.length > 0 && (
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <span className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground/80">
            Flow
          </span>
          <div className="inline-flex flex-wrap gap-1 rounded-lg border border-border/70 bg-card/60 p-1">
            {filtered.map((f) => {
              const active = f.id === flow?.id;
              return (
                <button
                  key={f.id}
                  type="button"
                  onClick={() => setSelectedId(f.id)}
                  className={cn(
                    "inline-flex items-center gap-2 rounded-md px-3 py-1.5 text-sm transition-colors",
                    active
                      ? "bg-primary/15 font-medium text-foreground"
                      : "text-muted-foreground hover:bg-secondary/60 hover:text-foreground",
                  )}
                >
                  <span>{f.name}</span>
                  <span
                    className={cn(
                      "rounded px-1.5 py-0.5 font-mono text-[10px] tabular-nums",
                      active
                        ? "bg-success/15 text-success"
                        : "bg-muted/50 text-muted-foreground",
                    )}
                  >
                    {f.implSummary.done}/{f.implSummary.total} done
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {flow ? (
        <>
          <div className="mb-3 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            {flow.entities.length > 0 && (
              <>
                <span className="font-medium text-foreground">Entities:</span>
                {flow.entities.map((e) => (
                  <span
                    key={e}
                    className="rounded-md border border-border/70 bg-card/60 px-2 py-0.5 font-mono text-[11px]"
                  >
                    {e}
                  </span>
                ))}
              </>
            )}
            {mock && (
              <span className={flow.entities.length > 0 ? "ml-1" : ""}>
                {flow.entities.length > 0 ? "· " : ""}mock data{" "}
                <span className="font-mono text-foreground">
                  {humanize(mock.id.split("/").pop() ?? mock.id)}
                </span>
              </span>
            )}
          </div>

          <FlowExplorer key={flow.id} flow={flow} mock={mock} />
        </>
      ) : (
        <EmptyState
          icon={<Workflow className="h-6 w-6" />}
          title={`No ${humanize(effectiveKind)} flows in ${source === "mock" ? "Mock" : "Real"} yet`}
          hint="Pick another source or kind above, or add a flow with that kind + source."
        />
      )}
    </div>
  );
}
