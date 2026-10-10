/**
 * "Runs" section of the flow step drawer: what kind of actor runs the step
 * (code, Jev, an AI agent or a person — the stored `actor_kind`) as a small
 * badge beside the named agent or script. Renders nothing when neither is known.
 */
import React from "react";
import { Bot } from "lucide-react";
import { ACTOR_KIND_LABEL, type ActorKind } from "@/lib/data/actor-kind";

export function StepRunner({ agent, actorKind }: { agent?: string | null; actorKind?: ActorKind | null }) {
  if (!agent && !actorKind) return null;
  return (
    <div>
      <div className="mb-1.5 flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wider text-muted-foreground/80">
        <Bot className="h-3 w-3" />
        Runs
      </div>
      <div className="flex flex-wrap items-center gap-1.5">
        {actorKind && (
          <span
            data-actor-kind={actorKind}
            title={`Actor kind: ${actorKind}`}
            className="inline-flex items-center rounded-full border border-border/70 bg-secondary/60 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-foreground/80"
          >
            {ACTOR_KIND_LABEL[actorKind]}
          </span>
        )}
        {agent && (
          <span className="inline-flex items-center gap-1.5 rounded-md border border-primary/30 bg-primary/10 px-2 py-1 font-mono text-[11px] text-primary">
            {agent}
          </span>
        )}
      </div>
    </div>
  );
}
