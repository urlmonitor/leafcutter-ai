---
title: "ADR-042: The Product-Truth Checker Reports a Closed Outcome Vocabulary on a Structured Channel"
description: "The product-truth checker emits a four-value outcome vocabulary plus a per-type empty_types list on a machine-readable stdout line, because the 0/1/2 exit code cannot distinguish a run that examined nothing from a run that examined everything and found it sound. Amended 2026-09-09 to withhold checked-and-sound from any run holding an unresolvable pointer, and to add the two pointer-count keys that make that exclusion observable on the structured channel."
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
  - docs/acceptance-criteria/ux-prototyping/UXP-700-truthful-project-record/UXP-700b-1.yaml
  - docs/acceptance-criteria/ux-prototyping/UXP-700-truthful-project-record/UXP-700c-1.yaml
  - docs/acceptance-criteria/ux-prototyping/UXP-700-truthful-project-record/UXP-700c-1-i.yaml
  - docs/acceptance-criteria/guardrail-engine/GE-120-green-means-checked/GE-120.yaml
  - docs/acceptance-criteria/ux-prototyping/UXP-550-atlas-mock-mode/UXP-609-2.yaml
  - docs/architecture/components/ux-prototyping.md
related_code:
  - docs/product-truth/scripts/validate_product_truth.py
  - scripts/commit_guardian/commit_guardian.json
  - unit_tests/product_truth/test_uxp_700b_1.py
---

# ADR-042: The Product-Truth Checker Reports a Closed Outcome Vocabulary on a Structured Channel

## Status

