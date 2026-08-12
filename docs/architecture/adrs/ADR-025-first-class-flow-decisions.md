---
title: "ADR-025: Decisions Are First-Class Flow Entities, Rendered as Chained Diamonds"
description: "Records the decision to promote decision points from implicit second-class `branches[]` to explicit first-class `decisions[]` entities in the product-truth flow schema — each decision carrying a from-step, a human-readable question, and labelled outcomes (condition + edge label + target). Multi-branch forks chain (diamond → diamond → happy path) rather than fanning into one N-way diamond. All ~15 existing flows are migrated and enriched, and the Leafcutter Atlas renders each decision as a diamond node with labelled yes/no edges."
type: "adr"
status: "active"
created: "2026-08-10"
last_updated: "2026-08-10"
deciders:
  - BrainCandy
components:
  - ux_prototyping
  - frontend_coding
  - build_pipeline
related_docs:
  - docs/architecture/adrs/ADR-023-product-truth-flow-first-upstream-layer.md
  - docs/architecture/adrs/ADR-022-mockups-are-the-real-app-in-mock-mode.md
  - docs/architecture/adrs/ADR-021-plan-feature-product-truth-phase.md
related_code:
  - docs/product-truth/schemas/flow.schema.json
  - docs/product-truth/scripts/validate_product_truth.py
  - leafcutter-web/lib/data/graph.ts
  - leafcutter-web/components/flows/flow-nodes.tsx
---

# ADR-025: Decisions Are First-Class Flow Entities, Rendered as Chained Diamonds

## Status

| Field | Value |
|---|---|
| Status | Proposed |
| Date | 2026-08-10 |
| Deciders | BrainCandy |
| Author | adr-author |
| Supersedes | — |

## Context

[ADR-023](ADR-023-product-truth-flow-first-upstream-layer.md) established the
product-truth store as the flow-first upstream authoring surface: a feature's
journey is authored as a `<product>/<name>.flow.json` before its ACs exist, and
the Leafcutter Atlas (`leafcutter-web/`) renders that journey live.

Today a flow models two things (`docs/product-truth/schemas/flow.schema.json`):

- **`steps[]`** — the ordered spine of the journey. Each step has an `id`,
  `label`, `human` line, `order`, an optional `screen`, and `implements` AC links.
- **`branches[]`** — the "what-if" forks. A branch is
  `{ id, from, condition, label, human?, screen?, implements?, … }`, where
  `from` is the id of the step it forks off.

A **branch is an implicit, second-class fork.** Three concrete symptoms follow
from that:

1. **A decision has no home to be enriched.** The *question* being asked at the
   fork ("Did the card authorize?") is nowhere in the data — it is only implied
   by the collection of `condition` strings that happen to share the same `from`.
   There is no `id`, no label, and no place to attach a human-readable question
   to the decision itself.

2. **Multi-branch forks are structurally invisible.** When several branches share
   one `from` step, nothing in the schema says "these three branches are the
   *outcomes of one decision*." They are three independent siblings. The real
   `fern-and-fig/checkout-and-pay` flow shows this exactly: the `authorize` step
   has two branches (`declined`, `soldOutAtPay`) plus the implicit happy-path
   fall-through to `confirmed` — three outcomes of one "authorization result"
   decision, modelled as two unrelated branch objects and one unstated edge.

3. **The renderer carries all the semantics, and still cannot tell them apart.**
   `buildFlowGraph` in `leafcutter-web/lib/data/graph.ts` emits every step **and**
   every branch as the same `kind: "phase"` node (distinguished only by a
   `meta.variant` of `"step"` vs `"branch"`), and `flow-nodes.tsx` renders both
   as the same 220px rounded card — the branch merely gets a dashed border and a
   `GitBranch` icon. A decision looks like just another step. There is no diamond,
   no question label on the node, and no yes/no label on the edges; a
   branch→target edge is an unlabelled `kind: "flow"` edge identical to a
   step→step edge.

The product owner has decided to fix this at the schema level rather than in the
renderer, so decisions become a reviewable, enrichable, first-class part of the
product truth. There are roughly **15 existing `*.flow.json` files** under
`docs/product-truth/flows/` (across the `leafcutter` and `fern-and-fig`
products), most carrying at least one `branches[]` entry; they are also thin and
should be enriched in the same migration pass.

