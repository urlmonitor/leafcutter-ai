/**
 * Which of ADR-053's four mechanisms runs a flow step or branch — the stored
 * `actor_kind` (docs/product-truth/schemas/flow.schema.json). The free-text
 * `agent` names the actor; this says what kind of actor it is.
 */
/** In the order the badges and the finder's Actor facet list them: Code, AI agent, Person, Jev. */
export const ACTOR_KINDS = ["deterministic", "llm", "human", "jev"] as const;
export type ActorKind = (typeof ACTOR_KINDS)[number];

/** Plain-language badge text, so a reader need not know the enum values. */
export const ACTOR_KIND_LABEL: Record<ActorKind, string> = {
  deterministic: "Code",
  jev: "Jev",
  llm: "AI agent",
  human: "Person",
};

/** Accept only the four stored values; anything else is shown as no kind (null), never coerced. */
export function parseActorKind(value: unknown): ActorKind | null {
  return typeof value === "string" && (ACTOR_KINDS as readonly string[]).includes(value) ? (value as ActorKind) : null;
}
