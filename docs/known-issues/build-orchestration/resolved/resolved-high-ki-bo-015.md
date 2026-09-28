---
title: "KI-BO-015 — `_worktree_exists` does not know the `fast-lane/` prefix, so a fast-lane run cannot recognise its own workspace and aborts at phase one"
description: "KI-BO-015 — `_worktree_exists` does not know the `fast-lane/` prefix, so a fast-lane run cannot recognise its own workspace and aborts at phase one"
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

# KI-BO-015 — `_worktree_exists` does not know the `fast-lane/` prefix, so a fast-lane run cannot recognise its own workspace and aborts at phase one

> One known issue, split out of `docs/known-issues/build-orchestration.md` on
> 2026-09-14. Index: [build-orchestration.md](../../build-orchestration.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** **RESOLVED 2026-09-07 — root cause fixed; the remedy this entry proposed was
  deliberately NOT taken.** `_worktree_exists` now matches `refs/heads/fast-lane/<branch>`, so
  the prefix blindness is gone and the lookup can see its own workspace. What it does on
  finding one is a **named refusal**, not reuse — specified by `BO-2400f-13` and its four
  children, and recorded as **ADR-039**. Verified: 10/10 on
  `test_bo2400f_13_occupied_workspace_refusal.py` plus 45 further tests across the changed
  module, all under `AC_ENFORCE_STRICT=1`.
  **The title above was corrected on the same date.** It read *"can never **reuse** its own
  worktree"*, which states the remedy as if it were the defect. The defect is that the lookup
  cannot **recognise** its own workspace; what to do about a recognised one was always a
  separate question, and this entry's own fix-direction listed it as undecided. The old
  wording cost a real collision: a test-writer derived a regression guard asserting reuse from
  this entry's framing while a coder implemented the AC's refusal, and the two met at the green
  gate after ~907k subagent tokens.
  **Do not delete this entry** — acceptance criteria and commit messages cite it by id.
- **Occurrences:** 1
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `templates/scripts/setup_ticket_worktree.py:232-275` (`_worktree_exists`), called at `:1289` from `cmd_create_fastlane_worktree`; branch built at `:1286` by `_fastlane_branch` (`:487-500`)

**Symptom.** `cmd_create_fastlane_worktree` creates the branch `fast-lane/<slug>` but asks
`_worktree_exists(slug)` whether a worktree already exists. That function matches a branch
against exactly three hardcoded prefixes:

```python
f"refs/heads/feature/{branch}",
f"refs/heads/ticket/{branch}",
f"refs/heads/ac-authoring/{branch}",
```

`fast-lane/` is absent, so the lookup can never match a fast-lane worktree. The reuse
branch is unreachable code. Every invocation falls through to `git worktree add`, which
fails with exit 128 the moment anything already occupies the target path. The workflow
surfaces this as `{"worktree_path": ""}` and halts at its first phase, having done nothing.

**Two consequences, the second worse than the first.**

*Collision.* The worktree path is derived solely from the AC id — `worktrees/<slug>` — so
any pre-existing directory there kills the run. This is how it was found: a hand-created
`worktrees/bo-1500a-5` (made minutes earlier for the same AC) caused
`fatal: '/home/henzeh/projects/leafcutter/worktrees/bo-1500a-5' already exists`, then
`fatal: … contains modified or untracked files, use --force to delete it`.

*Non-idempotency.* Re-running the fast lane on an AC it has already built fails the same
way, against its **own** prior worktree — which is exactly what the reuse branch exists to
prevent. `git worktree list` currently shows `worktrees/bo-2900g-3` on `fast-lane/bo-2900g-3`,
so re-running `BO-2900g-3` today would abort at phase one for this reason alone. A build
tool that cannot be re-run on the same input is the more serious half of this defect; the
collision is just the loud version.

**Evidence.** Confirmed by reading the source at HEAD, not inferred from the failure.
`grep -n "refs/heads/fast-lane" templates/scripts/setup_ticket_worktree.py` returns nothing;
`_worktree_exists(slug)` is called at `:1289` (and at `:1398` in the `scripts/` build-output
copy) while `_fastlane_branch(slug)` returns `fast-lane/<slug>`. Both copies carry it —
`scripts/setup_ticket_worktree.py` is generated from `templates/`, so a fix must land in
`templates/` and be mirrored, never edited in `scripts/` alone.

**Fix direction.** Pass the full branch name and match on it, rather than reconstructing
prefixes inside the lookup — `_worktree_exists` already receives a bare slug from three
other call sites, so the low-risk shape is an optional `prefixes` argument (or a
`full_branch=` overload) with `fast-lane/` added for this caller. Two things worth deciding
at the same time, both of which this AC tree (`BO-1500f-2`) is already specifying for the
authoring path: whether a re-run should reuse the existing worktree or mint a
run-distinct one, and whether the path should carry anything beyond the AC id so two
sessions on one AC cannot resolve to the same directory. Whatever is chosen, the failure
should name the occupying path and say which of the two cases it is, instead of surfacing an
empty `worktree_path`.

**Numbering note.** Filed as KI-BO-008 while this work sat in review, then renumbered to
014, then to 015 — main published a different 008, then everything through 013, then its
own 014, across the review window. The third renumber happened *during* the second one:
main gained 014 between reading the file and writing the append. KI-BO-010 carries the
same note from an earlier round. A number reserved in a long-lived branch is not reserved;
the free number must be re-read against `origin/main` at the moment of landing, not at the
moment of drafting.

**Status update, 2026-08-25.** Specified by `BO-2400f-13` and its four children. The chosen
ending is a **named refusal**, not reuse and not a run-distinct path — see that criterion's
`notes` for the reasoning, and `KI-BO-017` below for a pre-existing defect found while
specifying it.

---