## Decision

**Decision points are promoted to first-class entities in the flow schema. A new
`decisions[]` array explicitly models each fork; `branches[]` is retired and its
data is migrated into it. Multi-outcome forks CHAIN as diamond → diamond → happy
path. The Atlas renders each decision as a diamond node with labelled edges.**

Four rules realise this.

### 1. Decisions are modelled explicitly, not derived from branch fields

A **decision** is a schema entity anchored to the step it forks from, carrying
the human-readable question and an ordered list of outcomes. It is **authored**,
not reconstructed at render time from `condition` strings.

The proposed schema shape (added to `flow.schema.json`, replacing `branches[]`):

```jsonc
"decisions": {
  "type": "array",
  "items": {
    "type": "object",
    "additionalProperties": false,
    "required": ["id", "from", "question", "outcomes"],
    "properties": {
      "id":       { "type": "string", "description": "Unique within the shared step/decision/outcome id namespace." },
      "from":     { "type": "string", "description": "id of the step this decision forks from." },
      "question": { "type": "string", "description": "HUMAN: the yes/no (or multi-way) question rendered INSIDE the diamond, e.g. 'Did the card authorize?'." },
      "human":    { "type": "string", "description": "HUMAN: optional one-line elaboration of what is being decided." },
      "outcomes": {
        "type": "array",
        "minItems": 2,
        "items": {
          "type": "object",
          "additionalProperties": false,
          "required": ["id", "condition", "label", "to"],
          "properties": {
            "id":        { "type": "string" },
            "condition": { "type": "string", "description": "MACHINE: the branch predicate, e.g. 'the processor declines the card'." },
            "label":     { "type": "string", "description": "HUMAN: short edge label rendered ON the arrow, e.g. 'yes', 'no', 'declined'." },
            "to": {
              "type": "object",
              "additionalProperties": false,
              "description": "Exactly ONE of step / screen / terminal — where this outcome leads.",
              "properties": {
                "step":     { "type": "string", "description": "id of the step this outcome continues to (rejoins the spine)." },
                "screen":   { "type": "string", "description": "mockup id this outcome lands on (a dead-end surface)." },
                "terminal": { "type": "string", "description": "HUMAN: end-state label when the outcome ends the journey, e.g. 'Order not placed'." }
              }
            },
            "human":      { "type": "string" },
            "screen":     { "type": "string", "description": "mockup id rendered while on this outcome, if any." },
            "implements": { "type": "array", "items": { "type": "string" }, "description": "AC ids derived from this outcome." },
            "impl_status":{ "type": "string", "enum": ["not_started", "in_progress", "done"] },
            "impl_asof":  { "type": "string" }
          }
        }
      }
    }
  }
}
```

A worked example — the `authorize` fork of `fern-and-fig/checkout-and-pay`,
today two `branches[]` objects plus an unstated happy path, becomes one decision:

```jsonc
{
  "id": "authResult",
  "from": "authorize",
  "question": "Did the card authorize and is the item still in stock?",
  "outcomes": [
    { "id": "declined",     "condition": "the processor declines the card",
      "label": "declined",  "to": { "terminal": "No order placed; cart kept" },
      "screen": "checkout", "implements": ["UXP-210d-2"] },
    { "id": "soldOutAtPay", "condition": "the plant dropped to zero stock after add-to-cart",
      "label": "sold out",  "to": { "terminal": "No order created" },
      "screen": "checkout", "implements": ["UXP-210d-3"] },
    { "id": "ok",           "condition": "the card authorizes and the item is in stock",
      "label": "success",   "to": { "step": "confirmed" },
      "implements": ["UXP-210d-6"] }
  ]
}
```

### 2. Migration from `branches[]` is well-defined

The mapping from today's data to the new model is deterministic:

- **Each `branches[]` object becomes one `outcome`** of a decision. Its
  `condition`, `label`, `human`, `screen`, and `implements` carry over unchanged
  onto the outcome.
- **All branches sharing the same `from` step collapse into ONE decision**
  anchored at that step. The decision's `question` is authored fresh during
  migration (it is the enrichment this pass adds — the question was never stored).
