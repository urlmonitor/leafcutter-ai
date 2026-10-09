import { describe, expect, it } from "vitest";
import { ACTOR_KINDS, ACTOR_KIND_LABEL, parseActorKind } from "../actor-kind";

describe("stored actor_kind normalization", () => {
  it.each(ACTOR_KINDS)("accepts the stored value %s unchanged", (kind) => {
    // covers: UXP-523-3
    // angle: criterion
    expect(parseActorKind(kind)).toBe(kind);
    expect(ACTOR_KIND_LABEL[kind]).toMatch(/\S/);
  });

  it.each([[undefined], [null], [""], ["LLM"], ["agent"], [["llm"]], [1], [{ kind: "human" }]])(
    "never coerces %j into an actor kind", (value: unknown) => {
      // covers: UXP-523-3
      // angle: discrimination
      expect(parseActorKind(value)).toBeNull();
    },
  );
});
