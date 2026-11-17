---
title: "KI-TQ-20261024-sweep-list-recorded-against-head — test-writer records its consumer-sweep list against the branch's own HEAD, so the list stops counting once the branch takes in main and finish checks against the merge-base"
description: "medium — templates/agents/test-writer.md tells the writer to run consumer_sweep.py check and record with --base-ref HEAD. record stores that commit as the list's base, and check honours a list only at that base or a later base that descends from it. When finish runs against the merge-base with main after the branch has taken in main, a list recorded on a branch-only commit is not an ancestor of that base, every entry is dropped, and finish stops at 'sweep' with 'sweep list missing' for edits that were recorded. Seen 2026-10-24 on TQ-200d-1 (record base 9c3fb043, finish base 78a408fc)."
type: reference
category: reference
status: active
created: '2026-10-24'
last_updated: '2026-10-24'
components:
  - testing_quality
related_docs:
  - docs/known-issues/testing-quality.md
  - docs/known-issues/README.md
---

# KI-TQ-20261024-sweep-list-recorded-against-head — the sweep list is tied to the HEAD it was recorded at

> Filed 2026-10-24. Index: [testing-quality.md](../testing-quality.md).
> Filename severity is the three-level index bucket (`low`); the original grading is the
> `**Severity:**` line below.

- **Severity:** medium. The check fails closed, so no weakening slips through. But a correct,
  recorded sweep reads as "no list at all", the work stops before commit, and the only way on is
  to record the list again by hand against the base finish uses.
- **Status:** open, no AC.
- **Occurrences:** 1. TQ-200d-1 on 2026-10-24: the list was recorded with `--base-ref HEAD` on the
  branch-only commit `9c3fb043` (a docs commit made before the tests were written). The branch then
  took in `origin/main`, the work was committed, and `wrong_version_gate.py finish` was run against
  the merge-base `78a408fc`. It stopped at step `sweep` with `reason: "sweep list missing"`. Recording
  the same list again with `--base-ref 78a408fc` cleared it.
- **First seen:** 2026-10-24 · **Last seen:** 2026-10-24
- **Where** (line numbers at `origin/main` `849791105`):
  - `templates/agents/test-writer.md`:681 (the preview `consumer_sweep.py check`) and :701 (the
    `consumer_sweep.py record`), both with a fixed `--base-ref HEAD`. Nothing in the section
    (:625-750) says the base must match the one finish checks against, or that a list must be
    recorded again after the branch takes in main.
  - `scripts/build_orchestration/consumer_sweep.py`:93-124, `record`. It resolves `--base-ref`
    (default `HEAD`, :108) and stores that sha as the list's `base` (:120).
  - `scripts/build_orchestration/consumer_sweep.py`:127-135 and :138-149, `_moved_files` and
    `_honoured`. A list counts in full only when its base equals the check's base (:142). Otherwise
    its base must be an ancestor of the check's base (`git merge-base --is-ancestor`, :130); when it
    is not, `_moved_files` returns `None` and `_honoured` returns no entries (:147-148).
  - `scripts/build_orchestration/consumer_sweep.py`:207-214, `check`. With no honoured entries, every
    edit is unlisted and the reason is `"sweep list missing"` (:214), the same text as when no list
    was ever recorded.
  - `scripts/build_orchestration/wrong_version_gate.py`:91. `finish` runs the check with its own
    `--base-ref`. The routes pass `--base-ref HEAD` today: `templates/workflows-js/fast-lane-ship.js`:1773,
    `templates/workflows-js/build-feature.js`:1828, `templates/workflows-js/build-ticket.js`:1427 and
    `templates/skills/building-epics/SKILL.md`:1185.

## Symptom

`wrong_version_gate.py finish` stops at step `sweep`. The sweep object reports
`reason: "sweep list missing"` and lists as `unlisted` the very edits the writer recorded. A
`consumer_sweep.json` exists under `<git-dir>/leafcutter/work/<key>/`, and its `base` is a commit
that is not an ancestor of the base finish was given.

## Mechanism

1. **The list is anchored to a commit, not to the work.** `record` writes the sha of whatever
   `--base-ref` names. The template always names `HEAD`, which is the branch tip at the moment of
   recording, not the commit the work is measured against.
2. **The check only accepts its own base or a descendant of it.** That rule is right for a list
   recorded before later commits on the same line. It drops a list whose base sits on a side of
   history the check's base does not contain.
3. **Taking in main moves the base.** Once the work is committed and the branch has taken in main,
   `HEAD` no longer shows the work as a change. The work is then checked against the merge-base
   with main (as on TQ-200d-1), and a list recorded on a branch-only commit is not an ancestor of
   that merge-base. All its entries are dropped.
4. **The message hides the cause.** "sweep list missing" is the same text as for a writer that
   never recorded, so the operator looks for a missing record, not a base mismatch.

On the routes as written, the record and finish both use `HEAD` while the work is still
uncommitted, so they usually agree. The gap opens as soon as the two bases differ: a finish run
against the merge-base or another route base, or a branch that commits on its own line before
the writer records.

## Detection

Read `base` from `<git-dir>/leafcutter/work/*/consumer_sweep.json` and run
`git merge-base --is-ancestor <recorded base> <finish base>`. A non-zero exit on a check that
reports "sweep list missing" for recorded edits is this issue.

## Workaround

Record the same list again with `consumer_sweep.py record --base-ref <the base finish uses>` (for
example the merge-base with `origin/main`), then rerun finish.

## Suggested fix

Directions only; nothing here is applied.

- **Record against the base finish uses.** Have the template take the base from the dispatch (a
  base ref the route passes in, shared with its finish call) or name the merge-base with the
  target branch, instead of a fixed `HEAD`.
- **Or let record store the merge-base itself.** `record` could resolve the merge-base of `HEAD`
  with the target branch and store that, so a later merge of main keeps the list an ancestor of the
  check's base.
- **Document re-recording.** State in the Existing-Test Sweep section that a list must be recorded
  again after the branch takes in main or after the work is committed.
- **Say why a list was dropped.** When a list exists but its base is unrelated, report that (for
  example `"sweep list base not usable"`) instead of "sweep list missing".

**Pattern:** a record tied to the commit that happened to be checked out, read later by a check
that measures against a different commit.
