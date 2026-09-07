---
epic_name: EPIC-TrustThatAGreenCheckActuallyChecked
title: "Trust that a green check actually checked something"
type: epic
created: 2026-08-25
status: todo
depends_on: []
requires_diagram: false
requires_adr: false
change_target: code
risk_surface: contract_boundary
components:
  - ac_store
  - build_pipeline
  - commit_guardian
  - documentation_system
  - git_vcs_operations
  - precommit_hooks
  - testing_quality
  - worktree_manager
source_ac: GE-120
---
# EPIC-TrustThatAGreenCheckActuallyChecked

## Goal

This epic implements AC GE-120: Trust that a green check actually checked something. It consists of 37 ticket(s) generated from the leaf ACs beneath GE-120, assembled in topological build order with all inter-ticket dependencies derived from the AC depends_on graph.

## Tickets

| # | File | Title | Source AC | Depends On |
|---|------|-------|-----------|------------|
| 01 | [01_TICKET-20260825-GE-120a-1.md](./01_TICKET-20260825-GE-120a-1.md) | A check that could not perform its inspection reports a degraded outcome, not a clean pass | GE-120a-1 | — |
| 02 | [02_TICKET-20260825-GE-120a-1-i.md](./02_TICKET-20260825-GE-120a-1-i.md) | One unparseable input, while the check still ran, remains an ordinary pass | GE-120a-1-i | — |
| 03 | [03_TICKET-20260825-GE-120a-1-ii.md](./03_TICKET-20260825-GE-120a-1-ii.md) | A check that falls back to a weaker inspection reports its clean result as unverified | GE-120a-1-ii | — |
| 04 | [04_TICKET-20260825-GE-120a-2.md](./04_TICKET-20260825-GE-120a-2.md) | Each check declares, for itself, whether a cannot-run condition blocks or only announces | GE-120a-2 | 01_TICKET-20260825-GE-120a-1.md |
| 05 | [05_TICKET-20260825-GE-120a-2-i.md](./05_TICKET-20260825-GE-120a-2-i.md) | A check registered without a cannot-run disposition is named as a gap, never silently defaulted | GE-120a-2-i | — |
| 06 | [06_TICKET-20260825-GE-120a-3.md](./06_TICKET-20260825-GE-120a-3.md) | The AC-schema check reports a non-authoritative result when it cannot load the schema it validates against | GE-120a-3 | 03_TICKET-20260825-GE-120a-1-ii.md |
| 07 | [07_TICKET-20260825-GE-120a-4.md](./07_TICKET-20260825-GE-120a-4.md) | An inspection that resolved none of the targets it was given does not report success | GE-120a-4 | — |
| 08 | [08_TICKET-20260825-GE-120a-5.md](./08_TICKET-20260825-GE-120a-5.md) | The no-silent-pass rule is written where the next check author will find it | GE-120a-5 | 01_TICKET-20260825-GE-120a-1.md, 04_TICKET-20260825-GE-120a-2.md |
| 09 | [09_TICKET-20260825-GE-120b-2.md](./09_TICKET-20260825-GE-120b-2.md) | Checks obtain their prerequisites through one shared resolution path, not one private copy each | GE-120b-2 | — |
| 10 | [10_TICKET-20260825-GE-120b-2-i.md](./10_TICKET-20260825-GE-120b-2-i.md) | Main-checkout verdicts are unchanged by the shared resolution path | GE-120b-2-i | — |
| 11 | [11_TICKET-20260825-GE-120b-3.md](./11_TICKET-20260825-GE-120b-3.md) | Configuration and data prerequisites resolve from a separate working copy, not only importable helpers | GE-120b-3 | 09_TICKET-20260825-GE-120b-2.md |
| 12 | [12_TICKET-20260825-GE-120c-1.md](./12_TICKET-20260825-GE-120c-1.md) | A harness executes the deployed checks out of process from a real separate working copy | GE-120c-1 | — |
| 13 | [13_TICKET-20260825-GE-120b-1.md](./13_TICKET-20260825-GE-120b-1.md) | The AC-parent-covered-by check reaches the same verdict with and without the deployed-layout link | GE-120b-1 | 12_TICKET-20260825-GE-120c-1.md |
| 14 | [14_TICKET-20260825-GE-120b-1-i.md](./14_TICKET-20260825-GE-120b-1-i.md) | A working copy with no deployed layout at all still does not pass silently | GE-120b-1-i | 04_TICKET-20260825-GE-120a-2.md |
| 15 | [15_TICKET-20260825-GE-120b-4.md](./15_TICKET-20260825-GE-120b-4.md) | Every check in the manifest reaches an identical verdict from either working copy | GE-120b-4 | 09_TICKET-20260825-GE-120b-2.md, 12_TICKET-20260825-GE-120c-1.md |
| 16 | [16_TICKET-20260825-GE-120b-5.md](./16_TICKET-20260825-GE-120b-5.md) | The manual link-the-layout workaround is deleted, not left standing beside the fix | GE-120b-5 | 15_TICKET-20260825-GE-120b-4.md |
| 17 | [17_TICKET-20260825-GE-120c-1-i.md](./17_TICKET-20260825-GE-120c-1-i.md) | The harness reports its own setup failure instead of passing vacuously | GE-120c-1-i | — |
| 18 | [18_TICKET-20260825-GE-120c-2.md](./18_TICKET-20260825-GE-120c-2.md) | The harness is shown to fail against the behaviour that was actually observed | GE-120c-2 | 12_TICKET-20260825-GE-120c-1.md |
| 19 | [19_TICKET-20260825-GE-120c-3.md](./19_TICKET-20260825-GE-120c-3.md) | Every registered check is exercised by the harness, and a new check cannot opt out by omission | GE-120c-3 | 12_TICKET-20260825-GE-120c-1.md |
| 20 | [20_TICKET-20260825-GE-120c-4.md](./20_TICKET-20260825-GE-120c-4.md) | The unverified count of files that only looked clean is replaced with a measured one | GE-120c-4 | 12_TICKET-20260825-GE-120c-1.md |
| 21 | [21_TICKET-20260825-GE-120c-5.md](./21_TICKET-20260825-GE-120c-5.md) | The new verification surface is drawn as an architecture component | GE-120c-5 | 12_TICKET-20260825-GE-120c-1.md |
| 22 | [22_TICKET-20260825-GE-120d-1.md](./22_TICKET-20260825-GE-120d-1.md) | Working-copy set-up reports the outcome of every protection step it attempted | GE-120d-1 | — |
| 23 | [23_TICKET-20260825-GE-120d-2.md](./23_TICKET-20260825-GE-120d-2.md) | Set-up refuses to hand over a working copy whose protection it could not establish | GE-120d-2 | 22_TICKET-20260825-GE-120d-1.md |
| 24 | [24_TICKET-20260825-GE-120d-2-i.md](./24_TICKET-20260825-GE-120d-2-i.md) | Set-up distinguishes a never-built workspace from a broken one | GE-120d-2-i | — |
| 25 | [25_TICKET-20260825-GE-120d-3.md](./25_TICKET-20260825-GE-120d-3.md) | The set-up path locates its own helper scripts through the shared resolution facility | GE-120d-3 | 09_TICKET-20260825-GE-120b-2.md |
| 26 | [26_TICKET-20260825-GE-120d-4.md](./26_TICKET-20260825-GE-120d-4.md) | A working copy created by set-up passes the parity sweep with no manual repair | GE-120d-4 | 23_TICKET-20260825-GE-120d-2.md, 15_TICKET-20260825-GE-120b-4.md |
| 27 | [27_TICKET-20260825-GE-120d-5.md](./27_TICKET-20260825-GE-120d-5.md) | The how-to states what a prepared working copy guarantees and how to confirm it | GE-120d-5 | 23_TICKET-20260825-GE-120d-2.md, 16_TICKET-20260825-GE-120b-5.md |
| 28 | [28_TICKET-20260825-GE-120e-1.md](./28_TICKET-20260825-GE-120e-1.md) | A check that works out its own change set works out the author's change, not everything the staged tree happens to hold | GE-120e-1 | — |
| 29 | [29_TICKET-20260825-GE-120e-1-i.md](./29_TICKET-20260825-GE-120e-1-i.md) | An empty authored change set is inspected as empty, never widened back to the whole staged tree | GE-120e-1-i | — |
| 30 | [30_TICKET-20260825-GE-120e-2.md](./30_TICKET-20260825-GE-120e-2.md) | Which checks work out their own change set is read from the manifest, not from the two that were caught | GE-120e-2 | 28_TICKET-20260825-GE-120e-1.md |
| 31 | [31_TICKET-20260825-GE-120e-2-i.md](./31_TICKET-20260825-GE-120e-2-i.md) | A check whose recorded change-set source disagrees with what it actually inspects is named by running it, not by believing it | GE-120e-2-i | — |
| 32 | [32_TICKET-20260825-GE-120e-3.md](./32_TICKET-20260825-GE-120e-3.md) | The same authored content reaches the same verdict whether it is committed ordinarily or brought in alongside a mainline merge | GE-120e-3 | 28_TICKET-20260825-GE-120e-1.md, 30_TICKET-20260825-GE-120e-2.md |
| 33 | [33_TICKET-20260825-GE-120e-3-i.md](./33_TICKET-20260825-GE-120e-3-i.md) | Two arms that agree because the check said nothing at all is an inconclusive pair, not a pass | GE-120e-3-i | — |
| 34 | [34_TICKET-20260825-GE-120e-3-ii.md](./34_TICKET-20260825-GE-120e-3-ii.md) | A merge whose own resolution introduces the fault is still blocked, and no check treats a merge as grounds to skip | GE-120e-3-ii | — |
| 35 | [35_TICKET-20260825-GE-120e-4.md](./35_TICKET-20260825-GE-120e-4.md) | Undoing or replaying someone else's recorded change is treated the same way as merging it in | GE-120e-4 | 28_TICKET-20260825-GE-120e-1.md |
| 36 | [36_TICKET-20260825-GE-120e-4-i.md](./36_TICKET-20260825-GE-120e-4-i.md) | Reworking a merge after the operation record is gone still attributes only the author's part | GE-120e-4-i | — |
| 37 | [37_TICKET-20260825-GE-120e-5.md](./37_TICKET-20260825-GE-120e-5.md) | The attribution rule is written where the next check author decides how to get their diff | GE-120e-5 | 28_TICKET-20260825-GE-120e-1.md, 30_TICKET-20260825-GE-120e-2.md, 35_TICKET-20260825-GE-120e-4.md |

