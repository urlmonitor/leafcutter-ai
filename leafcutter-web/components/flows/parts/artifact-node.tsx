"use client";

/** Artifact knowledge-graph card (group-coloured accent; click for details). */
import * as React from "react";
import { Handle, Position, type NodeProps } from "reactflow";
import { cn } from "@/lib/utils";
import type { SelfRel } from "@/lib/data/types";
import {
  artifactEdgeStyle,
  ARTIFACT_GROUP_HSL,
  ARTIFACT_GROUP_LABEL,
} from "@/components/atlas/edges";

// Artifact node-family palette is defined once in components/atlas/edges.ts so
// the React renderer and the canvas PNG exporter cannot drift apart.
function groupHsl(group: string): string {
  return ARTIFACT_GROUP_HSL[group] ?? "155 7% 52%";
}

export interface ArtifactNodeData {
  label: string;
  group: string;
  path: string;
  key: string;
  note?: string;
  /** Self-referencing relationships, each carrying its encoding field. */
  selfRels?: SelfRel[];
  selected?: boolean;
}

function ArtifactNodeImpl({ data }: NodeProps<ArtifactNodeData>) {
  const { label, group, path, key, note, selfRels, selected } = data;
  const hsl = groupHsl(group);
  const groupLabel = ARTIFACT_GROUP_LABEL[group] ?? group;
  const [showDetails, setShowDetails] = React.useState(false);

  return (
    <div
      className={cn(
        "relative w-[200px] rounded-xl border bg-card/90 backdrop-blur",
        "transition-all duration-180",
        "hover:-translate-y-0.5 cursor-pointer",
      )}
      style={{
        borderColor: `hsl(${hsl} / ${selected ? "0.85" : "0.45"})`,
        boxShadow: selected
          ? `0 0 0 2px hsl(${hsl}), 0 12px 32px -14px hsl(${hsl} / 0.65)`
          : `0 8px 22px -16px hsl(0 0% 0% / 0.8)`,
      }}
      onClick={() => setShowDetails((v) => !v)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => e.key === "Enter" && setShowDetails((v) => !v)}
      aria-label={`Artifact node: ${label}`}
    >
      {/* Left group-color accent bar */}
      <div
        className="absolute left-0 top-3 bottom-3 w-[3px] rounded-full"
        style={{ background: `hsl(${hsl})` }}
        aria-hidden="true"
      />

      <Handle
        type="target"
        position={Position.Left}
        className="!h-1.5 !w-1.5 !border-0"
        style={{ background: `hsl(${hsl})` }}
        isConnectable={false}
      />
      <Handle
        type="source"
        position={Position.Right}
        className="!h-1.5 !w-1.5 !border-0"
        style={{ background: `hsl(${hsl})` }}
        isConnectable={false}
      />

      <div className="pl-4 pr-3.5 py-3">
        {/* Group chip */}
        <div className="mb-1.5 flex items-center justify-between gap-1">
          <span
            className="rounded-full px-2 py-0.5 text-[9px] font-semibold uppercase tracking-wide"
            style={{ color: `hsl(${hsl})`, background: `hsl(${hsl} / 0.14)` }}
          >
            {groupLabel}
          </span>
        </div>

        {/* Label */}
        <div className="text-sm font-semibold leading-snug text-foreground">
          {label}
        </div>

        {/* Self-referencing relationships (e.g. AC -> AC parent / depends_on).
            Drawn as a badge because a loop edge back to the same card is
            visually degenerate and would sit under the node. Each row names the
            ENCODING FIELD — three PARENT_OF rows are three different encodings,
            not a repeat — and carries the shape caveat glyph. */}
        {selfRels && selfRels.length > 0 && (
          <div className="mt-2 space-y-0.5 border-t border-border/30 pt-1.5">
            <div className="mb-1 text-[8.5px] font-medium uppercase tracking-wider text-muted-foreground/60">
              ↺ Self-relationships
            </div>
            {selfRels.map((sr) => {
              const spec = artifactEdgeStyle(sr.enforcement, sr.shape);
              return (
                <div
                  key={`${sr.rel}:${sr.field}`}
                  className="flex items-baseline gap-1.5 leading-tight"
                  title={sr.note ?? undefined}
                >
                  <span
                    className="inline-block h-1.5 w-1.5 shrink-0 rounded-full"
                    style={{ background: `hsl(${spec.hsl})` }}
                    aria-hidden="true"
                  />
                  <span className="text-[8.5px] font-semibold tracking-wide text-foreground/85">
                    {sr.rel}
                  </span>
                  <span className="font-mono text-[8px] text-muted-foreground/75">
                    {sr.field}
                  </span>
                  {spec.warnGlyph && (
                    <span className="text-[8.5px]" style={{ color: `hsl(${spec.hsl})` }}>
                      {spec.warnGlyph}
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {/* Details panel (toggled on click) */}
        {showDetails && (
          <div className="mt-2 space-y-1.5 border-t border-border/40 pt-2">
            <div className="flex flex-col gap-0.5">
              <span className="text-[9px] font-medium uppercase tracking-wider text-muted-foreground/70">
                Path
              </span>
              <span className="font-mono text-[9px] leading-relaxed text-muted-foreground break-all">
                {path}
              </span>
            </div>
            <div className="flex flex-col gap-0.5">
              <span className="text-[9px] font-medium uppercase tracking-wider text-muted-foreground/70">
                Key
              </span>
              <span className="font-mono text-[9px] text-foreground/80">{key}</span>
            </div>
            {note && (
              <div className="flex flex-col gap-0.5">
                <span className="text-[9px] font-medium uppercase tracking-wider text-muted-foreground/70">
                  Note
                </span>
                <span className="text-[9px] leading-relaxed text-muted-foreground">{note}</span>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export const ArtifactNode = React.memo(ArtifactNodeImpl);
