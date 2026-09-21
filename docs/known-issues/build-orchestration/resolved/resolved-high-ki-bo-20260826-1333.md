---
title: "KI-BO-20260826-1333 — Nine of a file's ten tests asserted only that strings were present in the source they covered — so the AC looked comprehensively covered because coverage was measured by count"
description: "KI-BO-20260826-1333 — Nine of a file's ten tests asserted only that strings were present in the source they covered — so the AC looked comprehensively covered because coverage was measured by count"
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

# KI-BO-20260826-1333 — Nine of a file's ten tests asserted only that strings were present in the source they covered — so the AC looked comprehensively covered because coverage was measured by count

> One known issue, split out of `docs/known-issues/build-orchestration.md` on
> 2026-09-14. Index: [build-orchestration.md](../build-orchestration.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** **closed in source** — fixed and merged 2026-08-26, PR #573 (squash `d97eb399`).
  **Not yet closed at the point of use** — see the deployment caveat below.
- **Occurrences:** 1
- **First seen:** 2026-08-26 · **Last seen:** 2026-08-26
- **Where:** `unit_tests/workflows/test_bo_1000c_1a.py` (nine of its ten tests, pre-#573)
  against `templates/workflows-js/finalize-feature.js` · AC `BO-1000c-1a`

**Correction — it was nine of ten, and the tenth is the entry's best evidence.**
`test_ac2_no_overwrite_of_journal_file` asserts `assertFalse(_OVERWRITE_JOURNAL_ANTI_PATTERN
.search(js))` — an **absence** assertion, not a presence one. It is also precisely the one of
the ten that **survives** the corrected source: the observed run was 9 failed, 1 passed, and
the one that passed is the one shaped differently.

That turns this entry's countermeasure from a proposal into a measurement. The argument below
is that absence assertions hold where presence assertions rot; the file already contained one
of each kind, and under a change that deleted the mechanism, the nine presence assertions all
demanded it back while the single absence assertion stayed correct. The evidence was in the
original test run and went unremarked.

**Deployment caveat — "closed" means closed on `main`, and that is not the same thing.**
Hours after `d97eb399` merged, the deployed copy still contained the deleted mechanism:

```text
grep -c "appendJournal\|require(" .leafcutter/workflows/finalize-feature.js  ->  4
```

The source is fixed; the tree that actually runs is not. Any finalize run launched from this
workspace still executes the `require('fs')` version.

This is `KI-BP-20260826-1331` demonstrating itself on the very fix that closed this entry, filed in the
same pull request — which is a sharper illustration than either entry could give alone. It
also sets a precedent worth adopting: in this repository, **"fixed and merged" is not
sufficient grounds to call a defect closed**, because the deployed surface is not derived from
`main`. A status line saying `closed` without naming which tree it refers to is the same
category of claim as an AC marked `done` on a test that never executed.

**Symptom.** `BO-1000c-1a` ("background finalize appends each progress line to a durable,
pollable run-progress journal as it happens") read `work_status: done` while its mechanism had
never once executed. `appendJournal()` obtained Node's `fs` module through `require('fs')`. The
E2 engine injects only `agent`, `parallel`, `pipeline`, `phase`, `log`, `args`, `workflow` and
`budget` into a workflow body — there is no module loader (ADR-030). The call therefore threw
on **every** invocation, a surrounding `try`/`catch` logged a WARNING, and the run reported
success. No journal file was ever written.

**Why this is a fourth concentration and not another instance of the first.** `KI-BO-028` names
three concentrations behind the phantom-dones the 2026-08-25 triage found: presence-only
assertions over JavaScript source (M1), population-vs-change scoping (`KI-CG-001`), and a
producer never round-tripped through its consumer (`BO-2200c-5`). This is a fourth, and the
distinction from the first is the whole point:

| | the grep-only concentration (`KI-BO-008`, `BO-2400f-10`) | this |
|---|---|---|
| Scope | an *individual* presence assertion propping up an individual AC | an *entire file* — ten of ten tests |
| Shape | a weak test among stronger ones | presence-only **is the file's design** |
| How it reads | one thin test, visible as thin to anyone who looks | comprehensive: a ten-test suite for one criterion |

Every one of the ten read `finalize-feature.js` as text and asserted that `appendJournal`,
`journalPath` and `fs.appendFileSync` were **present**. All ten passed for the entire life of
the defect, because the strings were there and the code never ran. Run against the corrected
source, **9 of 10 fail** — each one demanding that the dead mechanism be put back.

That is the failure the count hides. An AC covered by one grep looks under-tested. An AC
covered by ten tests looks thoroughly tested, and the only way to see otherwise is to read all
ten and notice they are the same assertion ten times. Coverage measured by test count is
maximally misleading exactly here: the reviewer's normal heuristic — "does this have tests?" —
returns the wrong answer with more confidence the larger the suite is.

**The countermeasure, which generalises.** The replacement is a single **absence** assertion:
the corrected source is asserted *not* to contain the known-broken pattern. The asymmetry is
why it works.

- A **presence** assertion stays green on dead code. That is exactly what happened here.
- An **absence** assertion fails the moment the pattern returns — whether or not it is reached
  at runtime, and whether or not it is wrapped in a swallowing `try`/`catch`.

That last clause is why a behavioural test cannot substitute. An inert reintroduction of
`require('fs')` inside a catch-all changes no observable dispatch: the run still succeeds, the
journal still is not written, and every behavioural assertion about the workflow's output still
passes. There is nothing for a behavioural test to observe. The only available signal is the
text of the source, and the only useful thing to assert about it is that the pattern is gone.

This is the same class `BP-1100b-5` exists to catch mechanically — presence-only assertions
ceasing to count as coverage. `BP-1100b-5` is still `todo` on `main`, and per `KI-BO-20260826-1332` a
complete unmerged implementation of it has existed on a local branch since 2026-08-19. Until it
lands, absence assertions are hand-written per defect.

**Two corrections landed with the fix, both worth recording.** The AC's *title* still described
the deleted mechanism and contradicted its own amended criteria — scanners and readers surface
the title, not the Gherkin, so a title promising the opposite of its criteria is its own
phantom-done vector. And `work_status` went `done` → **`in_progress`**, not `done`: only 1 of
the 5 declared `test_spec` descriptors is implemented, the other four needing a vm-sandboxed E2
harness that does not exist on `main`. Closing it would have minted a fresh phantom-done while
repairing one.

**Pattern:** `docs/reference/false-green-mechanisms.md` → M1 (a test that greps for a string
instead of exercising the behaviour), in its whole-suite form — where the number of tests is
itself the thing that makes the gap invisible.

**Related.** `KI-BO-028` (the triage this extends; `BO-1000c-1a` is recorded in its addendum as
the sweep's nineteenth phantom-done). `KI-BO-008` (a structural test making code comments
load-bearing — the individual-test form of the same mechanism). `KI-BO-20260826-1332` (why the
`BP-1100b-5` implementation that would catch this mechanically is invisible to the store).

---
