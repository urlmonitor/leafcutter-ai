---
title: "fix(build-orchestration): AC-record writes are now atomic, and an unwritable store halts the build instead of logging and continuing"
date: "2026-08-25"
time: "16:51"
type: manual
components: 
  - build_orchestration
  - ac_store
summary: "A crash mid-write during a build run could previously erase an acceptance-criterion record entirely; the build system now writes those records safely and stops itself instead of pretending the write happened when the store cannot be written at all."
description: "BO-2400e-3 and BO-2400e-3-i (both work_status: done, implemented_by scripts/build_orchestration/fast_lane.py). _update_ac_work_status previously opened the AC YAML with open(\"w\"), which truncates at open, so any failure between open and end-of-write left a zero-byte record; the function runs three times per AC per run, including the release-on-failure path that fires when something has already gone wrong. Replaced with _atomic_write_text: write to a same-directory temp file, then os.replace, so a lock-free concurrent reader (hooks, CI gates, humans) always sees the complete old or complete new content. On failure the temp file is cleaned up (itself failure-safe) and the OSError is re-raised rather than logged-and-swallowed; the claim CLI subcommand now reads claim_build_set's success/error fields and exits 1 on failure instead of unconditionally 0 -- the load-bearing fix, since log-and-return technically satisfies the repo's error-handling policy while letting the run claim, build, and mark-done against records it never touched. Ten new behavioral tests (test_bo2400e_3_durable_write.py, test_bo2400e_3_i_unwritable_store.py) use real AC-YAML fixtures on a real filesystem and genuinely read-only temp directories rather than a patched open(). Also fixed a pre-existing defect in test_bo2400f_lifecycle.py where a comment claimed the store directory was made read-only but the code only chmod'd the target file; the chmod now covers the directory as the comment always said, with no assertion changed."
breaking: false
---

## Entry

Two acceptance criteria under `BO-2400-fast-lane-build` land here, both now
`work_status: done` with `implemented_by: scripts/build_orchestration/fast_lane.py`:

**BO-2400e-3 — "An interrupted update never destroys the work record it was
updating."** `_update_ac_work_status` opened the AC YAML file with `open("w")`,
which truncates at open, so any failure between that instant and the end of
the write left a zero-byte acceptance-criterion record. These records are the
build system's source of truth and, in this workspace, frequently untracked
while being authored — a crash mid-write was unrecoverable data loss. The
function runs three times per AC per run (claim, release, mark-done); the
most dangerous of those is the release-on-failure path, which by definition
runs when something has already gone wrong.

Replaced with `_atomic_write_text`: write to a temp file in the same
directory, then `os.replace`. A concurrent reader — hooks, CI gates, humans,
none of which hold a lock — now always sees either the complete old content
or the complete new content. One extra filesystem metadata operation (the
rename).

**BO-2400e-3-i — "A store that cannot be written is announced, and the build
does not carry on as if it had been."** On failure the temp file is cleaned
up (failure-safe, and a cleanup failure never masks the original error) and
the `OSError` is re-raised. The `claim` CLI subcommand now reads
`claim_build_set`'s `success`/`error` fields, prints the error to stderr and
returns exit 1 instead of unconditionally 0. That control-flow change is the
load-bearing part: "log at WARNING and return" satisfies the project
error-handling policy on paper while letting the run claim work it never
claimed, build it, and mark it done against records it never touched.

### Tests

Ten new tests across `test_bo2400e_3_durable_write.py` and
`test_bo2400e_3_i_unwritable_store.py` — real AC-YAML fixtures on a real
filesystem, genuinely read-only temp directories rather than a patched
`open()`, since the whole question is what the filesystem is left holding.

Also fixed a pre-existing test defect in `test_bo2400f_lifecycle.py`: its
comment said "make the store directory read-only" but the code only chmod'd
the target file. That passed for the wrong reason under the truncating write
(which needs file-level write permission) and stopped simulating anything
once the write became atomic — POSIX `rename(2)` needs write+execute on the
containing directory. The chmod now matches the comment's stated intent. No
assertion was changed.

### Verification

- `AC_ENFORCE_STRICT=1 pytest unit_tests/build_orchestration/` — 151 passed,
  4 subtests passed.
- `ruff check scripts/build_orchestration/fast_lane.py` — all checks passed.
- Mutation proof: reverting `fast_lane.py` returns exactly the same 4 tests
  to red; restoring makes them green.
- Real-artifact spot check: driving the live CLI (`claim` then `mark_done`)
  against the real store took both records through `todo -> in_progress ->
  done` — two full write cycles — and changed exactly 2 lines total, one per
  file. Durability did not cost shape preservation, which is the specific
  trap BO-2400e-4's constraints warn about.

### Worth noting

This work was started by the `/fast-lane-build` workflow, which produced the
red baseline and then timed out in its test-writer phase. Its
release-on-failure step timed out too, stranding both ACs in `in_progress` —
the exact failure shape filed the same day as `KI-BO-020`. Nothing was lost
(the claim was never committed) and the implementation was finished by hand
from the workflow's red baseline.
