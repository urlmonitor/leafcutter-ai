---
title: "Five records disagree with the declares_side_effect derivation, and only three of them are wrong"
description: "Per-record adjudication of every authored/derived declares_side_effect disagreement in the store, the test that separates a genuine durable effect from a reporter/refuser, and the two deriver defects that produce the remaining two."
type: explanation
status: active
created: 2026-09-21
last_updated: 2026-09-21
components:
  - ac_store
  - build_orchestration
  - commit_guardian
---

# Five records disagree with the declares_side_effect derivation

`check-ac-schema` refuses any AC whose authored `declares_side_effect` disagrees
with the value derived from its own Then clause. Five records in the store carry
such a disagreement. All five are pinned in
`_KNOWN_PRE_EXISTING_DISAGREEMENTS` (`unit_tests/ac_store/test_bo_2900g_2_ii_store.py:81-87`)
so the store-wide staleness test stays green while they remain unresolved.

They were adjudicated on 2026-09-21, one record at a time. **Three are wrong and
should be flipped. Two are right, and the derivation is what is wrong.** The
allowlist should shrink from five entries to two, not to zero.

| Record | Authored | Derived | Verdict |
|---|---|---|---|
| `BO-2900g-1` | true | false | **flip to `false`** |
| `BO-2900g-4` | true | false | **flip to `false`** |
| `BO-2900g-2-i` | true | false | **flip to `false`** |
| `BO-2400g-4` | true | false | **keep `true`**, stay pinned |
| `BO-2400g-4-i` | true | false | **keep `true`**, stay pinned |

## Why this field matters, and how little it does

`declares_side_effect` has exactly one live consumer. Read off the record at
`_gtfa_cli.py:145`, it routes `user-surface-smoker` into the generated ticket's
agents map (`_gtfa_agents_inputs.py:270-271`) and makes that routing
non-overridable (`_gtfa_agents_map.py:78`, `:353-355`). It is then copied into
ticket frontmatter (`_gtfa_frontmatter.py:247-249`), where nothing reads it —
the drive dispatches from the `agents:` map, not the flag.

Nothing on the fast-lane path consumes it at all: `fast-lane-ship.js` has a
fixed phase roster (`:42-51`) with no conditional selection, and neither
`declares_side_effect` nor `user-surface-smoker` appears anywhere in
`scripts/build_orchestration/`.

Flipping the flag changes exactly three lines of a generated ticket: the
agents-map entry, the frontmatter field, and one `## Sign-offs` checkbox.

## The test that decides it

The obvious reading — "is the Then clause phrased as an absence?" — is the wrong
test, and applying it produces two false verdicts.

The test the two cited precedents were actually reconciled on is written down in
the allowlist itself:

- `BP-1100g-5-i` — *"every Then clause in it reports a shortfall and **writes
  nothing**"* (`test_bo_2900g_2_ii_store.py:62-64`)
- `BP-1100g-4-i` — *"every Then clause is a reporter/refuser … **with no durable
  object whose being written outlives the run**"* (`:72-77`)

So the operative question is:

> **Can a process that performs no durable write satisfy this clause?**

If yes, the clause is a reporter/refuser and `false` is honest. If no, the
clause asserts a durable effect however it is phrased.

There is also a lexical tell that tracks the same split, and it sits in
BA-authored criteria rather than in enrichment prose: the reporter/refuser
precedents say *reported*; `BO-2400g-4` says *left **recorded** as being worked
on*.

## The three that should flip

All three assert the **content of a produced structure**. Each is satisfiable by
a process that writes nothing.

**`BO-2900g-1`** — *"each plan contains a request for a proof … and work Y's
three authored proofs are all still present, unaltered and in their authored
order."* Asserts what a test plan contains. The generator does write a ticket
file, but the clause never asserts that write; the file is transport, not the
thing asserted. The record's own boundary confirms the narrowness: *"Planning-time
only … produces no gate, block or done-state consequence."*

