---
title: "ADR-043: A Journey Known to Be Behind Carries a Durable `behind` Mark in the Record Itself"
description: "The behind verdict is written into the journey artifact as one optional top-level `behind` object, deleted outright when the journey becomes current, because a verdict that exists only in a check's console output is invisible to every reader who did not run the check."
type: "adr"
status: "active"
created: "2026-09-09"
last_updated: "2026-09-09"
deciders:
  - BrainCandy
components:
  - ux_prototyping
  - precommit_hooks
related_docs:
  - docs/acceptance-criteria/ux-prototyping/UXP-700-truthful-project-record/UXP-700c-2-ii.yaml
  - docs/acceptance-criteria/ux-prototyping/UXP-700-truthful-project-record/UXP-700c-2.yaml
  - docs/acceptance-criteria/ux-prototyping/UXP-700-truthful-project-record/UXP-700c-2-i.yaml
  - docs/acceptance-criteria/ux-prototyping/UXP-520-atlas-flow-explorer/UXP-591.yaml
  - docs/architecture/adrs/ADR-023-product-truth-flow-first-upstream-layer.md
  - docs/architecture/adrs/ADR-025-first-class-flow-decisions.md
  - docs/architecture/components/ux-prototyping.md
related_code:
  - docs/product-truth/schemas/flow.schema.json
  - docs/product-truth/scripts/validate_product_truth.py
  - docs/product-truth/scripts/generate_product_truth.py
  - scripts/commit_guardian/commit_guardian.json
---

# ADR-043: A Journey Known to Be Behind Carries a Durable `behind` Mark in the Record Itself

## Status

| Field | Value |
|---|---|
| Status | Proposed |
| Date | 2026-09-09 |
| Deciders | BrainCandy |
| Author | `adr-author`, recorded during the `UXP-700c-2-ii` durable-mark pass of 2026-09-09 |
| Supersedes | None |

## Context

The product-truth store's journeys live in
`docs/product-truth/flows/<product>/<name>.flow.json`, governed by
`docs/product-truth/schemas/flow.schema.json` and read by
`docs/product-truth/scripts/validate_product_truth.py` (the checker) and
`docs/product-truth/scripts/generate_product_truth.py` (the generator). The store's
authority over product intent is recorded in
[ADR-023](ADR-023-product-truth-flow-first-upstream-layer.md); the flow schema's
`additionalProperties: false` posture — every new key must be registered before it can
be written — is called out in
[ADR-025](ADR-025-first-class-flow-decisions.md).

[`UXP-700c-2`](../../acceptance-criteria/ux-prototyping/UXP-700-truthful-project-record/UXP-700c-2.yaml)
gives each journey a three-valued freshness verdict — **behind**, **current**, or
**never-confirmed** (the third value added by
[`UXP-700c-2-i`](../../acceptance-criteria/ux-prototyping/UXP-700-truthful-project-record/UXP-700c-2-i.yaml)).
[`UXP-700c-2-ii`](../../acceptance-criteria/ux-prototyping/UXP-700-truthful-project-record/UXP-700c-2-ii.yaml),
the AC this record serves, requires that a **behind** verdict be *durable*: written into
the journey artifact itself, so a reader can see it without re-running the check.

The cost of not deciding is concrete on two axes.

**First, the verdict is otherwise invisible.** The checker's result today is an exit code
plus one structured stdout line (`{"outcome", "examined", "unreadable"}`, printed by
`_print_outcome_contract`). Nearly every reader of the record — the Atlas, a reviewer
opening a flow file, an agent loading a journey to reason about it — never runs the
checker and never sees that line. A journey the checker knows to be stale therefore
looks identical to a sound one to everyone except the person who invoked the run.
`UXP-700c-2-ii`'s own `test_rationale` states this directly: "a verdict that exists only
in a check's console output is invisible to every reader who did not run the check, which
is nearly all of them."

**Second, two agents are about to spell the same field differently.** This AC's
`delivers_to` block hands the mark to a *different* component's agent —
`frontend-coder`, rendering it in the Atlas under
[`UXP-591`](../../acceptance-criteria/ux-prototyping/UXP-520-atlas-flow-explorer/UXP-591.yaml)
— in a *later* ticket. The producing `python-coder` will therefore choose the field's
name and shape weeks before the consuming reader exists to disagree. `architect-review`
flagged exactly this on ticket `23_TICKET-20260909-UXP-700c-2-ii.md`, naming two
candidate spellings (`behind: {against, since}` versus `confirmed_against` +
`behind_since`) and explicitly deferring the choice to this record so that the two sides
cannot land on different ones. A durable, on-disk, cross-component contract with no ADR
of record is what this decision closes.