## Dependencies

```
GE-120a-1 (no dependencies)
GE-120a-1-i -> GE-120a-1
GE-120a-1-ii -> GE-120a-1
GE-120a-2 -> GE-120a-1
GE-120a-2-i -> GE-120a-2
GE-120a-3 -> GE-120a-1-ii
GE-120a-4 (no dependencies)
GE-120a-5 -> GE-120a-1, GE-120a-2
GE-120b-1 -> GE-120c-1
GE-120b-1-i -> GE-120b-1, GE-120a-2
GE-120b-2 (no dependencies)
GE-120b-2-i -> GE-120b-2
GE-120b-3 -> GE-120b-2
GE-120b-4 -> GE-120b-2, GE-120c-1
GE-120b-5 -> GE-120b-4
GE-120c-1 (no dependencies)
GE-120c-1-i -> GE-120c-1
GE-120c-2 -> GE-120c-1
GE-120c-3 -> GE-120c-1
GE-120c-4 -> GE-120c-1
GE-120c-5 -> GE-120c-1
GE-120d-1 (no dependencies)
GE-120d-2 -> GE-120d-1
GE-120d-2-i -> GE-120d-2
GE-120d-3 -> GE-120b-2
GE-120d-4 -> GE-120d-2, GE-120b-4
GE-120d-5 -> GE-120d-2, GE-120b-5
GE-120e-1 (no dependencies)
GE-120e-1-i -> GE-120e-1
GE-120e-2 -> GE-120e-1
GE-120e-2-i -> GE-120e-2
GE-120e-3 -> GE-120e-1, GE-120e-2
GE-120e-3-i -> GE-120e-3
GE-120e-3-ii -> GE-120e-3
GE-120e-4 -> GE-120e-1
GE-120e-4-i -> GE-120e-4
GE-120e-5 -> GE-120e-1, GE-120e-2, GE-120e-4
```