**`BO-2900g-4`** — *"every proof each plan requests uses a kind the definition
permits … the two plans read the same way against the definition."* Vocabulary
conformance of a description. The record states its own boundary explicitly:
*"No gate, no block, no done-state consequence."*

**`BO-2900g-2-i`** — *"that new record **carries** the declaration."* This is the
exact shape for which its own parent `BO-2900g-2` was resolved to `false` in
`9699d501`, with the reason recorded as *"its Then clause states what a record
CARRIES … The declaration follows what the Then clause states, not what the
implementation incidentally writes."* Its sibling `BO-2900g-2-ii` is already
`false`; `-2-i` is the last `true` left in its own family.

### How the wrong value got there

All three were enriched in the same automated pass (`by: it-po`,
`at: 2026-08-17`), each `amended_by` noting it added `declares_side_effect` with
*"criteria untouched"* — i.e. the flag was attached to criteria that were never
re-read against it. `BO-2900g-1` is the one that states a reason:
*"declares_side_effect is true because the observable is a ticket file written to
disk by the CLI."* That is a considered judgement made on the basis the house
rule rejects — reasoning from the implementation rather than the Then clause.
Note the deriver reads only `criteria`, so that justification, living in `notes`,
is invisible to the gate by construction.

Twelve records have previously hit this disagreement. All twelve were resolved by
flipping the flag; none by rewording criteria.

## The two that should stay

These are **derivation false negatives**: the criteria are right and the tool is
wrong. Flipping either would record a statement both analyses judged
substantively false, in order to quiet a gate — the field-level form of the
"reword until the regex stops objecting" move that `9699d501` explicitly
condemned.

### `BO-2400g-4` — a halt that must release its claims

Clause 3: *"when the run is stopped this way there is no commit and no pull
request for it, **and none of its requirements is left recorded as being worked
on**."*

Surface grammar is an absence. It is not satisfiable by inaction, and the proof
is the fast lane's own phase ordering:

- `claim_build_set` writes `work_status: in_progress` into the AC YAML on disk
  (`_fl_lifecycle.py:337` → `_update_ac_work_status` → `_atomic_write_text`).
- That claim executes at `fast-lane-ship.js:982`.
- The Review phase that can stop the run executes at `:1309`, and Commit at
  `:1529`.

By the time a review stop happens, the store on disk already says
`in_progress`. Doing nothing leaves it there — exactly what clause 3 forbids.
Satisfying the clause requires `release_claim`'s second on-disk write
(`_fl_lifecycle.py:395`). The record's own notes name the stake: *"stopping
without releasing the claim leaves the requirements permanently unbuildable."*

Both cited precedents are satisfiable by a pure function returning a verdict.
This one is not. That is the material difference.

On "restoration is not a new artifact": the schema's contrast class is *write*
versus *return*, not net-new versus restored. And the diff is not zero anyway —
`BO-2400f-10` requires the release *"is landed on mainline."*

### `BO-2400g-4-i` — findings must reach the pull request

Clause 1: *"all three findings are visible on the pull request itself, **so a
person who never saw the run can read them**."*

A submitted PR body is a record persisted on a user-facing surface outside the
process — squarely inside the schema's definition — and durability is not
incidental here, it *is* the requirement. The record says so: *"a finding that a
person never sees is indistinguishable from a finding that was never made."*

This is the exact inverse of `BO-2900g-1`: there the Then asserted a structure's
contents and the write was incidental; here the Then asserts persistence and
external readability as the requirement.

### Why the authored `true` is credible on these two

The same 2026-08-17 pass that set `true` blindly on the `BO-2900g` records set
the flag **discriminatingly** across the `BO-2400g` family:

| `BO-2400g-` | 1 | 1-i | 2 | 2-i | 3 | **4** | **4-i** |
|---|---|---|---|---|---|---|---|
| `declares_side_effect` | false | false | false | false | false | **true** | **true** |