There is a third pressure specific to this store. The generator is the store's
established **single writer** of artifact content: `write_flows` recomputes
`impl_status` / `impl_asof` / `impl_summary` and is the only thing that rewrites a flow
file, which is why the pre-commit entry `check-product-truth-generate` can run it with
`--check` and treat *any* would-be change as a hard commit failure. Letting the checker
write to a journey makes it a second writer of the same file. That is a real departure
from the store's convention and is decided explicitly below rather than absorbed
silently.

Finally, this mark must not be confused with the checker's **run-level** outcome
vocabulary (`checked-and-sound` / `nothing-examined` / `degraded` / `failed`, carried on
the stdout line). That vocabulary describes *one run of the checker*; this mark describes
*one journey's durable state* and outlives every run. The two are deliberately spelled
with no shared token.

This ADR originates from ticket
`EPIC-TruthfulProjectRecord/23_TICKET-20260909-UXP-700c-2-ii.md`.

## Decision

### 1. The mark MUST be a single optional top-level `behind` object on the journey artifact

`flow.schema.json` MUST register one new optional top-level property named exactly
`behind`, of `"type": "object"`. Its **presence** is the mark: a journey whose artifact
carries a `behind` key is behind; a journey whose artifact does not carry that key is
not.

The name `behind` MUST be used verbatim by the producing checker and by every consumer.
The mark MUST NOT be spelled `outcome`, `status`, `verdict`, `freshness`, or any token
already used by the checker's run-level outcome vocabulary or by the flow schema's
existing `status` / `readiness` / `realization` fields, because a reader who meets the
same word in two places will conflate a transient run result with the record's durable
per-journey state.

### 2. The mark's shape is fixed and closed

The `behind` object MUST set `"additionalProperties": false` and MUST require all three
of the following keys whenever it is present:

```json
"behind": {
  "confirmed_against": "<stable string identity of the confirmation this journey was last checked at>",
  "changed": ["<id of each described thing that has moved since that confirmation>"],
  "since": "YYYY-MM-DD"
}
```

- `confirmed_against` MUST be a non-empty string naming what the journey was last
  confirmed against, satisfying `UXP-700c-2-ii`'s "and what it was last confirmed
  against" clause. It MUST be copied verbatim from the journey's own confirmation
  record; the checker MUST NOT re-derive it.
- `changed` MUST be an array of strings, each naming one described thing (an AC id or a
  project file path) that has moved since that confirmation. It MUST be non-empty when
  the mark is present — a journey with nothing changed is not behind — and MUST be
  written in a deterministic (sorted) order so re-running the checker on an unchanged
  store produces byte-identical output.
- `since` MUST be an ISO-8601 `YYYY-MM-DD` date string, matching the store's existing
  `asof` date convention.

This shape is closed. Adding a fourth key is an architectural change and MUST be recorded
by amending this ADR.

### 3. `UXP-700c-2`'s confirmation record MUST expose one stable string identity

This decision binds the sibling ticket that produces the verdict. Whatever shape
`UXP-700c-2` chooses for the per-journey confirmation record, that record MUST expose a
single stable string that identifies the confirmation, and `behind.confirmed_against`
MUST be that string. If the confirmation record is a structured snapshot, it MUST carry
an explicit string field for this purpose; the checker MUST NOT flatten, hash, or
otherwise synthesise an identity at the point of writing the mark, because a synthesised
identity cannot be matched back to the confirmation it names.

### 4. A journey becoming current MUST have the key deleted, not nulled

When a check finds a journey current, the checker MUST remove the `behind` key entirely
from the artifact — `flow.pop("behind", None)` — before serialising.

It MUST NOT write `"behind": null`, `"behind": {}`, or `"behind": false`. A
present-but-empty key still satisfies `additionalProperties: false`, so nothing would
catch it, and it would read as a live mark to any consumer that tests for key presence
(§8 requires exactly that test). Absence is the only representation of "not behind".

### 5. A journey the check did not examine MUST be left byte-identical on disk

