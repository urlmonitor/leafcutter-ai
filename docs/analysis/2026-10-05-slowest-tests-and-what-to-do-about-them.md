---
title: "The slowest tests in the suite, ranked, and what to do about each"
description: "The slowest files in the suite are the speed programme's own tests, at ~29% of measured time. The second-largest cost is not a build at all: a pure-Python YAML parse of the 4,635-file AC store, 24.68s per sweep, 13.25x cheaper with a loader this repo already uses in exactly one file."
type: explanation
status: active
created: 2026-10-05
last_updated: 2026-10-05
components:
  - testing_quality
  - build_pipeline
  - ac_store
---

# The slowest tests in the suite, ranked, and what to do about each

Part 1 of five.
[Part 2](2026-10-05-slowest-tests-and-what-to-do-about-them-2-the-speed-programmes-own-tests.md)
explains why TQ-600a's own tests are the slowest in the suite.
[Part 3](2026-10-05-slowest-tests-and-what-to-do-about-them-3-the-yaml-parser.md)
measures the AC-store parse and the loader that is 13x faster.
[Part 4](2026-10-05-slowest-tests-and-what-to-do-about-them-4-per-item-verdicts.md)
gives a per-item verdict for the top tests and files.
[Part 5](2026-10-05-slowest-tests-and-what-to-do-about-them-5-skipping-and-run-once.md)
answers "can we skip some?" and "where do N tests recompute one result?".

This builds on, and does not repeat,
[the ten-minute-target set](2026-10-05-pytest-ten-minute-target.md) (5 parts).
That set sized the *build* cost and designed CI sharding. This set reads the
individual slow tests and says what to do with each. Where the two disagree,
the disagreement is called out rather than smoothed over.

Worktree `ci/shard-pytest-suite` at `d4ee594d`, fully merged with `origin/main`.

## 1. Two findings, both uncomfortable

**The slowest files in the suite are TQ-600a's own tests** — the programme
whose entire purpose is making the suite fast. Six files under
`unit_tests/suite_performance/` hold **1,535 s across 27 tests, ~29% of all
measured time**. Part 2 explains the mechanism and it is not incompetence:
each test spawns a real child `pytest` session to observe cross-process
behaviour, and each child session produces the shared layout from scratch
because the run key is a fresh UUID per process. The fixture is
cross-process-cached by design; its own tests are the one population that
deliberately defeats the cache.

**The second finding was not in anyone's model.** The next-largest cluster is
not paying for builds at all. It is paying for **PyYAML**. Measured today on
this worktree:

| | |
|---|---|
| AC store | **4,635 YAML files**, 23.8 MB |
| glob + read every file | 0.17 s |
| parse with `yaml.safe_load` (pure Python) | **24.68 s** |
| parse with `yaml.CSafeLoader` | **1.86 s** |
| speedup | **13.25x** |

`CSafeLoader` is available in this environment. `yaml.safe_load` appears in
**44 scripts under `scripts/`**, including 26 under `scripts/ac_store/` and 30
under `scripts/commit_guardian/`. Exactly **one** file in the repo already uses
the fast loader — `scripts/render_effective_prompt.py:57` — with a comment that
states the finding and was never generalised:

```python
#: slow (~2500 files → minutes on SafeLoader, ~1s on CSafeLoader).
_YAML_LOADER = getattr(yaml, "CSafeLoader", yaml.SafeLoader)
```

Downstream, measured end to end today:

| entry point | time |
|---|---|
| `scripts/ac_store/validate_ac_schema.py docs/acceptance-criteria` | **23.16 s** |
| `scripts/ac_store/generate_ticket_from_ac.py --ac … --dry-run` | **24.00 s** |

Both are ~95% YAML parsing. `validate_ac_schema.py` is a **required CI check**
("AC store valid") and a pre-commit hook, so this is not only a test-suite
cost. Part 3 works it through.

## 2. Ranked: the top 20 files by total cost

From `/home/henzeh/tq600a1-backup/slowest.py` over 5,525 locally measured
tests. Read §4 before using the seconds.