- **The outcome's `to` is inferred and then confirmed by hand.** A legacy branch
  that only `screen`s and does not rejoin the spine maps to `to.terminal` (or
  `to.screen` when it lands on a dead-end surface); the implicit fall-through from
  the `from` step to the next ordered step becomes an **explicit** outcome whose
  `to.step` is that next step. Every fork therefore gains its previously-unstated
  happy-path outcome.
- **`acceptance_scenarios[].for`** continues to resolve against the shared id
  namespace, which now spans steps, decisions, and outcomes. Existing `for`
  values that pointed at a branch id MUST be repointed at the corresponding
  outcome id (the migration preserves branch ids as outcome ids to keep this
  a rename-free move wherever possible).

Migration MUST enrich, not merely transliterate: each migrated flow gains its
authored `question` text, its explicit happy-path outcome, and any missing
`human`/`label` copy, per the product owner's directive that the thin existing
flows be improved in the same pass.

### 3. Multi-outcome forks CHAIN — one diamond per outcome

A decision with N outcomes renders as a **chain of N−1 diamonds**, not a single
N-way diamond:

```
step ──▶ ◇ q₁ ──label₁──▶ outcome₁ target
          │ (else)
          ▼
          ◇ q₂ ──label₂──▶ outcome₂ target
          │ (else)
          ▼
          happy-path outcome (rejoins spine)
```

Each diamond tests one outcome's `condition` and is labelled with that outcome's
`label`; its "else" edge descends to the next diamond, and the final else is the
happy path. This keeps every fork a readable series of binary questions and
scales to arbitrary N without an unreadable star of edges from one node.

### 4. The Atlas renders decisions as labelled diamonds

`buildFlowGraph` (`leafcutter-web/lib/data/graph.ts`) MUST emit a distinct
`decision` node kind per diamond in the chain (not a `phase` node with
`variant: "branch"`), and MUST emit **labelled** edges — the outcome `label`
rides on the edge, and the "else" edges are marked as the fall-through. A new
diamond renderer in `flow-nodes.tsx` MUST draw the `question` inside a diamond
shape, visually distinct from the step card. Decision and outcome nodes tint by
their derived `impl_status`, consistent with ADR-023 rule 3 (status is derived
from AC `work_status`, never hand-edited).

The `docs/product-truth/scripts/validate_product_truth.py` validator MUST be
extended to enforce the new invariants: `decisions[].from` resolves to a step id,
`to` names exactly one of step/screen/terminal, `to.step`/`to.screen` resolve,
outcome ids are unique in the shared namespace, and every `acceptance_scenarios`
`for` still resolves. `branches[]` MUST be rejected once migration is complete.

> **Component note.** `ux_prototyping` owns the flow schema, the store, and the
> Atlas surface; `frontend_coding` is tagged because the diamond renderer rework
> lands in the `leafcutter-web` frontend; `build_pipeline` is tagged because the
> product-truth validator (a commit-gate) must learn the new schema. These are
> the closest registered component ids for the three touched surfaces.

## Consequences

### Positive

- **Decisions become reviewable and enrichable.** A persona reviewing a flow
  sees the actual question at each fork, not a bag of condition strings. The
  decision has an id, a label, and a home for `human` copy and AC links.
- **Multi-branch forks are explicit and honest.** The one-decision-per-fork model
  captures the previously-unstated happy-path outcome, so a fork can no longer
  silently omit the "everything went fine" edge.
- **The renderer stops carrying the semantics.** Because the schema now says
  "this is a decision with these outcomes," `buildFlowGraph` reads structure
  instead of inferring a fork from shared `from` values, and a decision is
  visually unmistakable (a diamond, not another card).
- **Arbitrary N stays readable.** Chaining renders any fork as a series of binary
  questions with labelled edges rather than an N-way star.

### Negative / Costs

- **All ~15 existing flows must be migrated and enriched.** Every
  `*.flow.json` under `docs/product-truth/flows/` that carries `branches[]`
  (nearly all of them — `checkout-and-pay`, `track-an-order`,
  `customer-buys-a-plant`, `define-a-feature`, `deliver-a-feature`,
  `ac-lifecycle`, `finalize-feature`, `how-acs-are-built`,
  `generate-product-truth`, `flow-render-pipeline`, `product-truth-architecture`,
  `author-product-truth`, `python-coder-internal`, `explore-flows-in-atlas`, …)
  must be rewritten into `decisions[]`, each fork given an authored `question`
  and an explicit happy-path outcome. This is hand work per fork, not a pure
  mechanical transform, because the question text and happy-path target are new.