## Agent Assignments

| Agent | Tickets |
|-------|---------|
| ac-fulfillment-gate | 01, 02, 03, 04, 05, 06, 07, 09, 10, 11, 12, 13, 14, 15, 16, 20, 22, 23, 24, 25, 26, 27, 28, 29, 30, 35, 36 |
| ac-validator | 01, 02, 03, 04, 05, 06, 07, 09, 10, 11, 12, 13, 14, 15, 16, 20, 22, 23, 24, 25, 26, 27, 28, 29, 30, 35, 36 |
| architect-review | 01, 02, 03, 04, 06, 07, 09, 10, 11, 13, 14, 15, 23, 25, 26, 28, 29, 30, 34, 35 |
| architecture-diagram-author | 21 |
| commit | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37 |
| documentation-expert | 01, 02, 03, 04, 06, 07, 08, 09, 10, 11, 13, 14, 15, 16, 21, 23, 25, 26, 27, 28, 29, 30, 34, 35, 37 |
| documentation-verifier | 01, 02, 03, 04, 06, 07, 08, 09, 10, 11, 13, 14, 15, 16, 21, 23, 25, 26, 27, 28, 29, 30, 34, 35, 37 |
| pr-reviewer | 01, 02, 03, 04, 06, 07, 09, 10, 11, 13, 14, 15, 23, 25, 26, 28, 29, 30, 34, 35 |
| pull-request | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37 |
| python-coder | 01, 02, 03, 04, 05, 06, 07, 09, 10, 11, 13, 14, 15, 22, 23, 24, 25, 26, 28, 29, 30, 34, 35, 36 |
| status-checker | 04, 30 |
| test-runner | 01, 02, 03, 04, 05, 06, 07, 09, 10, 11, 12, 13, 14, 15, 17, 18, 19, 20, 22, 23, 24, 25, 26, 28, 29, 30, 31, 32, 33, 34, 35, 36 |
| test-writer | 01, 02, 03, 04, 05, 06, 07, 09, 10, 11, 12, 13, 14, 15, 17, 18, 19, 20, 22, 23, 24, 25, 26, 28, 29, 30, 31, 32, 33, 34, 35, 36 |

