---
title: "KI-ACS-013 — `delivers_to` and `expects_from` are the two ends of one edge keyed on different things, so the forward half is not traversable and nothing validates either"
description: "KI-ACS-013 — `delivers_to` and `expects_from` are the two ends of one edge keyed on different things, so the forward half is not traversable and nothing validates either"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - ac_store
related_docs:
  - docs/known-issues/ac-store.md
  - docs/known-issues/README.md
---

# KI-ACS-013 — `delivers_to` and `expects_from` are the two ends of one edge keyed on different things, so the forward half is not traversable and nothing validates either

> One known issue, split out of `docs/known-issues/ac-store.md` on
> 2026-09-14. Index: [ac-store.md](../ac-store.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-26 · **Last seen:** 2026-08-26
- **Where:** `config/ac_store_schema.json` (the `delivers_to` / `expects_from` declarations);
  `scripts/ac_store/validate_ac_schema.py`; `templates/scripts/commit_guardian/check_ac_schema.py`

**Symptom.** You cannot ask the store "what consumes this criterion?" and get an answer from
the criterion itself. You have to build a reverse index over every record in the store, which
is what had to be done to answer that question for a single record on 2026-08-25.

**Root cause — the two ends of the edge are keyed on different things.** Measured across all
3,376 records:

```
delivers_to entry shapes            expects_from entry shapes
  714  [agent, contract]              1651  [ac_id, contract]
   51  [ac_id, agent, contract]         46  [agent, contract]
   14  [ac_id, contract]               119  {}          <- empty dict
    3  [<bare AC id as the KEY>]         7  [<bare AC id as the KEY>]
```

`expects_from` is **AC-keyed**; `delivers_to` is **agent-keyed**. These are supposed to be the
reverse of each other. An agent name does not identify a record, so the forward direction
cannot be walked: `expects_from` gives you "which criterion produces what I need", and
`delivers_to` gives you a role name shared by hundreds of records.

**The store has already voted.** 65 `delivers_to` entries carry an `ac_id` key that no schema
documents and no validator reads — 51 alongside `agent`, 14 instead of it. Authors reached for
the missing field and added it themselves.

**Nothing validates either field.** `config/ac_store_schema.json` accepts
`null | string | object (additionalProperties: true) | array`. `validate_ac_schema.py` and
`check_ac_schema.py` contain **zero** occurrences of `delivers_to`. So:

- **29 `delivers_to.agent` values name no registered agent** (60 are registered). Crucially,
  most are **not errors** — `finalize-feature` (×6), `create-ticket` (×6),
  `diagram-classifier` (×5), `build-feature` (×2), `create-ac-workflow`, `ci`, `eval-runner`.
  These name a real consumer that simply is not an agent: a workflow, a CI job, a runner.
  One genuinely is malformed: `TKT-100g` carries
  `agent: "product-owner | business-analyst-v3"`, two names in one string.
- **119 `expects_from` entries are empty dicts** — a contract declaring nothing.
- **10 entries across both fields are shape-malformed**, with a bare AC id used as the dict
  *key* rather than as a value (`BP-006a-1`, `BP-006a-2`, `BP-006b-1`, `BP-006b-2`,
  `BP-006c-1`, `BP-006c-2`, `UXP-600` ×3).

**Why "restrict `agent` to the registry" is the wrong fix on its own.** It is the obvious
first idea and it would refuse 29 records, of which roughly two-thirds name a legitimate
non-agent consumer. That mistakes *not an agent* for *wrong*, and would push authors to name
a plausible agent instead of the true consumer — strictly worse information. The precedent
worth copying is `ADR-035`, which made the fast lane's producer roster **data** rather than
a hardcoded literal while keeping it closed; the equivalent here is a declared consumer
vocabulary that admits workflows and CI, not the agent registry alone.

**Fix direction.** Three separable pieces, most valuable first:

- **Document `ac_id` on `delivers_to` and make it the edge key**, mirroring `expects_from`.
  That is what makes the graph traversable in both directions, and 65 records already do it.
  `agent` stays as useful colour — which role will do the work — but stops being the identity.
- **Validate what is present.** An `ac_id` must resolve to a record in the store; an `agent`
  must resolve against a declared consumer vocabulary wider than
  `config/agent_registry.json`. Follow `ACS-100i-9`'s shape: one shared helper imported by
  both entry points, one format string, no second list in the JSON schema.
- **Refuse the malformed shapes** — the 10 bare-AC-id-as-key entries and the 119 empty
  `expects_from` dicts. These are unambiguous, and unlike the 29 they have no defensible
  reading.

**Scope note.** `assigned_agent` is getting exactly this treatment right now
(`ACS-100i-9..11`, registry validation via a shared `_ac_agents.py`; `ADR-035` for the
roster). `delivers_to.agent` and `expects_from.agent` were not in that scope and remain
unvalidated, so the store now has one producer field that is checked and two consumer fields
that are not.

**What it costs today.** Quiet, but not small, and the quietness is the problem.

Nothing here breaks a build. The only live readers are `pr-reviewer`'s Cross-File Contract
Tracing and `ac-validator` §2d, both LLMs told to open the consuming file named in the
contract, so a wrong or absent value degrades a review pass rather than failing a gate.

**Raised from `medium` to `high` on 2026-08-26.** The first assessment weighed the blast
radius of a single bad value, which is genuinely low. That was the wrong unit. Three things
together make this a `high`:

- **It silently disables two review checks across the whole store.** `ac-validator` treats a
  contract gap as a **blocker** and `pr-reviewer` as a **high-confidence finding**. Point
  either at a contract naming no openable consumer and it has two options — skip, or invent
  a consumer. The first makes the check a no-op that reads as performed; the second produces
  a fabricated finding against correct work. Both are the false-green shape this repo exists
  to prevent, sitting *inside* the machinery meant to catch it.
- **The traversal gap has a compounding cost.** Every question of the form "what depends on
  this?", "is this AC terminal?", "what breaks if I change this contract?" requires a
  full-store scan. That is not a one-off inconvenience: it is a tax on every future
  reasoning pass over the store, and it is why an authoring session in 2026-08-25 had to
  build a reverse index over 3,376 records to answer that question for one record.
- **The store is actively drifting away from the fix.** 64% of populated `delivers_to`
  entries name their own `assigned_agent`, and 65 records have already invented an
  undocumented `ac_id` key. Every week this stays open, more records are authored to a
  convention the schema does not describe, and the eventual correction gets larger. The
  sibling field `assigned_agent` is being validated right now (`ACS-100i-9..11`), so the gap
  between the checked producer field and the unchecked consumer fields is widening rather
  than closing.

The severity reflects the store-wide, compounding, self-concealing character of the defect —
not the cost of any one wrong value.

**Related.** `KI-ACS-012` (approved code leaves with no test contract — the same shape asked
of `test_spec`). `KI-ACD-015` (`expects_from` is invisible to the build sequencer, so
ordering must live in `depends_on` — a separate defect, and the reason neither of these
fields should be used to express ordering).

---
