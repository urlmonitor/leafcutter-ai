---
title: "Documentation is demanded of records that own no document"
date: "2026-08-31"
time: 1750
type: manual
components: 
  - build_orchestration
  - ac_driven_dev
  - documentation_system
summary: "Six L3s specifying that a documentation demand follows ownership rather than the classification of the code change, four amendments to the approved siblings they narrow, and an explanation doc tracing the mechanism end to end. Measured cause of an epic halt: 25 of 25 tickets carried a documentation demand and 1 of 25 owned the document it was told to produce."
description: "Three steps decide documentation and none consults the others. Whether documentation-expert runs is decided from change_target and risk_surface via documentation_gates, which never looks at whether the record has a document. Which document is decided separately by _extract_doc_path, returning the first doc_links entry with a slash and ignoring relationship and status. documentation-verifier then demands that document appear in that ticket's own diff and fails closed. On EPIC-StartingNewWorkTheProperWayAlways the result was 25 of 25 tickets carrying a demand against 1 of 25 owning its target, with 22 pointing at a single page a 23rd creates; the drive halted there. Reordering cannot resolve it because the authoring record depends on the behaviour those tickets deliver, closing a cycle. The root cause is that doc_links is authored as context and consumed as contract: it-po section 2.6 instructs relationship describes for architecture documentation and offers no field for a document the record produces, so the 24 describes entries are the template being followed correctly. Ownership is specified as creates or modifies only, deliberately not the wider edit-surface set used for files_touched, because 169 records link ac-schema.md as specifies and the wide set would tell all 169 to write it."
breaking: false
---

## Entry

Three mechanisms decide whether a ticket must produce documentation, and none of them
consults the others.

**Whether** `documentation-expert` runs is decided entirely from the AC's `change_target`
and `risk_surface`, through the `documentation_gates` policy. It never looks at whether the
record has a document of its own.

**Which** document is decided separately, by `_extract_doc_path` — the *first* `doc_links`
entry whose path contains a slash, ignoring `relationship` and ignoring `status`. When
`doc_links` is empty it invents a path.

**Enforcement** then demands that document appear in *that ticket's* git diff, fail-closed.

Measured on `EPIC-StartingNewWorkTheProperWayAlways`:

| | |
|---|---|
| tickets carrying a documentation demand | 25 of 25 |
| tickets that own the document they must produce | 1 of 25 |

Twenty-two pointed at the same reference page — one that a twenty-third ticket creates. The
drive halted there, three tickets blocked at `documentation-verifier` and the other
twenty-two headed for the same wall.

Reordering does not resolve it. The record that authors the page documents behaviour those
tickets deliver, so it legitimately depends on them; adding the reverse edge closes a cycle
(`a-1 → d-4 → a-5 → a-1`, all three edges present in the store).

### Why this is a specification change rather than a bug fix

`doc_links` is **authored as context and consumed as contract**.

`it-po.md` §2.6 tells the enriching agent to record "architecture docs, component docs, and
ADRs that describe the relevant component", to use `relationship: describes`, and to mark a
not-yet-existing doc `status: planned`. It offers **no field at all** for a document the
record produces. The generator then reads the first such entry as the deliverable.

So the twenty-four `describes` entries are not careless authoring — they are the template
being followed correctly. A generator-only fix would not hold, because the next record
authored would reintroduce the same shape.

### What is specified

Six L3 records under `BO-2200c-5`: the target is the doc_link the record **owns** rather
than the first it mentions; owning a source file is not owning a document; a record owning
no document is never *dispatched* a demand, which is phase selection and not merely
rendering; the writer reads its target before writing and reports which of three things it
did; writer and verifier agree what "satisfied" means so an already-correct document passes
without a diff; and a doc_link's `status` never changes what is demanded.

Ownership is `{creates, modifies}` **only** — deliberately not the wider edit-surface set
already used for `files_touched`. That set includes `specifies`, and **169 records** link
`docs/reference/ac-schema.md` as `specifies`, meaning the wide set would instruct all 169 to
write it: the same collision an order of magnitude larger. Doc ownership is a strict subset
of edit-surface membership, so a doc target is never absent from `files_touched`.

The idempotency criterion cannot ship alone. The verifier satisfies a document only when its
path appears in the diff, so a writer that correctly changes nothing would be blocked on
every already-documented target; the matching verifier criterion travels with it.

### Amendments, and one that survives but stops discriminating

Three approved siblings assert their trigger absolutely and are narrowed to
necessary-but-no-longer-sufficient. A fourth is checked and explicitly **not** narrowed —
every assertion in it is negative, and ownership gating only ever removes demands.

That fourth record acquires a subtler problem worth naming, because nothing would go red
when it bites: once ownership gates the demand, a fixture owning no document produces no
`documentation-expert` whatever its classification, so its two negative tests would pass
without exercising the classification rule at all — satisfied by the ownership gate alone
and blind to a regression that over-triggers on an internal refactor. Its `test_spec`
descriptors now carry the fixture constraint and a required control: flip only the
classification on an owning fixture and assert the demand reappears.

Placement was the point. The same warning already existed in that record's `amended_by`, but
`test-writer` does not read `amended_by` — it works from the ticket's Test Requirements,
derived from `test_spec`. Guidance the agent cannot see does not help it.

### Sequencing

Only about **18 of 3,701** records carry `relationship: creates` today. Landing the ownership
rule before the store is backfilled would turn documentation demands from near-universal to
near-zero. The order is: `doc_links` schema validation and a `relationship` enum in the AC
store — there is currently no `doc_links` validation of any kind, no shape check and no enum
for either field — then the backfill, then the rule.

The companion gap check, that every `planned` cross-link target is `created` by some record,
is a whole-store invariant and belongs in the schema validator rather than a commit hook:
the AC hooks only ever see the staged index.