Five `false`, two `true`, in one pass, each `true` carrying a clause-level
written reason — `BO-2400g-4`'s names the contrast outright: *"TRUE for this AC
and not for its g-2/g-3 siblings."* The split does not track `assigned_agent`
(`-2`, `-2-i`, `-3` are also `llm-expert` and got `false`). That is judgement,
not a default.

## Two deriver defects produce these false negatives

**Vocabulary register.** `_DURABLE_EFFECT_RE`
(`_ac_schema_validators.py:616-632`) already contains `updates? the
(?:database|store)` — the vocabulary has a phrase for `BO-2400g-4`'s effect. The
author wrote the outcome (*"none … is left recorded"*) rather than the mechanism
(*"the store is updated"*). Nothing covers *"visible on the pull request"* at
all. This is the register mismatch of `KI-BP-20260908-1140`: the BA writes
customer language, the deriver matches engineering language.

**Negation blindness.** `KI-CG-014` records that the deriver cannot parse
negation. The consequence cuts both ways: it could derive `true` for an AC whose
point is that nothing is written, and it cannot distinguish an absence-phrased
clause that *requires* a write from one that forbids one. On `BO-2400g-4` the
derived `false` is therefore low-evidence in either direction — the deriver did
not adjudicate clause 3, it pattern-matched around it.

Any widening should follow the discipline of `9699d501`, which narrowed this
same pattern by **measuring** the marked-set delta first (139 → 88, 51 flipped,
zero newly marked) and rejecting a blunter variant that dropped genuine
positives.

## The gate these records route is currently empty

Independent of the flag question: `user-surface-smoker` reads a `## Smoke
Fixture` block and a `user_facing_surface` field. **The generator emits
neither** — `grep -rn "Smoke Fixture" scripts/` returns nothing, and no
AC-generated ticket has ever carried one. So routing the smoker today produces a
checkbox, not a check. Filed as `KI-ACD-022` (open, high); fix direction #1
("never emit a conditional agent without its condition") is unimplemented.

The two pinned records are blocked on *different* things, and the difference is
actionable:

- **`BO-2400g-4`** — its observable is a git-tracked AC YAML. The smoker's
  capture is `git status --short` / `git diff HEAD`, so a stranded
  `in_progress` **would** appear. It needs a fixture, not a new mechanism. This
  is the cheapest record in the store to turn into real coverage.
- **`BO-2400g-4-i`** — its observable is a PR body, which no `git diff` can see
  and which `git restore .` cannot undo. It needs a new capture mechanism, and
  invoking the real lane as a fixture would leave real pull requests behind.

## What to do

1. Flip `BO-2900g-1`, `BO-2900g-4`, `BO-2900g-2-i` to `false` using the
   `e51c4ecb` template: flag flip, an `amended_by` entry with
   `reason: derived-field-correction` stating `criteria untouched`, **shrink the
   allowlist in the same commit**, and add a `changelogs/` entry. The staleness
   test asserts every pinned id still disagrees, so flipping without shrinking
   fails CI; `unit_tests/` is not changelog-exempt.
2. Leave `BO-2400g-4` and `BO-2400g-4-i` pinned, with this document as the
   recorded reason.
3. Correct `BO-2900g-2.yaml:171-172`, which still claims that record carries
   `true`. It was flipped to `false` in `9699d501` — a stale untruth in the
   record that invented the rule.

Urgency is low and bounded: the whole-store gate
(`ci.yml:302`) is `continue-on-error: true`, and only the diff-scoped PR gate
blocks. These surface when a record is staged, which is why they sat unnoticed —
the AC hooks read the commit index, so a record never staged is never checked.

## Method note

Two independent analyses were run, one on code mechanism and one on requirement
fidelity, each briefed to stay off the other's ground. They initially split on
`BO-2400g-4` — absence-phrasing versus persisted-state — and were then
confronted with each other's argument. The mechanism analysis withdrew its
position after reading the two precedents directly, on the phase-ordering fact
above. Every load-bearing claim in this document was independently re-verified
against the tree before it was written.
