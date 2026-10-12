---
title: "check-root-files no longer blocks edits to files already tracked at the repo root"
date: "2026-09-22"
time: "11:00"
type: manual
components: 
  - commit_guardian
  - ac_store
summary: "Fixed a pre-commit safeguard that was refusing to let anyone edit a file already tracked at the repository root, not just block new ones from being added; also corrected an acceptance-criteria record that had been marked done before its own prerequisite was actually finished."
description: "1 commit (e74db646). check_root_files.py's get_staged_new_files() matched git status codes A, M and R although the function and its docstrings describe an add-only check, so any pre-existing root file absent from root_files.allowed_files could never be modified again by anyone; found via a refused one-line edit to requirements-dev.txt. Fixed to match A/R only, verified behaviourally against a fixture repo (original hook exits 1 on a staged modification, fixed hook exits 0, a genuinely new unauthorised root file is still refused). Also corrects GE-120e-1's work_status from done to todo, since its child GE-120e-1-i is still todo with an empty covered_by; the false claim was corrected rather than bypassed. Adds AC GE-120e-1-ii and its test."
commits: 
  - e74db646
breaking: false
---

## Entry

### The fix: editing an existing root file no longer fails the commit

The `check-root-files` pre-commit hook is supposed to stop a NEW, unauthorised file from
being added at the repository root. Instead it was also refusing an ordinary EDIT to a
root file that was already tracked and already legitimate, as long as that file happened
to be absent from `root_files.allowed_files`. Its `get_staged_new_files()` function
matched git's `A` (added), `M` (modified) and `R` (renamed) status codes, even though the
function's own name, its docstring, and the module docstring all describe an add-only
check — the code comment next to the `M` check ("just in case") shows it was defensive
rather than deliberate.

The practical effect: any file already tracked at the root but absent from the allowlist
could never be edited again by anyone. This was found when a genuine one-line addition to
`requirements-dev.txt` — this project's real dependency file — was refused outright.

The hook now matches only `A` and `R`. Verified behaviourally against a standalone
fixture repo rather than by inspection: the original hook exits 1 naming the file on a
staged modification of a pre-existing root file, the fixed hook exits 0 on the same
fixture, and a control case confirms a genuinely new, unauthorised root file is still
refused — so the fix narrows the check rather than disabling it.

`requirements-dev.txt` is still absent from `root_files.allowed_files`; that gap is
unrelated to this fix (edits no longer need the allowlist entry) and is left for a
follow-up.

### A status correction, not new work

The same commit also flips `GE-120e-1`'s `work_status` from `done` back to `todo`.
`GE-120e-1` is a composite whose `covered_by` names two children, `GE-120e-1-i` and
`GE-120e-1-ii`. `GE-120e-1-i` is still `todo` with an empty `covered_by`, so the parent's
`done` claim was false. `check_done_proof` refused the commit on exactly that basis, and
the claim was corrected in place rather than bypassed — no hook was skipped. This is a
record correction, not a report of `GE-120e-1-i` being finished; it will go back to `done`
once that child is genuinely implemented and covered. The new AC `GE-120e-1-ii` and its
test, `unit_tests/commit_guardian/test_ge_120e_1_ii.py`, ship in this same commit.
