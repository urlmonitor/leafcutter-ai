---
title: "KI-BO-20260907-1555 — `failed` is a terminal phase state: the dispatcher filters it out, so a phase that exhausted its retries can never be re-run by any later drive"
description: "KI-BO-20260907-1555 — `failed` is a terminal phase state: the dispatcher filters it out, so a phase that exhausted its retries can never be re-run by any later drive"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - build_orchestration
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/known-issues/README.md
---

# KI-BO-20260907-1555 — `failed` is a terminal phase state: the dispatcher filters it out, so a phase that exhausted its retries can never be re-run by any later drive

> One known issue, split out of `docs/known-issues/build-orchestration.md` on
> 2026-09-14. Index: [build-orchestration.md](../../build-orchestration.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** **RESOLVED 2026-09-07** — fix direction 1 taken, in both twins. Left in the
  register rather than deleted because the reasoning below is why the predicate is shaped the
  way it is, and the entry is cited from the code.
- **Occurrences:** 1 confirmed in detail (GE-120 ticket 36); 6 further tickets in the same
  epic carried at least one `failed` phase when this was filed
- **First seen:** 2026-09-07 · **Last seen:** 2026-09-07
- **Where (before the fix):** `templates/workflows-js/build-ticket.js:1293`
  (`orderedPhases.filter((p) => p.status === "needed")`), against the planner schema at
  `:70` whose status enum is `['needed', 'signed_off', 'not_needed', 'failed']`.
  **TWIN: `build-feature.js:1541` carried the identical filter (verified) — both fixed.**

> **Resolution.** The inline filter in both drivers is replaced by a pure, named
> `selectDispatchableByStatus(orderedPhases)` selecting `needed` **or** `failed`. It is a
> function rather than a widened inline filter for two reasons: the `failed` half is a
> decision that has to be readable at the call site, and a pure top-level function can be
> extracted and **executed** under `node` by the unit layer — which
> `unit_tests/workflows/test_ki_bo_20260907_1555_failed_phase_redispatch.py` does, running
> the real on-disk function from both files against GE-120 ticket 36's actual frontmatter.
>
> **Measured before and after** on that ticket's real phase map: the old predicate returned
> **0** phases, the new one returns **5**.
>
> **Why re-dispatch terminates**, which was the load-bearing question: on success a phase
> agent *sets* `signed_off` (signoff skill §"Update frontmatter" step 1) rather than
> find-replacing the literal `needed`, so the `failed` row is cleared and the phase does not
> return on the next drive. On failure it stays `failed`, where it already was. The
> within-drive retry ladder is untouched. This also makes the driver match the state machine
> the signoff skill already documented — *"`failed` → `signed_off` after rework"* — which the
> dispatcher had simply never implemented.
>
> **Deliberately not done:** a cross-drive attempt counter (part of fix direction 1 as
> originally written). Without it a genuinely unfixable phase is retried once per re-drive.
> That is operator-gated rather than automatic, and strictly better than the dead end it
> replaces, but it means an unattended epic re-drive now spends one attempt per failed phase.
> Revisit if that cost shows up.
>
> **Fix direction 2 is still open and still worth doing.** The `noPhaseRequired` refusal at
> `build-ticket.js:902` remains scoped to "absent, empty, or every phase `not_needed`", and
> its advice still reads *"Do not look for a failed phase"*. That message is now much harder
> to reach — an all-`failed` ticket dispatches instead of refusing — but if it is ever reached
> it still misdirects.

**The dispatcher recognises four phase states and will act on exactly one of them.** The
planner is explicitly asked to report `failed` — it is in the schema enum, and the read-back
prompt at `:769` names the needed set as "every agent in the frontmatter `agents:` map whose
value is `needed`". The dispatch set is then computed by the single filter at `:1293`. A phase
recorded `failed` is therefore *enumerated and discarded*.

Nothing anywhere in the workflow transitions `failed` back to `needed`. The failure-adjudication
ladder retries **within** a drive; once a phase exhausts that ladder and the state is persisted
to frontmatter, the only exit is a human editing the `agents:` map by hand. `failed` is
write-only.

**Observed.** GE-120 ticket 36 (`GE-120e-4-i`) ended a drive with:

```yaml
agents:
  ac-fulfillment-gate: failed
  ac-validator: failed
  commit: failed
  pull-request: not_needed
  python-coder: failed        # signed_off today, by direct dispatch
  test-runner: failed
  test-writer: signed_off
```

Zero phases marked `needed`. Re-driving the ticket through `build-ticket.js` dispatched **no
phase agent at all** and wrote no code — not as a bug in that run, but by construction: the
filter at `:1293` had nothing to select. The implementation was produced only by abandoning
the workflow and dispatching `python-coder` directly, which took it to 4/4 green in a single
pass. The tokens spent on the no-op re-drive bought nothing, and a second re-drive would have
bought the same nothing.

**What is NOT wrong here, so that nobody fixes the wrong thing.** The completion side is
sound and was clearly designed with this hazard in mind:

- With an empty dispatch set, `:1338` still runs `concludeTicket`, and deliberately bases the
  decision on `claimedPhasesForCompletion` (`:680`) — *every* agent in the map except
  `not_needed`, which **includes the `failed` ones**.
- Each of those must be backed by a passing sign-off entry in the record. The `failed` phases
  have none, so they land in `outstanding` and the verdict is `completed: false`.

The ticket is correctly held `todo`. **This is not a phantom-done.** The driver diagnoses the
state accurately and then cannot act on it — it reports phases as outstanding that it has no
mechanism to ever run. That gap between an accurate diagnosis and an impossible remedy is the
whole defect.

**Why it is worth an entry rather than a shrug.** The state is reached by the ordinary
failure path — any ticket whose coder or test-runner exhausts the retry ladder lands here — and
the operator-visible symptom is "I re-ran the drive and it did nothing", which reads like a
harness fault rather than a state-machine dead end. Six other tickets in this one epic are
already carrying `failed` phases. In the five of those that still have some `needed` phases the
symptom is quieter and worse: the drive runs, makes real progress, and silently never retries
the failed phase, so each re-drive shrinks the `needed` set while the `failed` set stays frozen.

**Fix direction, in preference order.** *(1 taken; the attempt-counter half of it and item 2
remain open — see the resolution note above.)*

1. **Treat `failed` as re-dispatchable.** Change the filter at `:1293` to select `needed` **or**
   `failed`, and carry a per-phase attempt counter in the frontmatter so the retry ladder's cap
   survives across drives rather than resetting. This is the smallest change and matches what
   an operator means by "re-run the drive". Apply to the `build-feature.js` twin in the same
   commit.
2. **Failing that, make the dead end loud.** When the dispatch set is empty *and* the map
   contains a `failed` phase, refuse with a message that names those phases and states plainly
   that no drive will retry them until they are flipped to `needed`. The `noPhaseRequired`
   branch at `:902` is the model — it exists precisely because "an empty set means nothing was
   looked at, never that everything passed" — but its condition ("absent, empty, or marks every
   phase it names as `not_needed`") does not cover the all-`failed` case, and its advice
   actively says *"Do not look for a failed phase"*, which is the wrong instruction for exactly
   this state.
3. **At minimum, document it** in the building-epics skill so the manual remedy (flip to
   `needed`, or dispatch the agent directly) is discoverable without reading the dispatcher.

**Related.** `KI-BO-025` (the build-feature planner schedules only the currently-unblocked set
and never re-plans) is the same shape one level up: a set computed once, and no path back into
it. `KI-ACD-20260907-1555` shares this epic's ticket 36 as its worked example, from the
contract side.

**Pattern:** a state machine that persists a terminal state its own dispatcher does not accept
as input — so the recorded outcome of a failure permanently removes the work from the only
mechanism that could address it, while every report about that work continues to list it as
owed.

---
