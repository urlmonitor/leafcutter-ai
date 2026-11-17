"use client";

import type { MouseEventHandler } from "react";
import { X } from "lucide-react";
import type { FinderChip } from "@/lib/flow-finder/types";

/** One removable chip per chosen facet value, in address order, plus Clear all. */
export function AppliedChips({
  chips,
  clearAllHref,
  onRemove,
  onClearAll,
}: {
  chips: FinderChip[];
  clearAllHref: string | null;
  onRemove: (chip: FinderChip) => void;
  onClearAll: MouseEventHandler<HTMLAnchorElement>;
}) {
  if (chips.length === 0) return null;
  return (
    <ul aria-label="Applied filters" className="my-3 flex flex-wrap items-center gap-2">
      {chips.map((chip) => (
        <li
          key={`${chip.facet}:${chip.value}`}
          className="inline-flex items-center gap-1 rounded-full border border-primary/50 bg-primary/10 py-0.5 pl-2.5 pr-1 text-xs text-primary"
        >
          <span>{chip.label}</span>
          <button
            type="button"
            aria-label={`Remove filter ${chip.label}`}
            onClick={() => onRemove(chip)}
            className="rounded-full p-0.5 transition-colors hover:bg-primary/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring active:bg-primary/30"
          >
            <X aria-hidden="true" className="h-3.5 w-3.5" />
          </button>
        </li>
      ))}
      {clearAllHref && (
        <li>
          <a
            href={clearAllHref}
            onClick={onClearAll}
            className="rounded text-xs text-accent underline-offset-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            Clear all
          </a>
        </li>
      )}
    </ul>
  );
}
