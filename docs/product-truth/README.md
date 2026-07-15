# Product-Truth Store

> The **baseline business information** every product rests on — the things that
> exist (Mock Data), the journeys people take (Flows), and the screens they see
> (Mockups). Agents read the JSON; personas review the picture; they are the same
> artifact.

This store is the future-state layer from the flow-site vision, made real. It sits
**beside** the acceptance-criteria store (`docs/acceptance-criteria/`) and feeds the
existing agents — it does not replace anything. Each artifact hangs off the ACs it
serves, and moves through the same `readiness` lifecycle (`draft → reviewed →
approved`) reviewed by a **persona** (for now, the Product Owner).

The artifacts in here today were **walked by hand** (dogfooded) so they are the *gold
reference* — "where we want to be when done." The mock/flow/mockup agents that come
later must produce artifacts that match these in shape and quality, and must **extend
these** rather than duplicate them.

---

## Layout

```
docs/product-truth/
  README.md                     this file
  index.json                    the SEARCHABLE manifest (see "Search" below)
  schemas/
    flow.schema.json            shape of a Flow artifact
    mock-data.schema.json       shape of a Mock Data artifact
    classifier-eval.schema.json shape of one classifier eval row
  classifier/
    eval.jsonl                  labelled examples: request → which artifacts are needed
  flows/<product>/<name>.flow.json    machine-readable flow (source of truth)
  flows/<product>/<name>.md           human-readable rendering (GENERATED — do not edit)
  mock-data/<product>/<name>.mock.json
  mockups/<product>/…           (HTML; the flow-site is the current renderer)
  scripts/
    validate_product_truth.py   schema + cross-ref + impl-rollup + eval validator
```

## Linkage: graphs ↔ mocks ↔ ACs (how everything cross-references)

The whole point is one connected web, keyed on stable ids:

- **Flow step → ACs** — each step/branch carries `implements: [<AC ids>]` (authored by
  the business-analyst from that step's `acceptance_scenarios`). This is the link a
  visualizer follows to show a step's live status.
- **Flow step → implementation status** — `impl_status` (`not_started | in_progress |
  done`) is **DERIVED** from the `work_status` of every AC in `implements` (which itself
  bottoms out on ticket `status: done`). Never hand-edit it — the validator/generator
  recomputes it and flags drift. `impl_summary` rolls it up for the whole flow.
- **Flow → Mock Data** — `mock_data_ref` points at the one canonical dataset; each
  step's `reads`/`writes` name the entities it touches.
- **Mock Data → entities** — the `entity_registry` in `index.json` is the shared
  vocabulary; every entity name must be a member (a typo becomes a hard failure, not a
  duplicate dataset).

So: click an AC → find the step(s) whose `implements` contains it → see the flow + the
mock records those steps read/write. Click a step → see its ACs' live status + its data.

## Reading a flow (for humans)

Open `flows/<product>/<name>.md` — a plain-language rendering generated from the JSON
(flow `summary`, each step's `human` line, the "what if" branches, and the acceptance
checks). **Never edit the `.md`** — edit the `.flow.json` and regenerate. The JSON stays
the single source of truth; the `.md` and the flow-site are two read-only views of it.

`status` (is the journey live vs. retired: `active | deprecated`) is a different axis
from `readiness` (has a persona reviewed it: `draft → reviewed → approved`).

## Validation

`python scripts/validate_product_truth.py` checks schema conformance, that `index.json`
mirrors each artifact, entity-registry membership, step/branch id uniqueness +
`acceptance_scenarios.for` resolution, `impl_summary` correctness, mock-data invariants,
and classifier `outcome` consistency. Unresolved `implements` AC ids are warnings (seed
flows may reference not-yet-authored ACs). Wire it into the commit gates alongside
`ac-fulfillment-gate`.

Artifact ids are path-stable: `<product>/<name>` (e.g. `fern-and-fig/catalog`). The id
never changes when an artifact is extended — only its `version` and contents grow.

---

## Search — how an agent finds what already exists

**Before drafting anything, the mock or flow agent MUST search `index.json`.** The
index is keyed on the dimensions an agent actually reasons about:

| Dimension | Question it answers | Field |
|-----------|--------------------|-------|
| **component** | "Is there already product-truth for this component (e.g. `ux-prototyping`)?" | `by_component` |
| **entity** | "Do we already have a canonical dataset for `Plant` / `Customer` / `Order`?" | `by_entity` |
| **flow** | "Is there already a journey this step belongs to?" | `by_flow` |
| **type** | "Show me every `mock_data` / `flow` / `mockup`." | `artifacts[].type` |
| **tag** | free-text grouping (`checkout`, `catalog`, …) | `artifacts[].tags` |

`artifacts[]` is the authoritative list; `by_component` / `by_entity` / `by_flow` are
derived indexes for fast lookup. Keep them consistent when you edit.

---

## The add-vs-create decision (MANDATORY for mock & flow agents)

```
1. Classifier says the request needs a Flow / Mock Data / Mockup, and gives
   its component + entities (see classifier/eval.jsonl).
2. Search index.json by component AND entities (and flow, for a flow step).
3. If a matching artifact exists:
       → EXTEND it in place. Add the new records / fields / steps / branches,
         bump `version`, append to `provenance`. Keep the id.
   Else:
       → CREATE a new artifact, then register it in artifacts[] and every
         derived index it belongs to.
4. NEVER create a second mock-data artifact for an entity that a component
   already has. There is ONE canonical dataset per entity per component; it
   grows. Duplicating it is the synthetic-fixture bug this store exists to kill.
```

The same rule applies to flows: a new screen that belongs to an existing journey is a
**step added to that flow**, not a new flow.

---

## Who consumes these

- **`/plan-feature`** is the **orchestrator** of the product-truth authoring set.
  On every invocation it runs an always-on product-truth phase (between `ac-triage`
  and the AC pipeline) that dispatches `pt-classifier`, then — filtered to the
  classifier's outcome — the `mock-data-author`, `mockup-author`, and `flow-author`
  agents (fixed order, each behind an approve/edit/cancel gate and a surgical
  commit), hands the approved flow to the `business-analyst`, and reconciles the
  reported back-links via `scripts/apply_flow_backlinks.py`. When this store is
  absent the phase self-skips non-silently and AC authoring still proceeds. See
  ADR-021 and `templates/skills/plan-feature/SKILL.md`.
- **`business-analyst`** derives L2/L3 Gherkin ACs from a Flow's steps + branches
  (each branch → a scenario). See `acceptance_scenarios` on the flow.
- **`test-writer`** builds fixtures from a Mock Data artifact's `records` — the tests
  run against the exact data the PO reviewed.
- **`frontend-coder`** builds each screen to match the Mockup, populated from the same
  Mock Data.
- **`user-surface-smoker`** asserts the built screen matches the approved Mockup.
- **`ac-triage` / classifier** decides *which* of the three a request needs — the
  `classifier/eval.jsonl` set is its gold eval.

---

## Status of the seeds (2026-07-10)

| Artifact | Type | Status | Reviewed by |
|----------|------|--------|-------------|
| `fern-and-fig/customer-buys-a-plant` | flow | approved | product-owner (persona) |
| `fern-and-fig/catalog` | mock_data | approved | product-owner (persona) |
| `classifier/eval` | eval set | seed | — |

These are hand-walked. When the agents are built, they must reproduce artifacts of at
least this shape and quality, and extend these rather than start over.