| # | secs | tests | file | verdict |
|---|---|---|---|---|
| 1 | 423.2 | 5 | `unit_tests/suite_performance/test_tq_600a_5.py` | RESTRUCTURE |
| 2 | 343.5 | 7 | `unit_tests/suite_performance/test_tq_600a_3_integration.py` | RESTRUCTURE |
| 3 | 302.7 | 5 | `unit_tests/suite_performance/test_tq_600a_5_reporting.py` | RESTRUCTURE |
| 4 | 271.7 | 10 | `unit_tests/portability/test_bp_1500g_1.py` | OPTIMISE |
| 5 | 267.2 | 5 | `unit_tests/suite_performance/test_tq_600a_1.py` | KEEP |
| 6 | 204.0 | 7 | `unit_tests/portability/test_bp_1500g_2_i.py` | OPTIMISE |
| 7 | 148.1 | 6 | `unit_tests/portability/test_bp_1500g_1_i.py` | OPTIMISE |
| 8 | 131.1 | 7 | `unit_tests/ac_store/test_authored_test_spec_survives_generation.py` | OPTIMISE |
| 9 | 106.3 | 4 | `unit_tests/portability/test_bp_1500g_1_ii.py` | OPTIMISE |
| 10 | 99.8 | 3 | `unit_tests/suite_performance/test_tq_600a_1_i.py` | KEEP |
| 11 | 98.4 | 2 | `unit_tests/suite_performance/test_tq_600a_1_multiworker.py` | KEEP |
| 12 | 96.3 | 4 | `unit_tests/build_guards/test_acd_2100d_2_i.py` | OPTIMISE |
| 13 | 79.5 | 4 | `unit_tests/build_guards/test_bp_1500g_1.py` | OPTIMISE |
| 14 | 74.4 | 3 | `unit_tests/ac_store/test_tkt_600b_2.py` | OPTIMISE |
| 15 | 73.4 | 15 | `unit_tests/product_truth/test_uxp_300.py` | OPTIMISE |
| 16 | 72.0 | 2 | `unit_tests/build_guards/test_bp_1500g_1_i.py` | OPTIMISE |
| 17 | 67.3 | 4 | `unit_tests/portability/test_acd_2100d_3.py` | OPTIMISE |
| 18 | 67.2 | 3 | `unit_tests/build_guards/test_bp_1500g_2.py` | OPTIMISE |
| 19 | 61.3 | 4 | `tests/test_prioritize_ac_integration.py` | OPTIMISE |
| 20 | 58.8 | 3 | `unit_tests/portability/test_bp_1500g_2.py` | OPTIMISE |

Three clusters hold almost all of it:

| cluster | files | secs | share of measured |
|---|---|---|---|
| `suite_performance` (TQ-600a's own tests) | 6 | **1,534.8** | **29.1%** |
| `BP-1500g` adopter-content family | 8 | **1,007.6** | **19.1%** |
| AC-store / product-truth store sweeps | 6+ | **~410** | **~7.8%** |

Note how small the remainder is. Below rank 20 the per-file cost falls under a
minute, and the long tail is genuinely flat: top 200 tests are 92.6% of
measured time. **There is no diffuse slowdown to chase.** Three clusters, three
mechanisms, three different fixes.

## 3. Ranked: the top 25 individual tests

| # | secs | test |
|---|---|---|
| 1 | 102.9 | `…/test_tq_600a_5_reporting.py::…::test_tq600a_5_the_run_reports_how_many_tests_were_undeclared_MANUAL` |
| 2 | 101.9 | `…/test_tq_600a_5.py::…::test_tq600a_5_the_declaration_selects_the_path_not_the_file_name_or_location_MANUAL` |
| 3 | 92.8 | `…/test_tq_600a_5.py::…::test_tq600a_5_an_undeclared_test_receives_its_own_copy_MANUAL` |
| 4 | 92.5 | `…/test_tq_600a_5.py::…::test_tq600a_5_a_test_declared_a_reader_receives_the_shared_layout_MANUAL` |
| 5 | 89.3 | `…/test_tq_600a_5.py::…::test_tq600a_5_a_test_declared_a_mutator_receives_its_own_copy_MANUAL` |
| 6 | 75.8 | `…/test_tq_600a_5_reporting.py::…::test_tq600a_5_the_declared_mutator_count_and_the_undeclared_count_are_two_separate_figures_MANUAL` |
| 7 | 74.7 | `…/test_tq_600a_1.py::…::test_tq600a_1_a_selection_of_read_only_consumers_deploys_the_package_once_MANUAL` |
| 8 | 74.6 | `…/test_tq_600a_5_reporting.py::…::test_tq_600a_5_reachable_from_entry_point_MANUAL` |
| 9 | 72.4 | `…/test_tq_600a_1.py::…::test_tq_600a_1_reachable_from_entry_point_MANUAL` |
| 10 | 71.7 | `…/test_tq_600a_1.py::…::test_tq600a_1_every_consumer_receives_the_identical_layout_root_MANUAL` |
| 11 | 66.3 | `…/test_authored_test_spec_survives_generation.py::…::test_every_approved_authored_spec_reaches_its_ticket` |
| 12 | 60.7 | `…/test_tq_600a_3_integration.py::…::test_tq600a_3_the_test_that_ran_between_the_two_states_is_named_MANUAL` |
| 13 | 59.5 | `…/test_tq_600a_3_integration.py::…::…_how_many_consuming_tests_ran_between_the_two_states_MANUAL` |
| 14 | 57.0 | `…/test_tq_600a_3_integration.py::…::test_tq_600a_3_reachable_from_entry_point_MANUAL` |
| 15 | 56.7 | `…/test_tq_600a_3_integration.py::…::test_tq600a_3_a_clean_run_reports_no_added_changed_or_missing_file_MANUAL` |
| 16 | 54.4 | `…/test_tq_600a_3_integration.py::…::…_a_deliberately_dirtied_layout_is_reported_with_the_altered_file_named_MANUAL` |
| 17 | 54.2 | `…/test_tq_600a_3_integration.py::…::test_tq600a_3_bytecode_churn_is_not_reported_as_a_difference_MANUAL` |
| 18 | 50.5 | `…/test_tq_600a_1_multiworker.py::…::…_a_run_spread_across_several_workers_still_executes_exactly_one_deploy_MANUAL` |
| 19 | 50.5 | `…/test_tq_600a_1_i.py::…::…_a_worker_with_no_scheduled_consumer_produces_nothing_MANUAL` |
| 20 | 50.1 | `unit_tests/ac_store/test_acs_100i_7_store_wide_pass.py::test_commit_time_ac_check_does_not_block_an_unedited_build_record` |
| 21 | 49.7 | `unit_tests/portability/test_bp_1500d_1_i.py::…_one_session_builds_both_layouts_…_MANUAL` |
| 22 | 49.0 | `…/test_tq_600a_5_reporting.py::…::test_tq600a_5_an_undeclared_test_still_runs_and_still_passes_MANUAL` |
| 23 | 48.9 | `unit_tests/build_guards/test_bp_1500g_1_i.py::…_the_preflight_list_and_the_real_removal_list_are_identical` |
| 24 | 48.9 | `…/test_tq_600a_1_i.py::…::test_tq_600a_1_i_reachable_from_entry_point_MANUAL` |
| 25 | 47.9 | `…/test_tq_600a_1_multiworker.py::…::…_consumers_on_different_workers_receive_the_identical_root_path_MANUAL` |

**19 of the top 25 are TQ-600a's own tests.** Per-item verdicts for the top 40
are in Part 4.

## 4. What these numbers can and cannot support

State this before anyone plans against the table.

**Coverage is incomplete, and the gap is not random.** 5,525 tests were
measured locally. CI collects **~9,551**; a plain local collection reports
**7,604**. Three distinct holes:

- **Most root-level `unit_tests/test_*.py` are missing.** The second
  measurement pass was interrupted at ~22%. That is exactly where the
  build-spawning `BP-900g-8` family lives. Those tests are *known* expensive
  and are *absent* from this ranking — so the ranking under-represents the
  build-heavy root directory, not over-represents it.
- **Everything under `tests/kernel/` and `tests/knowledge/` contributes 0 s.**
  `pydantic`, `langgraph`, `langchain`, `neo4j` and `langfuse` are pinned in
  `requirements-dev.txt` and absent locally, so 163 modules failed to import at
  measurement time. They run on CI and cost real time there. Their zero here is
  "not measured", not "free".
- **Measured under agent-fleet contention.** Absolutes are inflated by an
  unknown, non-uniform factor.

**So: the ranking is trustworthy, the seconds are not, and the total is not a
suite total.** 5,272 s is the sum of what was measured. Do not quote it as the
suite's runtime; the full local run is 1:29:47 and the best observed CI run is
53m33s.

**The probes in Parts 2 and 3 are different and stronger.** They were run today
by this analysis, in-process, measuring one specific operation. They were still
taken under load, so the absolutes are upper bounds — but every claim made from
them is a **ratio measured within a single run** (CSafeLoader vs SafeLoader on
the same 4,635 files in the same process; copytree vs build in the same
script). Contention inflates both sides of a ratio, so the ratios hold.

**One correction to the prior set.** Part 3 §2 of the ten-minute-target
analysis prices "a copytree of the deployed layout" at 0.607 s and calls it
91x cheaper than a build. That is right for the **consumer-install** layout
(907 entries, 10.7 MB). It is *not* the layout the TQ-600a producer makes,
which is a self-hosted tree of **12,489 entries, 106 MB**, measured at
**2.067 s** to copy. The copy route is still overwhelmingly worth it — **23.7x**
on the measurement below — but the figure to plan with depends on which layout
is being copied, and the two differ by 3.4x.

## 5. The shape of the answer

| lever | mechanism | measured basis | where |
|---|---|---|---|
| **A. CSafeLoader across the store readers** | 24.68 s → 1.86 s per sweep | 13.25x, in-process | Part 3 |
| **B. Seed the child sessions' layout** | 48.94 s → 2.07 s per production | 23.7x, in-process | Part 2 |
| **C. Golden adopter for `BP-1500g`** | 41 identical fixture builds → 1 build + 41 copies | 41 call sites counted | Part 4 |
| **D. Memoise store-scanning subprocesses** | N identical 24 s subprocesses → 1 | 24.00 s measured | Part 5 |

None of these is a skip. Every one of them keeps every assertion and removes
only repetition. That matters here more than it would elsewhere: this repo has
shipped, by `CLAUDE.md`'s own count, **four** checks that passed having
inspected nothing. A speed fix that quietly narrows coverage would be the
fifth, and it would be found the same way the others were — late, by accident.

Part 5 takes the skipping question seriously anyway, because there is one
honest candidate and it is worth naming precisely.
