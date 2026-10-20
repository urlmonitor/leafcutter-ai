"use client";

import { FACET_DEFS, type FacetDef } from "@/lib/flow-finder/facets";
import type { FacetName, FinderIndex, FinderRun, FinderState } from "@/lib/flow-finder/types";
import { FacetOptionRow } from "./facet-option-row";
import { FieldPicker } from "./field-picker";

const HEADING = "text-[11px] font-semibold uppercase tracking-wider text-muted-foreground";

function Options({
  def,
  state,
  run,
  onToggle,
}: {
  def: FacetDef;
  state: FinderState;
  run: FinderRun;
  onToggle: (facet: FacetName, value: string) => void;
}) {
  return (
    <>
      {run.facetOptions[def.name].map((o) => (
        <FacetOptionRow
          key={o.value}
          label={o.label}
          count={run.facetCounts[def.name][o.value] ?? 0}
          checked={state.facets[def.name].includes(o.value)}
          onToggle={() => onToggle(def.name, o.value)}
        />
      ))}
    </>
  );
}

/** The counted facets, in declaration order (UXP-617-1-iii). */
export function FacetPanel({
  index,
  state,
  run,
  onToggle,
}: {
  index: FinderIndex;
  state: FinderState;
  run: FinderRun;
  onToggle: (facet: FacetName, value: string) => void;
}) {
  return (
    <aside
      aria-label="Filters"
      className="rounded-xl border border-border bg-secondary/30 px-3 py-1 lg:sticky lg:top-4 lg:max-h-[calc(100vh-2rem)] lg:overflow-y-auto"
    >
      {FACET_DEFS.map((def) => {
        if (def.source === "field") {
          return (
            <FieldPicker
              key={def.name}
              facet={def.name as "uses" | "produces"}
              index={index}
              state={state}
              run={run}
              onToggle={(value) => onToggle(def.name, value)}
            />
          );
        }
        if (def.source === "entity" || def.source === "screen") {
          return (
            <details
              key={def.name}
              open={state.facets[def.name].length > 0 || undefined}
              className="border-b border-border/60 py-2"
            >
              <summary className={`cursor-pointer ${HEADING}`}>{def.title}</summary>
              <div className="mt-1 max-h-44 overflow-auto">
                <Options def={def} state={state} run={run} onToggle={onToggle} />
              </div>
            </details>
          );
        }
        return (
          <fieldset key={def.name} className="m-0 border-0 border-b border-border/60 p-0 py-2 last:border-b-0">
            <legend className={`p-0 ${HEADING}`}>{def.title}</legend>
            <div className="mt-1">
              <Options def={def} state={state} run={run} onToggle={onToggle} />
            </div>
          </fieldset>
        );
      })}
    </aside>
  );
}
