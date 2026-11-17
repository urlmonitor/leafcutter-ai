"use client";

/**
 * Legend panel of the artifact-graph canvas: node groups, edge-trust key, and
 * the full trust record of the selected edge.
 */
import * as React from "react";
import {
  artifactEdgeStyle,
  INGESTABILITY_LEGEND,
  ARTIFACT_GROUP_HSL,
  ARTIFACT_GROUP_LABEL,
} from "@/components/atlas/edges";
import type { GraphEdge } from "@/lib/data/types";

export function ArtifactLegend({
  selectedEdge,
  onClose,
}: {
  selectedEdge: GraphEdge | null;
  onClose: () => void;
}) {
  return (
  <div className="pointer-events-none absolute right-4 top-4 z-10">
    <div className="pointer-events-auto panel max-w-xs p-3.5">
      <div className="eyebrow mb-2">Legend</div>
      <div className="mb-1 text-[10px] font-medium uppercase tracking-wider text-muted-foreground/80">
        Node group
      </div>
      <div className="mb-3 flex flex-wrap gap-x-3 gap-y-1.5">
        {Object.entries(ARTIFACT_GROUP_LABEL).map(([group, label]) => (
          <span
            key={group}
            className="inline-flex items-center gap-1.5 text-[11px] text-muted-foreground"
          >
            <span
              className="h-2 w-[3px] rounded-full"
              style={{ background: `hsl(${ARTIFACT_GROUP_HSL[group]})` }}
            />
            {label}
          </span>
        ))}
      </div>
      <div className="mb-1 text-[10px] font-medium uppercase tracking-wider text-muted-foreground/80">
        Edge trust
      </div>
      <div className="flex flex-col gap-1">
        {INGESTABILITY_LEGEND.map((row) => (
          <span
            key={row.key}
            className="inline-flex items-baseline gap-1.5 text-[11px] text-muted-foreground"
          >
            <svg width="20" height="6" className="shrink-0 overflow-visible">
              <line
                x1="0" y1="3" x2="20" y2="3"
                stroke={`hsl(${row.hsl})`}
                strokeWidth="2"
                strokeDasharray={
                  row.key === "absent"
                    ? "2 7"
                    : row.key === "untrusted"
                      ? "4 3"
                      : undefined
                }
              />
            </svg>
            <span className="text-foreground/85">{row.label}</span>
            <span className="text-[9px] text-muted-foreground/70">{row.hint}</span>
          </span>
        ))}
      </div>
      <p className="mt-2.5 text-[9px] leading-relaxed text-muted-foreground/70">
        Labels show the <span className="font-mono">field</span> that encodes each edge.
        ⚠ ambiguous · ~ freetext · ∅ often-empty — these need partitioning before
        ingestion even when enforced. Dashes mark derived or untrusted links.
        A red ✗ line is a relation the repo does NOT have — recorded so a gap
        is distinguishable from an omission, never traversable.
        Click an edge for its full trust record; ↺ on a card lists
        self-referencing relationships.
      </p>

      {selectedEdge && (() => {
        const spec = artifactEdgeStyle(
          selectedEdge.enforcement ?? "none",
          selectedEdge.shape ?? "clean",
          selectedEdge.status ?? "present",
        );
        return (
          <div className="mt-3 border-t border-border/40 pt-2.5">
            <div className="mb-1.5 flex items-center justify-between gap-2">
              <span
                className="text-[11px] font-semibold"
                style={{ color: `hsl(${spec.hsl})` }}
              >
                {selectedEdge.rel}
              </span>
              <button
                type="button"
                onClick={() => onClose()}
                className="text-[10px] text-muted-foreground hover:text-foreground"
              >
                close
              </button>
            </div>
            <dl className="space-y-1 text-[9.5px] leading-relaxed">
              <div>
                <dt className="inline text-muted-foreground/70">field </dt>
                <dd className="inline font-mono text-foreground/85">
                  {selectedEdge.field ?? "—"}
                </dd>
              </div>
              <div>
                <dt className="inline text-muted-foreground/70">trust </dt>
                <dd className="inline text-foreground/85">
                  {selectedEdge.status === "absent"
                    ? "no such link"
                    : `${selectedEdge.enforcement} · ${selectedEdge.shape}`}{" "}
                  <span style={{ color: `hsl(${spec.hsl})` }}>
                    ({spec.ingestability})
                  </span>
                </dd>
              </div>
              <div>
                <dt className="inline text-muted-foreground/70">cardinality </dt>
                <dd className="inline text-foreground/85">
                  {selectedEdge.cardinality ?? "—"}
                </dd>
              </div>
              {selectedEdge.note && (
                <div className="pt-0.5 text-muted-foreground">
                  {selectedEdge.note}
                </div>
              )}
            </dl>
          </div>
        );
      })()}
    </div>
  </div>
  );
}