The checker MUST NOT write to a journey file it did not examine in that run. This binds
three cases:

1. a journey outside the run's scope,
2. a journey skipped as unreadable by `load_flows` (the fail-open path that appends to
   `unreadable_flows`),
3. a journey whose serialised text is unchanged — the checker MUST compare the newly
   serialised text against the file's current text and MUST write only when they differ,
   mirroring `write_flows`'s existing write-only-on-change behaviour.

Neither writing nor removing the mark is permitted for these journeys, including the
removal of §4: a journey that was not examined MUST keep whatever mark it already
carries, because the checker learned nothing about it this run.

### 6. A never-confirmed journey MUST NOT carry the mark

A journey with no confirmation record is **never-confirmed**, which
[`UXP-700c-2-i`](../../acceptance-criteria/ux-prototyping/UXP-700-truthful-project-record/UXP-700c-2-i.yaml)
establishes as a third value precisely because it is neither current nor behind. The
checker MUST NOT write a `behind` mark for such a journey and MUST NOT remove one under
§4 either (there is nothing it can be behind).

On the day this ships every journey in the store is never-confirmed, so the first run
MUST write zero marks and MUST leave every journey file byte-identical. A run that marks
all journeys behind on day one is a defect of this rule, not an acceptable migration.

### 7. Re-marking MUST overwrite in place, and `since` MUST be preserved while the confirmation holds

A journey already marked behind and found behind again MUST have its single `behind`
object overwritten with the current values. The checker MUST NOT append a second mark,
MUST NOT turn the field into a list, and MUST NOT error on an existing mark.

`since` MUST be preserved from the stored mark while `confirmed_against` is unchanged,
and MUST be re-stamped with the run date when `confirmed_against` changes. This mirrors
`write_flows`'s existing `impl_asof` preservation rule, and it makes `since` mean "behind
since" rather than "last rewritten" — a value that moved on every run would carry no
information and would churn the file on every check.

### 8. The Atlas and every other consumer MUST read the field, and MUST NOT re-run the checker

Consumers of this mark — starting with the Atlas rendering deferred to `frontend-coder`
under [`UXP-591`](../../acceptance-criteria/ux-prototyping/UXP-520-atlas-flow-explorer/UXP-591.yaml)
— MUST determine a journey's behind state by testing for the presence of the `behind`
key on the loaded artifact. They MUST NOT shell out to `validate_product_truth.py`, and
MUST NOT infer the state from the checker's stdout line, which is a *run* result and is
not available to a reader of a checked-in file.

Consumers MUST treat the mark as derived data: it MUST NOT be hand-edited, and a consumer
MUST NOT write it back.

### 9. The checker becomes a second writer of journey files, under a fenced side effect

`validate_product_truth.py` MUST write journey files, departing from the store's
single-writer convention. The departure is fenced by these constraints, all of which are
binding:

- The checker MUST write **only** the `behind` key. It MUST NOT add, remove, reorder, or
  recompute any other field, and in particular MUST NOT touch `impl_status`,
  `impl_asof`, or `impl_summary`, which remain the generator's exclusively.
- The checker MUST serialise with exactly
  `json.dumps(flow, indent=2, ensure_ascii=False) + "\n"` — byte-for-byte the
  serialisation `generate_product_truth.write_flows` uses — so a checker write can never
  make `generate_product_truth.py --check` report spurious drift.
- A write failure (`OSError`) MUST be reported as a `WARNING` on the prose channel
  (stderr) and MUST NOT change the process exit code. The checker fails open on its own
  write, per the store's standing fail-open convention: a record it could not stamp is
  not a reason to block the work that triggered the check.
- The checker MUST NOT stage, `git add`, or commit the files it writes. The pre-commit
  entry `check-product-truth-validate` invokes it, and a hook that stages files behind
  the committer's back is out of scope for this decision.

### 10. The write/remove helper MUST live beside the verdict computation

The helper that writes and removes the mark MUST live in
`docs/product-truth/scripts/validate_product_truth.py`, in the same module as
`UXP-700c-2`'s verdict computation, following the module's existing `_check_*` / helper
naming. A parallel script MUST NOT be created, so that the reachability test for this
behaviour drives the same already-shipped CLI entry point (`main()`, guarded by
`if __name__ == "__main__":`) that every sibling ticket in this epic uses.

## Consequences

### Positive

