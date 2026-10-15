import { cn } from "@/lib/utils";
import type { ActorKind } from "@/lib/data/actor-kind";

const TONE: Record<ActorKind, string> = {
  deterministic: "border-border bg-muted/60 text-muted-foreground",
  llm: "border-chart-4/50 bg-chart-4/10 text-chart-4",
  human: "border-info/50 bg-info/10 text-info",
  jev: "border-primary/50 bg-primary/10 text-primary",
};

/** The actor badge: the label comes from the shared ACTOR_KIND_LABEL via the finder core. */
export function ActorBadge({
  actorKind,
  label,
  count,
}: {
  actorKind: ActorKind;
  label: string;
  count?: number;
}) {
  return (
    <span
      data-actor-kind={actorKind}
      className={cn(
        "inline-flex items-center whitespace-nowrap rounded-full border px-2 text-[11px] font-semibold leading-5",
        TONE[actorKind],
      )}
    >
      {label}
      {count !== undefined && <span className="ml-1 font-mono font-normal">{count}</span>}
    </span>
  );
}
