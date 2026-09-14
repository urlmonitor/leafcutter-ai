---
title: "EPIC: Files stay workable — the size standard explains itself and the backlog shrinks"
epic_name: EPIC-FilesStayWorkable
created: 2026-09-14
status: in_progress
components:
  - commit_guardian
  - precommit_hooks
source_ac: GE-127
depends_on: []
change_target: code
risk_surface: contract_boundary
# Considered, not needed. No new component is introduced. Every ticket modifies
# check_file_size.py, _file_size_ratchet.py or _file_description.py, all of which
# are already inside the commit-guardian family whose C4 diagram covers them.
requires_diagram: false
# Considered, not needed. The two decisions with architectural weight in this tree
# were already taken and recorded where they bind: GE-127f chose an end-state
# comparison over a removal quota, with its rationale in the record and in the
# changelog entry that shipped with it, and the separation-of-duties half was
# deliberately routed to build-orchestration (BO-3800) rather than specified here.
# An ADR restating either would be a second place for them to drift.
requires_adr: false
---
# EPIC-FilesStayWorkable

## Goal

Close out `GE-127` — "files stay workable" — by building the nine leaf ACs that are
ready today.

Three of the five L1s are already delivered and green. `GE-127a` refuses a file that
crosses the limit, `GE-127b` stops an already-oversized file getting bigger, and
`GE-127c` makes a pass distinguishable from a file the standard never looked at. What
is left is the part that makes the standard **honest and finite**:

- **`GE-127d`** — the rule an author is shown and the rule the gate enforces are checked
  against each other, and the length a file is quoted at is one the author can arrive at
  themselves. Today they cannot: `count_content_lines` strips triple-quoted regions and
  block comments but **not** `#` comments and **not** blank lines, and nothing published
  says so.
- **`GE-127e`** — the refusal arrives with enough to act on, and the help it offers is
  help that actually exists. `GE-127e-1` shipped the description engine; these four
  govern what it is allowed to promise.
- **`GE-127f`** — an addition to an oversized file must leave it **smaller**. Without it
  the ratchet freezes the backlog at 212 files and 62,524 excess lines forever.

## Build order

Nine tickets. The ordering is not cosmetic: `GE-127d-2` publishes the measurement rule
that `GE-127f-2` then counts in, and `GE-127f-1`'s comparison consumes `GE-127f-2`'s
output. Almost every ticket touches `templates/scripts/commit_guardian/check_file_size.py`,
so the file-conflict gate will serialise most of this regardless — the `depends_on` edges
exist so the *order* it picks is the correct one rather than an arbitrary one.

| # | File | Title | Source AC | Depends On |
|---|------|-------|-----------|------------|
| 01 | [01_TICKET-20260914-GE-127d-1.md](./01_TICKET-20260914-GE-127d-1.md) | The published rule and the enforced rule are checked against each other, and no fact the standard accepts about a change is left without effect on its verdict | GE-127d-1 | — |
| 02 | [02_TICKET-20260914-GE-127d-2.md](./02_TICKET-20260914-GE-127d-2.md) | The length a file is quoted at is one the author can arrive at themselves by following a published measurement rule | GE-127d-2 | 01_TICKET-20260914-GE-127d-1.md |
| 03 | [03_TICKET-20260914-GE-127e-2.md](./03_TICKET-20260914-GE-127e-2.md) | Two different oversized files are not given the same advice, and changing what is in a file changes the advice it gets | GE-127e-2 | — |
| 04 | [04_TICKET-20260914-GE-127e-3.md](./04_TICKET-20260914-GE-127e-3.md) | The refusal offers only help that actually arrives, and a bare verdict is preferred to a promise nothing keeps | GE-127e-3 | — |
| 05 | [05_TICKET-20260914-GE-127e-3-i.md](./05_TICKET-20260914-GE-127e-3-i.md) | Guidance that could not be produced is said so plainly, and whether guidance exists never moves the commit verdict in either direction | GE-127e-3-i | 04_TICKET-20260914-GE-127e-3.md |
| 06 | [06_TICKET-20260914-GE-127e-4.md](./06_TICKET-20260914-GE-127e-4.md) | Everything needed to choose arrives with the refusal, the division is offered as a starting point, and declining it costs nothing | GE-127e-4 | — |
| 07 | [07_TICKET-20260914-GE-127f-2.md](./07_TICKET-20260914-GE-127f-2.md) | What the change added is the measured lines it put into the file, not the amount the file grew, so a change that gives back what it took has still added something | GE-127f-2 | 02_TICKET-20260914-GE-127d-2.md |
| 08 | [08_TICKET-20260914-GE-127f-2-i.md](./08_TICKET-20260914-GE-127f-2-i.md) | A run that cannot establish what a change added says which situation it is in and refuses, rather than recording the change as having added nothing | GE-127f-2-i | 07_TICKET-20260914-GE-127f-2.md |
| 09 | [09_TICKET-20260914-GE-127f-1.md](./09_TICKET-20260914-GE-127f-1.md) | An addition to an already-oversized file must leave it at or below the less demanding of its permitted length and its previous length minus what the change added | GE-127f-1 | 07, 08 |

## What is deliberately NOT in this epic

**`GE-127f-3`** — the disposition half, which says a demand above some size is handed to a
restructuring specialist rather than to the author. It is `readiness: draft` on purpose and
blocked on `INF-800f`: the specialist is a slash command today, reachable by a human at a
terminal and by nothing else. Writing a machine-checked `test_spec` against a dispatch
contract that does not exist is the `BP-100k-4` mistake this store has already made once.
Its supervisor-side counterpart, `BO-3800`, is specified and six of its nine leaves are
held for the same reason.

## Two traps this epic will walk into if nobody is watching

**The gate refuses its own test files.** This has already happened twice in the `GE-127`
family — `test_ge_127c_1.py` reached 579 counted lines and was refused by the very check it
tests. It was split into four files plus a shared fixture rather than exempted, and that is
the standing answer: **do not add an exemption.** Expect it again here; several of these
tickets carry eight descriptors each.

**The fixtures hand-enumerate their production dependencies.** Both
`unit_tests/commit_guardian/_ge_127a_1_ordinary_commit_fixture.py` and
`_ge_127c_1_scope_fixture.py` copy a hand-written list of modules into their temp repos, and
nothing checks either list against the real import graph. When `GE-127e-1` added one import
to `check_file_size.py`, six descriptors went red — none of them `GE-127e-1`'s own — and the
failure surfaced as `baseline commit failed`, with the real `ModuleNotFoundError` visible
only inside a captured traceback. **If a ticket in this epic adds an import to
`check_file_size.py`, both lists must be updated in the same change.** Tracked as
`KI-TQ-20260914-test-fixtures-hand-enumerate-their-production-dependencies`.

## Verification standard for this epic

Every ticket here is a **gate** AC. Per `CLAUDE.md`, a grep-only test is not coverage for
any of them — a test that reads the source for a string passes on dead code and cannot tell
"the gate is wired and runs" from "the gate string is defined and ignored". Each descriptor
must execute the behaviour, and the red baseline must be captured with
`AC_ENFORCE_STRICT=1`, because `pytest_ac_enforcement` downgrades failures on not-`done` ACs
to xfail and a run without it will report green on work that has not been done.