- Every reader of the record — the Atlas, a reviewer with the file open, an agent loading
  a journey — sees the behind state without running anything, which is the entire point
  of `UXP-700c-2-ii`.
- The field name and shape are fixed before either side is written, so `python-coder`
  (producer) and the later `frontend-coder` (consumer) cannot land on different
  spellings. That is the specific failure `architect-review` deferred to this record.
- Delete-don't-null (§4) means "not behind" has exactly one representation, so a consumer
  that tests key presence — the test §8 mandates — is correct by construction and cannot
  be fooled by a stale empty object.
- `changed[]` localises the staleness: a reader learns *which* described thing moved, not
  merely that something did, turning an alarm into an actionable next step.
- Byte-identical serialisation (§9) plus write-only-on-change (§5.3) means the checker's
  new write cannot trip `check-product-truth-generate --check`, so no existing pre-commit
  entry needs to change.
- Preserving `since` (§7) keeps repeated checks of an unchanged store from rewriting
  files, so `git status` stays quiet on a no-op run.

### Negative

- The store now has two writers of journey files, and the single-writer property that
  made `generate_product_truth.py --check` a trustworthy drift gate is weakened. §9's
  fence ("only the `behind` key, only that serialisation") is a rule that must be actively
  defended by review; nothing in the runtime enforces it.
- Running the checker mutates the working tree. Anyone who assumed a validator is
  read-only — including the pre-commit path — will see files change under them. The
  ticket declares this (`declares_side_effect: true`), but the surprise is real and
  permanent.
- The mark can go stale in the opposite direction: a journey that was marked behind and
  is then excluded from a later run keeps its mark (§5), so a reader can see a mark that
  the most recent run did not re-confirm. This is the deliberate trade for §5's
  "unexamined means untouched" guarantee, and it is why `since` names a date the reader
  can weigh.
- `behind.confirmed_against` imposes a shape constraint (§3) on a sibling ticket that has
  not yet been designed. If `UXP-700c-2` chooses a confirmation record with no stable
  string identity, that ticket must amend this ADR rather than quietly widen the field's
  type.
- The schema's closed `behind` object means any future addition (a severity, a link to
  the run that wrote it) requires amending this record and migrating existing marks,
  rather than an additive write.

### Operational

- `unit_tests/product_truth/test_uxp_700c_2_ii.py` pins this contract. Its `real_artifact`
  test MUST re-read the journey from disk in a separate process (not inspect an in-memory
  result), its `criterion` test MUST assert the key is genuinely **absent** after the
  journey becomes current, its `boundary` test MUST assert an unexamined journey's file
  is byte-identical, and its `reachability` test MUST invoke `main()` as a subprocess
  through the shipped CLI per §10.
- The first run against this repository writes zero marks (§6), because every journey is
  never-confirmed until `UXP-700c-2` lands a confirmation record. A green first run is the
  expected result and is not evidence the write path works — only the test suite is.
- `check-product-truth-validate` in `scripts/commit_guardian/commit_guardian.json` is
  **not** modified by this decision. It will begin mutating unstaged journey files as a
  side effect of the hook; operators who see modified flow files after a blocked commit
  should re-stage them rather than reverting.
- The mark is derived data and MUST NOT be hand-edited. A hand-written `behind` block
  survives schema validation and will be silently overwritten or deleted by the next run
  that examines the journey.

## Alternatives

- **`confirmed_against` + `behind_since` as two flat top-level fields.** Rejected. The
  two fields would have to be kept in sync by convention alone: `additionalProperties:
  false` cannot express "if `behind_since` is present then `confirmed_against` must be",
  so a partial write or a hand-edit that drops one leaves a journey that is half-marked,
  and every consumer would need its own two-field presence test. Nesting both inside one
  `behind` object makes the pair atomic — one key appears and disappears together — which
  is what §4's delete-don't-null rule needs to be checkable at all.

- **Set `"behind": null` (or `{}`) when the journey becomes current.** Rejected. A
  present-but-null key satisfies `additionalProperties: false`, so no schema check would
  ever flag it, and it reads as a live mark to the presence test §8 requires of every
  consumer. It would also churn the file on every run for journeys that have never been
  behind, defeating §5.3's write-only-on-change guarantee.