- **Generator and validator updates.** `validate_product_truth.py` gains the new
  decision/outcome invariants and must reject `branches[]`; any generator or
  authoring tooling that emits or reads `branches[]` must be updated in lockstep,
  or the commit gate will fail every flow.
- **Renderer rework.** `buildFlowGraph`, the `FlowStepNodeData`/node-type wiring,
  and `flow-nodes.tsx` all change: a new `decision` node kind, a diamond
  renderer, edge labels, chain layout (column/row placement of the diamond
  chain), and the loss of the `variant: "branch"` card path. Existing
  screenshots/tests of the Flows view will need updating.
- **A schema-breaking change.** `flow.schema.json` sets
  `additionalProperties: false`, so the migration is atomic: the schema, the
  validator, every flow file, and the renderer must land together — a flow with
  `branches[]` fails the new schema, and a flow with `decisions[]` fails the old.
- **`acceptance_scenarios.for` re-pointing.** Any scenario whose `for` named a
  branch id must be repointed at the corresponding outcome id; preserving branch
  ids as outcome ids minimises but does not eliminate this.

### Neutral

- The upstream/downstream authority split from ADR-023 is unchanged: flows still
  generate ACs, `impl_status` is still derived from AC `work_status`, and the
  `.flow.json` remains the single source of truth. This ADR changes only how a
  *fork* is modelled and drawn.
- `steps[]` is untouched; the ordered spine and its fields are unchanged.

## Alternatives

### Alternative A — Derive decisions implicitly from `branches[]` at render time (no schema change)

Leave `branches[]` as-is and have `buildFlowGraph` group branches by shared
`from`, synthesize a diamond, and infer the happy path, all at render time.

**Rejected.** This keeps decisions second-class: there is still no place in the
data to author the fork's *question*, attach `human` copy, or review the decision
as a reviewed artifact — the whole point of the product-truth store per ADR-023.
It also puts all the semantics back in the renderer (the exact problem in
Context §3): the Atlas would have to infer what is a decision, guess the happy
path, and invent question text, and the validator could never check any of it.

### Alternative B — One N-way diamond per multi-branch step (no chaining)

Model the fork as a single decision but render it as one diamond with N outgoing
labelled edges fanning to each outcome.

**Rejected in favour of chaining.** A single N-way diamond becomes an unreadable
star of crossing edges as N grows, and it forces the reader to evaluate N
conditions "at once" rather than as a sequence of clear binary questions.
Chaining (diamond → diamond → happy path) reads as a natural decision sequence,
lays out cleanly in a column, and scales to arbitrary N. The schema shape is
identical either way (`decisions[].outcomes[]`); this is purely the rendering
contract, and chaining is the chosen one (Decision rule 3).

## References

- [ADR-023 — Product-Truth Store as the Flow-First Upstream Layer](ADR-023-product-truth-flow-first-upstream-layer.md) — establishes the flow schema, the derived-`impl_status` rule, and the Atlas as the read surface that this ADR extends.
- [ADR-022 — Mockups Are the Real App in Mock Mode](ADR-022-mockups-are-the-real-app-in-mock-mode.md) — the `screen` targets an outcome's `to.screen` / `screen` fields point at.
- [ADR-021 — plan-feature Product-Truth Phase](ADR-021-plan-feature-product-truth-phase.md) — the authoring phase where flows (and now their decisions) are created before ACs.
- `docs/product-truth/schemas/flow.schema.json` — the schema gaining `decisions[]` and losing `branches[]`.
- `docs/product-truth/scripts/validate_product_truth.py` — the commit-gate validator extended with the decision/outcome invariants.
- `leafcutter-web/lib/data/graph.ts` — `buildFlowGraph`, which gains the `decision` node kind, labelled edges, and chain layout.
- `leafcutter-web/components/flows/flow-nodes.tsx` — gains the diamond renderer and drops the `variant: "branch"` card path.
</content>
</invoke>