## Deferred red baselines — restore these when their tickets are driven

Three red-baseline test files were **removed from the branch on 2026-09-01** so the first
tranche of this epic could merge. They are not lost: restore each from the salvage commit
`98797e669` with `git checkout 98797e669 -- <path>`.

| File | Ticket | Why it was still red |
|---|---|---|
| `unit_tests/portability/test_ge_120b_2_i.py` | 10 (`GE-120b-2-i`) | Needs its own entry point `scripts/commit_guardian/ge120b2i_verify_unchanged.py`, a CLI with `capture`/`verify` subcommands. Not yet written. |
| `unit_tests/portability/test_ge_120e_2_i.py` | 31 (`GE-120e-2-i`) | 2 of 5 now pass. The remaining 3 call `build_second_working_copy()`; the harness exposes `DeployedCheckHarness.create_second_copy()`. Reconcile the name, then assess whether ticket 31 needs implementing. |
| `unit_tests/portability/test_ge_120e_4_i.py` | 36 (`GE-120e-4-i`) | Needs `GE-120e-4`'s semantics (parent discovery, `REVERT_HEAD`/`CHERRY_PICK_HEAD`). **Also carries its own fixture bug** — `_build_merge_repo()` never `mkdir`s the repo directory before running `git init` with it as `cwd`, so these 4 fail regardless of how well `GE-120e-4` is implemented. Fix the fixture first. |

**Why they had to go rather than be marked xfail.** CI sets `AC_ENFORCE_STRICT=1`, which
disables `pytest_ac_enforcement`'s masking precisely so a red baseline for a not-done AC
cannot merge (`KI-TQ-011`). Adding `xfail` markers would have worked around a deliberate
policy rather than honouring it.

**A pattern to watch when restoring them.** All three failed at least partly because a
sibling test file was authored against a *speculative* API that the implementing ticket then
named differently — `_resolve_change_set` vs `_authored_change`, `harness` vs
`_deployed_check_harness`, `build_second_working_copy` vs `create_second_copy`. Before
building the remaining tickets, reconcile the names against what has actually shipped;
each mismatch has cost a full review round to discover.

