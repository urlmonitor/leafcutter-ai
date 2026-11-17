"use client";

import type { MouseEvent } from "react";
import type { FinderEmptyState } from "@/lib/flow-finder/types";

/** Nothing matches: the title names the search or the filters, with one way out per chosen filter. */
export function FinderEmpty({
  empty,
  inPlace,
}: {
  empty: FinderEmptyState;
  inPlace: (href: string) => (e: MouseEvent<HTMLAnchorElement>) => void;
}) {
  return (
    <div className="rounded-xl border border-dashed border-border bg-card/50 p-6">
      <h3 className="text-base font-semibold text-foreground">{empty.title}</h3>
      <p className="mb-4 mt-1 text-sm text-muted-foreground">{empty.detail}</p>
      <div className="flex flex-wrap gap-2">
        {empty.suggestions.map((s) => (
          <a
            key={s.href}
            href={s.href}
            onClick={inPlace(s.href)}
            className="rounded-lg border border-primary/50 px-3 py-1.5 text-[13px] text-primary transition-colors hover:bg-primary/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring active:bg-primary/20"
          >
            {s.label}{" "}
            <span className="text-muted-foreground">
              · {s.flows} {s.flows === 1 ? "flow" : "flows"}
            </span>
          </a>
        ))}
      </div>
    </div>
  );
}
