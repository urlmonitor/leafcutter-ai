/**
 * The shared actor words and the step/branch card name (UXP-617-3). The finder's
 * actor facet, its step rows and the flow page's cards all read these, so Code,
 * AI agent, Person and Jev are spelled in one place (Jev is never folded into
 * AI agent).
 */
import { ACTOR_KIND_LABEL, type ActorKind } from "@/lib/data/actor-kind";

/** The badge word of a stored actor kind; null when the node has no actor. */
export function actorLabel(kind: ActorKind | null | undefined): string | null {
  return kind ? ACTOR_KIND_LABEL[kind] : null;
}

/**
 * The accessible name of a card: 'Step <order> of <step count>: <label> (<actor>)'
 * for a step, 'Branch: <label> (<actor>)' for a branch; no '(<actor>)' without an actor.
 */
export function cardLabel(p: {
  variant: "step" | "branch";
  label: string;
  order?: number;
  stepCount: number;
  actorKind?: ActorKind | null;
}): string {
  const head = p.variant === "step" ? `Step ${p.order} of ${p.stepCount}: ${p.label}` : `Branch: ${p.label}`;
  const actor = actorLabel(p.actorKind);
  return actor ? `${head} (${actor})` : head;
}
