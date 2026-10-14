import type { MouseEvent } from "react";
import type { FinderResult } from "@/lib/flow-finder/types";
import { ActorBadge } from "./actor-badge";

const PILL = "rounded-full border border-border px-2 text-[11px] text-muted-foreground";
const LINK =
  "rounded hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";
const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;

/** One flow: its facts, then up to three matching step rows and "N more steps". */
export function ResultCard({
  result,
  open,
}: {
  result: FinderResult;
  open?: (flowId: string, stepId: string | null) => (e: MouseEvent<HTMLAnchorElement>) => void;
}) {
  const { meta } = result;
  const noNodes = meta.stepCount + meta.branchCount === 0;
  return (
    <article className="rounded-xl border border-border bg-card p-4 transition-colors focus-within:border-primary/50 hover:border-primary/50">
      <h3 className="text-[15px] font-semibold leading-snug">
        <a href={result.href} onClick={open?.(result.flowId, null)} className={LINK}>
          {result.flowName}
        </a>
      </h3>
      <div className="mt-1.5 flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
        <span className={PILL}>{meta.productLabel}</span>
        <span className={PILL}>{meta.kind}</span>
        <span className={PILL}>{meta.realization}</span>
        <span className={PILL}>{meta.level}</span>
        <span>
          {noNodes
            ? "map of nodes"
            : `${plural(meta.stepCount, "step", "steps")} · ${plural(meta.branchCount, "branch", "branches")}`}
        </span>
        {meta.actorMix.map((m) => (
          <ActorBadge key={m.actorKind} actorKind={m.actorKind} label={m.actorLabel} count={m.count} />
        ))}
        {meta.ioGapNodes > 0 && (
          <span className="rounded-full border border-warning/50 px-2 text-[11px] text-warning">
            {plural(meta.ioGapNodes, "step", "steps")} with I/O not yet defined
          </span>
        )}
      </div>
      {result.stepRows.length > 0 && (
        <ul className="mt-3 border-t border-border/60">
          {result.stepRows.map((row) => (
            <li
              key={row.nodeId}
              className="grid grid-cols-[1fr_auto] gap-x-3 gap-y-0.5 border-b border-border/40 py-2 last:border-b-0"
            >
              <span className="min-w-0 text-sm">
                {row.nodeKind === "branch" && (
                  <span className="mr-1.5 text-[11px] uppercase tracking-wide text-muted-foreground">Branch</span>
                )}
        <a href={row.href} onClick={open?.(result.flowId, row.nodeId)} className={LINK}>
                  {row.label}
                </a>
              </span>
              {row.actorKind && row.actorLabel && <ActorBadge actorKind={row.actorKind} label={row.actorLabel} />}
              <span className="col-span-2 text-xs text-muted-foreground">{row.reason}</span>
            </li>
          ))}
        </ul>
      )}
      {result.moreSteps > 0 && (
        <a
          href={result.href}
          onClick={open?.(result.flowId, null)}
          className="mt-2 inline-block rounded text-xs text-accent underline-offset-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          {plural(result.moreSteps, "more step", "more steps")}
        </a>
      )}
    </article>
  );
}