| Field | Value |
|---|---|
| Status | Proposed, amended |
| Date | 2026-09-09 |
| Amended | 2026-09-09 — Amendment 1 (`checked-and-sound` is withheld when any pointer is unresolvable; two pointer-count keys added to the payload). See [Amendment 1](#amendment-1--2026-09-09--checked-and-sound-is-withheld-when-any-pointer-is-unresolvable). |
| Deciders | BrainCandy |
| Author | Recorded during the UXP-700b-1 outcome-vocabulary pass of 2026-09-09 |
| Supersedes | None |

> **Read §1, §2 and §3 together with [Amendment 1](#amendment-1--2026-09-09--checked-and-sound-is-withheld-when-any-pointer-is-unresolvable).** The outcome is no
> longer derived from `errors` and `empty_types` alone — a third input condition
> (unresolvable pointers) was added, and §3's payload shape gained two additive keys.
> The four-value vocabulary itself is unchanged.

## Context

`docs/product-truth/scripts/validate_product_truth.py` is the checker for the project
record: it reads the store's journeys (`flows`), example datasets (`mock-data`) and
screens (`mockups`), validates them against schemas and derived data, and returns a
process exit code. Until now that exit code was its entire externally-visible result:
`0` for "no errors", `1` for "errors found", `2` for a load/setup failure.

That contract is structurally blind in one specific way. A store holding zero journeys,
zero example datasets and zero screens produces zero errors — there is nothing to find
an error in — so the checker exits `0`, exactly like a fully populated store in which
every check genuinely passed. A caller sees the same byte in both cases. The run that
examined nothing is indistinguishable from the run that examined everything and found
it sound.

This is precisely the failure mode that
[`GE-120` — green means it was checked](../../acceptance-criteria/guardrail-engine/GE-120-green-means-checked/GE-120.yaml)
exists to forbid, applied to the record's own checker. The sibling drift-guard already
adopts the correct shape under
[`UXP-609-2`](../../acceptance-criteria/ux-prototyping/UXP-550-atlas-mock-mode/UXP-609-2.yaml):
it fails when it read zero fixture records, and never passes on nothing.

The cost of not deciding is concrete and imminent, not hypothetical. The pre-commit
entry `check-product-truth-validate` in `scripts/commit_guardian/commit_guardian.json`
runs this checker through a wrapper that forwards only the exit status. A future gate
ticket (`UXP-700c-3`) will consume this checker's result as its verdict. If the result
stays a bare exit code, the emptiness blindness propagates: nothing downstream can tell
the two runs apart either, and an empty project record silently reports green forever.
Deciding the representation now — before a second component starts reading it — is what
keeps the checker (`ux_prototyping`) and its gate consumers (`precommit_hooks`) from
drifting on spelling and on meaning.

This ADR originates from ticket `UXP-700b-1` ("A run that examined nothing reports a
different outcome from a run that examined something") in
`EPIC-TruthfulProjectRecord`, whose acceptance criteria deliberately left the
representation channel open and constrained only what a caller must be able to observe.
This record closes that gap.

## Decision

### 1. The checker MUST report a machine-readable outcome from a closed vocabulary

`validate_product_truth.py` MUST classify every completed run into exactly one of four
values, and MUST NOT emit any value outside this set:

| Outcome | Meaning |
|---|---|
| `checked-and-sound` | Zero errors **and** zero empty artifact types — every type was read and every check passed. |
| `nothing-examined` | Zero errors, but **every** artifact type held zero records. |
| `degraded` | Zero errors, but **some** artifact types held zero records. |
| `failed` | One or more schema or derived-data errors were found. |

The vocabulary is closed. Adding a fifth value is itself an architectural change and
MUST be recorded by amending this ADR.

> Extended by [Amendment 1](#amendment-1--2026-09-09--checked-and-sound-is-withheld-when-any-pointer-is-unresolvable): the derivation of these four values takes a
> third input condition (unresolvable pointers). The set of values is unchanged.

### 2. `checked-and-sound` MUST be reserved for a run that examined every artifact type

A run in which any artifact type held zero records MUST NOT report
`checked-and-sound`. A wholly empty store MUST report `nothing-examined`; a partially
empty store MUST report `degraded`. Rounding either case up to the clean-pass value is
forbidden, because that is the exact conflation this ADR exists to eliminate.

> Extended by [Amendment 1](#amendment-1--2026-09-09--checked-and-sound-is-withheld-when-any-pointer-is-unresolvable) §A2: `checked-and-sound` MUST additionally be
> withheld from a run holding one or more unresolvable pointers.

### 3. The outcome MUST be carried on a structured channel, not by a new exit code

The checker MUST print the outcome as a JSON object on the **last** stdout line, of the
shape `{"outcome": <value>, "empty_types": [<type>, ...]}` (extended with two additive
pointer-count keys by [Amendment 1](#amendment-1--2026-09-09--checked-and-sound-is-withheld-when-any-pointer-is-unresolvable) §A6), and it MUST be the only
JSON-parseable line on stdout. Human-readable prose (the `logger` output) MUST go to
stderr and MUST remain separate from that line.

A caller MUST be able to distinguish the four outcomes by reading `outcome` alone,
without parsing any prose. The existing `0` / `1` / `2` exit codes MUST retain their
current meanings unchanged; this decision MUST NOT introduce a new exit code, because
the wrapper and hook already in production forward the exit status and would
mis-interpret a fourth value as an unexpected crash.

### 4. The report MUST name each artifact type that yielded zero records

`empty_types` MUST list, by name, every artifact type for which the checker read zero
records, drawn from the canonical identifiers `flows`, `mock-data`, `mockups` (matching
the store's own directory names). A type holding at least one record MUST NOT appear,
even when other types are empty. The list MUST be emitted on every run, including the
empty list on a `checked-and-sound` run, so its absence never has to be interpreted.

### 5. Gate consumers MUST read the outcome value, not the exit code alone

Any consumer that gates on this checker — starting with `UXP-700c-3`, which wires the
`check-product-truth-validate` pre-commit entry — MUST read the `outcome` field to
form its verdict. A consumer MUST NOT treat exit code `0` as sufficient evidence that
the record was checked, because `nothing-examined` and `degraded` both exit `0` by
design (see §6). Consumers MUST compare against the vocabulary defined here rather
than against ad hoc string literals of their own.

### 6. Fail-open applies to degraded runs; it MUST NOT apply to empty ones

`degraded` and `nothing-examined` MUST continue to exit `0`, preserving the standing
fail-open convention: a check that ran but was degraded does not block a commit. That
convention MUST NOT be read as permission to *report success* for a check that examined
nothing. The distinction lives in the `outcome` value, and §5's consumers are what turn
it into a blocking decision. Failing open on a degraded-but-ran check is acceptable;
reporting `checked-and-sound` for a run that examined nothing is not.

## Consequences

### Positive

- A run that examined nothing is now separable from a sound run by a single field read,
  satisfying `GE-120`'s "green means it was checked" principle for the project record.
- `empty_types` localizes the gap: a reader learns *which* artifact type is missing, not
  merely that something is, which turns an alarm into an actionable next step.
- The closed vocabulary is defined once, in the checker, giving `UXP-700c-3` a stable
  contract to import rather than a set of strings to re-spell and drift on.
- Existing consumers are unaffected: because the exit-code meanings are untouched, the
  wrapper and the pre-commit entry keep working without modification during the
  interval before the gate ticket lands.

### Negative

- Two result channels now exist (exit code and stdout JSON), and they can disagree if a
  future edit updates one without the other. `degraded` exiting `0` is deliberate, but
  it means the exit code alone is permanently insufficient — a reader who forgets §5
  will silently get the old blindness back.
- Parsing stdout is more fragile than reading an exit code: any stray `print()` that
  emits JSON on a later line would shadow the report. §3's "only JSON-parseable line"
  constraint is a rule that must be actively defended, not a property the runtime
  enforces.
- The vocabulary is a cross-component contract, so extending it later requires
  coordinating the checker and every gate consumer rather than editing one file.

### Operational

- `unit_tests/product_truth/test_uxp_700b_1.py` pins this contract, including a
  regression guard asserting the outcome payload is the only JSON-parseable stdout
  line. Changes to the checker's output must keep that suite green.
- The `check-product-truth-validate` pre-commit entry in
  `scripts/commit_guardian/commit_guardian.json` is deliberately **not** modified by
  this decision; wiring the gate to read `outcome` is deferred to `UXP-700c-3` per that
  ticket's contract.
- Because `degraded` and `nothing-examined` exit `0`, an operator watching only CI exit
  statuses will not notice an emptying store. Surfacing the `outcome` value in run logs
  is the intended mitigation until the gate lands.

## Alternatives

- **Add a fourth exit code (e.g. `3` for "nothing examined").** Rejected. The checker is
  invoked through a wrapper that forwards the exit status verbatim into the pre-commit
  runner, which treats any non-zero status as a hook failure. A `3` would therefore turn
  an intentionally fail-open empty-store run into a hard commit block, changing the
  meaning of the existing contract rather than extending it, and it could still carry
  only one bit of information — it could never name *which* artifact types were empty
  (§4).

- **Let callers grep the human-readable log line ("OK: 0 flows, 0 mock-data, 0 mockups").**
  Rejected. That line is prose on stderr written for a human, and its wording changes
  whenever a message is improved; a consumer built on it breaks on an unrelated
  copy-edit. It also fails the AC's explicit requirement that a caller reading only the
  outcome, without reading the message, can tell the two runs apart.

- **Write the outcome to a sidecar file the gate reads afterwards.** Rejected. It
  introduces lifecycle problems the stdout line does not have: a stale file from a
  previous run is indistinguishable from a fresh one if the checker crashes before
  writing, so the gate could read a `checked-and-sound` verdict for a run that never
  completed — reintroducing the exact false-green this ADR removes.

- **Return a rich Python object and require consumers to import `main()` in-process.**
  Rejected. The production entry point is a subprocess CLI invoked by the pre-commit
  runner, which cannot import the module across the process boundary. It would force
  every consumer into the checker's interpreter and dependency set, and would leave the
  actual shipped invocation path — the one the hook uses — still reporting only an exit
  code.

- **Emit a boolean `examined: true/false` flag instead of a vocabulary.** Rejected. A
  boolean cannot represent the partially-empty store, which is neither fully examined
  nor fully empty; `degraded` would collapse into one of the two poles. Collapsing it
  into `examined: true` recreates the false-green for a store missing two of three
  artifact types, which is the case `UXP-700b-1-ii` specifically pins.

- **Leave the checker alone and let the future gate (`UXP-700c-3`) count artifacts itself.**
  Rejected. The gate would have to re-implement the store's loading and counting logic
  in a different component, so the two counts could disagree after any change to the
  store's layout, and the checker itself would keep reporting a green result it has not
  earned to every other caller.

## Amendment 1 — 2026-09-09 — `checked-and-sound` is withheld when any pointer is unresolvable

| Field | Value |
|---|---|
| Amends | §1's derivation of the four values (a third input condition), §2's reservation rule for `checked-and-sound`, and §3's stdout payload shape (two additive keys) |
| Status | Proposed |
| Deciders | BrainCandy |
| Driven by | `UXP-700c-1-i` ("A pointer the checker cannot classify is reported as unresolvable, never as sound"), extending `UXP-700c-1` |
| Supersedes this ADR? | No. The vocabulary stays closed at four values, and every alternative rejected above stays rejected. |

### Why this had to change

[`UXP-700c-1`](../../acceptance-criteria/ux-prototyping/UXP-700-truthful-project-record/UXP-700c-1.yaml)
gave the checker a **two-valued** pointer verdict: `_check_pointers` either counts a
pointer as resolved (its target AC id is in the AC store) or appends it to `errors` as
broken. That partition is exhaustive only if every pointer's target is a kind the
checker knows how to resolve.

[`UXP-700c-1-i`](../../acceptance-criteria/ux-prototyping/UXP-700-truthful-project-record/UXP-700c-1-i.yaml)
closes the gap that leaves. A pointer whose target lies outside the recognised target
kinds fits neither bucket, and forcing it into either one produces a distinct failure:

|  | Where the unclassifiable pointer lands | What it costs |
|---|---|---|
| Counted as resolved | The resolved count and `checked-and-sound` | A false green: the run claims to have verified a pointer it never understood. This is exactly the `GE-120` failure this ADR exists to prevent, one layer down. |
| Appended to `errors` | The broken-pointer list, exit code `1` | A hard commit block for a pointer that is not known to be dangling. Adopters learn to ignore the report, which hides real drift a second way. |

That AC's fourth clause reaches this record directly: "the run's outcome is not the
outcome for a record that was checked and found sound while any pointer is
unresolvable." §1 above derives the outcome from `errors` and `empty_types` **only**, and
§2 states the reservation rule for `checked-and-sound` in terms of empty artifact types
alone. Implementing the AC without amending this record would leave shipped code
contradicting an active decision, with nothing anywhere saying which a reader should
believe — the same class of defect this ADR was written to remove.

### A1. The pointer verdict gains a third value; the outcome vocabulary does not

`_check_pointers` MUST classify every pointer it walks into exactly one of three
verdicts: `resolved`, `broken`, or `unresolvable`. This third value is a **pointer**
verdict, not a run outcome. The run-outcome vocabulary of §1 stays closed at four values
and MUST NOT gain a fifth, because `degraded` already carries the precise meaning an
unresolvable pointer leaves the run in: the run completed and found no errors, but it
did not establish that everything it was asked to check is sound.

### A2. An unresolvable pointer MUST demote `checked-and-sound` to `degraded`

§2 is extended. `checked-and-sound` MUST be withheld from any run in which one or more
pointers were classified `unresolvable`, in addition to being withheld from a run with
errors or with empty artifact types. Such a run MUST report `degraded`.

The three input conditions MUST be evaluated in this fixed precedence order:

1. one or more entries in `errors` → `failed`
2. otherwise, **every** artifact type empty → `nothing-examined`
3. otherwise, **some** artifact type empty **or** one or more unresolvable pointers → `degraded`
4. otherwise → `checked-and-sound`

`_compute_outcome` MUST receive the unresolvable-pointer count as an explicit third
argument alongside `errors` and `empty_types`. It MUST NOT infer that count from the
other two inputs, and no caller may pre-fold the condition into `errors` or
`empty_types` to avoid changing the signature — folding it in would violate §A3 and
would make the third condition invisible at the one call site that decides the outcome.

### A3. An unresolvable pointer MUST NOT be an error and MUST NOT be a resolution

An unresolvable pointer:

- MUST NOT be appended to `errors`. It therefore never appears in the broken-pointer
  report and never changes the process exit code, which stays `0` under the fail-open
  convention of §6 — a check that ran but could not classify a target does not block a
  commit; it reports `degraded` and is caught by §5's consumers.
- MUST NOT be counted in `_check_pointers`'s resolved count. The resolved count states
  how many pointers were *verified against the AC store*, and an unclassifiable target
  was never verified against anything.
- MUST NOT affect `empty_types`. That list names artifact types that yielded zero
  records (§4) and its meaning is unchanged by this amendment.

### A4. Classification MUST be by an explicit recognised-target-kind predicate, not by lookup failure

The checker MUST decide `unresolvable` by asking whether the pointer's target belongs to
a target kind it knows how to resolve, and MUST make that decision **before** attempting
any lookup. It MUST NOT infer `unresolvable` from a lookup that returned nothing: a
failed lookup of a *recognised* kind is `broken`, and conflating the two is precisely the
mutation `UXP-700c-1-i` exists to kill. A target of a recognised kind MUST continue to be
resolved exactly as `UXP-700c-1` established; only an unrecognised kind yields
`unresolvable`.

Exactly one such predicate MUST exist in
`docs/product-truth/scripts/validate_product_truth.py`, and it MUST be a named function
so that every call site shares it. A second, per-call-site classification MUST NOT be
written — a second classifier is how a fourth ad hoc vocabulary enters a codebase this
ADR already closed once.

### A5. The unresolvable report MUST name holder, position, target and reason

Each unresolvable pointer MUST be reported as one message on the existing prose channel
(the module `logger`, which §3 requires to go to stderr), at `WARNING` level so it
survives the `--quiet` flag. Each message MUST carry all four of:

1. the artifact holding the pointer (`flow['id']`),
2. the position within that artifact (the step or branch id),
3. the target that could not be classified,
4. the reason it could not be classified.

The message MUST use the prefix `[pointer-unresolvable]`, distinct from the
`[pointer]` prefix broken pointers already use, so the two verdicts are separable by a
reader and by a `grep` without parsing the rest of the line. The reason MUST name which
classification the target failed; it MUST NOT be empty and MUST NOT be the bare word
"unknown", which states nothing an operator can act on.

### A6. The stdout payload gains two additive integer keys

§3's payload shape becomes:

```json
{"outcome": "<value>", "empty_types": ["<type>", "..."], "resolved_pointers": 0, "unresolvable_pointers": 0}
```

`resolved_pointers` and `unresolvable_pointers` MUST both be integers and MUST both be
emitted on every run, including the zero values, so their absence never has to be
interpreted (the same rule §4 already applies to `empty_types`). Everything else in §3
is unchanged: this remains a single line, the last stdout line, and the only
JSON-parseable line on stdout, with prose on stderr.

The counts live on the structured channel because `UXP-700c-1-i`'s second clause — the
unresolvable pointer "is excluded from the stated count of pointers resolved" — is
otherwise observable only in stderr prose, which §3 forbids consumers from parsing.
Placing both counts in the payload makes the exclusion checkable through the same
channel §5's consumers already read.

Payload keys are **additive-only**. Consumers MUST continue to form their verdict from
`outcome` alone (§5) and MUST NOT assert an exact key set or reject unrecognised keys.
That rule is what keeps `unit_tests/product_truth/test_uxp_700b_1.py` green across this
amendment, and it MUST be preserved by any future extension of the payload.

### Consequences of this amendment

#### Positive

- The false green closest to the checker's own subject matter is removed: a record whose
  pointers the checker could not understand can no longer report `checked-and-sound`.
- The noisy alternative is removed at the same time: an unclassifiable pointer does not
  block a commit, so the report stays credible and adopters have no reason to learn to
  ignore it.
- `unresolvable_pointers` gives `UXP-700c-3`'s gate a count it can surface, and
  `resolved_pointers` gives it the denominator, without either side re-implementing the
  pointer walk.
- The single-JSON-line contract and the four-value vocabulary both survive intact, so no
  existing consumer needs to change to keep working.

#### Negative

- `degraded` now means two different things — "some artifact type was empty" and "some
  pointer was unclassifiable". A reader who sees only `outcome` cannot tell which; they
  must read `empty_types` and `unresolvable_pointers` to find out. This is the price of
  keeping the vocabulary closed, and it is why §A6 requires both keys on every run.
- `_compute_outcome`'s signature changes, so every caller and every direct-import test
  must be updated in the same change.
- The recognised-target-kind predicate (§A4) is a new place where a mistake is silent: a
  kind wrongly treated as unrecognised turns a genuinely broken pointer into a
  non-blocking `degraded`. Its definition needs the same care as the vocabulary itself.

#### Operational

- `unit_tests/product_truth/test_uxp_700b_1.py` remains the pinned regression suite for
  §3 and MUST stay green; the additive-key rule in §A6 is what makes that possible.
- `unit_tests/product_truth/test_uxp_700c_1_i.py` pins this amendment. Its reachability
  test MUST invoke `main()` as a subprocess and assert on the `outcome` field of the
  stdout payload, per §3 — not on parsed prose and not by importing the helper directly.
- Because an unresolvable pointer keeps exit code `0`, an operator watching only CI exit
  statuses will not see it. `unresolvable_pointers` in the run log is the mitigation
  until `UXP-700c-3`'s gate reads the field.

### Alternatives considered for this amendment

- **Add a fifth outcome value (e.g. `unresolvable-pointers`).** Rejected. §1 declares the
  vocabulary closed and §5 requires every consumer to compare against it; a fifth value
  would fall through the comparison chain of every consumer written against the four,
  landing in an unhandled branch rather than in a verdict. It would also carry no
  information that `degraded` plus `unresolvable_pointers` does not already carry.

- **Report unresolvable pointers through `errors`.** Rejected. It contradicts the AC's
  third clause directly, and it turns exit `1` — a hard pre-commit block — into the
  response to a pointer the checker merely does not know how to classify yet. Screen and
  mockup pointers are an explicitly anticipated future kind, so this would block commits
  on work that is simply ahead of the checker.

- **Count unresolvable pointers as resolved.** Rejected. This is the named mutation the
  AC exists to kill: the resolved count would over-state what was verified, and the run
  would report `checked-and-sound` for a record whose pointers were never checked — the
  exact false-green `GE-120` forbids.

- **Infer `unresolvable` from a lookup miss plus a heuristic on the target string.**
  Rejected. A malformed-but-recognised AC id would be silently downgraded from `broken`
  to `unresolvable`, so a genuinely dangling pointer would stop blocking and stop being
  reported as broken. The decision must be about the target's *kind*, taken before the
  lookup (§A4).

- **Leave the outcome alone and let `UXP-700c-3`'s gate notice the unresolvable count.**
  Rejected for the same reason as the "let the gate count artifacts itself" alternative
  above: the checker would keep reporting a `checked-and-sound` it has not earned to
  every other caller, and the gate would be the only place in the system where the
  record's real state was known.

- **Carry the full unresolvable detail list (holder, position, reason) in the stdout
  payload.** Rejected. The detail is per-pointer prose whose consumer is a human, and
  every other per-artifact finding in this checker already lives on the prose channel;
  embedding it would grow the single-line payload for no consumer that reads it, while
  making the line harder to eyeball. Counts are the machine-readable part (§A6); the
  naming requirement is met on stderr (§A5).

## References

- Originating ticket: `EPIC-TruthfulProjectRecord/11_TICKET-20260909-UXP-700b-1.md`
  (AC `UXP-700b-1`); extended by `UXP-700b-1-ii` (the partially-empty `degraded` case).
- Consuming ticket: `UXP-700c-3` — wires the pre-commit gate to this vocabulary.
- [`GE-120` — green means it was checked](../../acceptance-criteria/guardrail-engine/GE-120-green-means-checked/GE-120.yaml)
  — the parent principle this decision applies to the record's own checker.
- [`UXP-609-2`](../../acceptance-criteria/ux-prototyping/UXP-550-atlas-mock-mode/UXP-609-2.yaml)
  — the drift-guard shape mirrored here: never pass on zero records read.
- Governed code: `docs/product-truth/scripts/validate_product_truth.py`
  (`_compute_outcome`, `_compute_empty_types`, `_check_pointers`, `main`).
- Amendment 1 ticket: `EPIC-TruthfulProjectRecord/20_TICKET-20260909-UXP-700c-1-i.md`
  (AC `UXP-700c-1-i`), extending `19_TICKET-20260909-UXP-700c-1.md` (AC `UXP-700c-1`,
  the two-valued pointer verdict this amendment adds a third value to).
- Amendment 1 is pinned by `unit_tests/product_truth/test_uxp_700c_1_i.py`.