- **Reuse the checker's run-level outcome vocabulary (`degraded`, `failed`, …) for the
  per-journey mark.** Rejected. Those values describe one execution of the checker and are
  meaningless on a checked-in artifact — `nothing-examined` on a journey record has no
  referent. Spelling the two alike guarantees a future reader conflates a transient run
  result with the record's durable state, which is the specific confusion
  `architect-review` directed this record to prevent.

- **Reuse the existing `impl_summary.asof` / `impl_asof` fields as the freshness stamp.**
  Rejected, and rejected explicitly by `UXP-700c-2`'s own notes. Those fields record when
  the *derived* data was regenerated, and the generator rewrites them on every run, so
  every journey would be permanently current and the check could never report anything.

- **Keep the verdict on the checker's stdout line only, and let the Atlas re-run the
  checker.** Rejected. It fails the AC's durability clause literally ("readable without
  running the checker"), and it puts a subprocess invocation of a Python CLI on the
  Atlas's render path — a browser-facing surface that cannot spawn it at all. Every
  non-executing reader of the record (reviewer, agent, diff) would still see nothing.

- **Write the marks to a sidecar file (e.g. `docs/product-truth/freshness.json`) instead
  of into the journeys.** Rejected. The sidecar and the journeys drift independently:
  renaming or deleting a journey leaves an orphan entry that still reports behind, and a
  journey copied into another store arrives with no mark at all. It also reintroduces the
  staleness hazard already rejected in the checker's outcome-channel decision — a sidecar
  left over from a crashed run is indistinguishable from a fresh one — and the AC asks for
  the mark "in the record itself", not beside it.

- **Have `generate_product_truth.py` write the mark, preserving the single-writer
  convention.** Rejected. The freshness verdict is computed by the checker
  (`UXP-700c-2`), so the generator would have to either re-implement the comparison in a
  second place — where the two copies can disagree after any change — or import the
  checker and run it, which makes the generator's `--check` mode (contractually a no-write
  dry run) transitively depend on the checker's write path. It would also mean a journey
  only gets marked when someone happens to run the generator, decoupling the mark from
  the check that produced it, which contradicts the AC's "when that check completes".

- **Append each behind verdict to a `provenance`-style history array on the journey.**
  Rejected. The artifact would grow without bound on every run, and §4's removal clause
  has no meaning against an append-only log — "a later check that finds the journey
  current removes the mark" would become "adds a cancelling entry", which every consumer
  would then have to fold to answer the one question they actually ask. The current state
  is the contract; the history is not asked for by any AC.

- **Make the mark a boolean (`"behind": true`).** Rejected. It cannot carry "what it was
  last confirmed against", which is an explicit clause of the AC, and it cannot name the
  changed things, so a reader learns that something is wrong but nothing about what. It
  also reintroduces the null-versus-absent ambiguity the moment someone writes
  `"behind": false`.

## References

- Originating ticket: `EPIC-TruthfulProjectRecord/23_TICKET-20260909-UXP-700c-2-ii.md`
  (AC `UXP-700c-2-ii`).
- Producing sibling: `EPIC-TruthfulProjectRecord/21_TICKET-20260909-UXP-700c-2.md`
  (AC `UXP-700c-2`, the behind/current/never-confirmed verdict this mark makes durable),
  extended by `UXP-700c-2-i` (the never-confirmed value).
- Consuming surface: [`UXP-591`](../../acceptance-criteria/ux-prototyping/UXP-520-atlas-flow-explorer/UXP-591.yaml)
  — the Atlas rendering of the mark, deliberately deferred to a later `frontend-coder`
  ticket per `UXP-700c-2-ii`'s `delivers_to` contract.
- [ADR-023 — Product-Truth Flow-First Upstream Layer](ADR-023-product-truth-flow-first-upstream-layer.md)
  — the store's authority and its never-hand-edited derived-data convention.
- [ADR-025 — First-Class Flow Decisions](ADR-025-first-class-flow-decisions.md)
  — the prior schema change to `flow.schema.json` and its `additionalProperties: false`
  posture.
- Governed code: `docs/product-truth/schemas/flow.schema.json` (the `behind` property),
  `docs/product-truth/scripts/validate_product_truth.py` (the write/remove helper and
  `main`), `docs/product-truth/scripts/generate_product_truth.py` (`load_flows`,
  `write_flows` — the serialisation §9 requires the checker to match).
- Pinned by `unit_tests/product_truth/test_uxp_700c_2_ii.py`.
