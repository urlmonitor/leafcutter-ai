"use client";

import { useState } from "react";
import { facetDef } from "@/lib/flow-finder/facets";
import { searchFields } from "@/lib/flow-finder/options";
import { flowsWithOption } from "@/lib/flow-finder/run-finder";
import type { FinderIndex, FinderRun, FinderState } from "@/lib/flow-finder/types";
import { FacetOptionRow } from "./facet-option-row";

/**
 * Uses field / Produces field: picked by type-ahead over the field keys the index
 * holds. Nothing is listed until a field name is typed, except the fields already
 * chosen, which stay listed so they can be unticked.
 */
export function FieldPicker({
  facet,
  index,
  state,
  run,
  onToggle,
}: {
  facet: "uses" | "produces";
  index: FinderIndex;
  state: FinderState;
  run: FinderRun;
  onToggle: (value: string) => void;
}) {
  const [text, setText] = useState("");
  const def = facetDef(facet);
  const chosen = run.facetOptions[facet];
  const found = searchFields(index, facet, text).filter((o) => !chosen.some((c) => c.value === o.value));

  return (
    <details open={chosen.length > 0 || undefined} className="border-b border-border/60 py-2">
      <summary className="cursor-pointer text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
        {def.title}
      </summary>
      <div className="mt-2 space-y-1">
        <label htmlFor={`finder-${facet}`} className="sr-only">
          {def.label}
        </label>
        <input
          id={`finder-${facet}`}
          type="text"
          autoComplete="off"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Type a field name"
          className="h-8 w-full rounded-md border border-input bg-background px-2 text-xs text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        />
        <div className="max-h-44 overflow-auto">
          {chosen.map((o) => (
            <FacetOptionRow
              key={o.value}
              label={o.label}
              count={run.facetCounts[facet][o.value] ?? 0}
              checked
              onToggle={() => onToggle(o.value)}
            />
          ))}
          {found.map((o) => (
            <FacetOptionRow
              key={o.value}
              label={o.label}
              count={flowsWithOption(index, state, facet, o.value)}
              checked={false}
              onToggle={() => onToggle(o.value)}
            />
          ))}
        </div>
      </div>
    </details>
  );
}
