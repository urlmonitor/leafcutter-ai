---
title: "KI-TQ-20261009-integrity-plugin-prints-clean-while-failing-the-session — the shared-layout integrity plugin prints \"clean\" and exits 1 when a reader produced the layout after setup, and unittest-style readers have no documented way to avoid that"
description: "high — in scripts/suite_performance/shared_layout_integrity.py, _final_report() returns files_ok False when readers ran but no baseline was captured, and pytest_sessionfinish then sets exitstatus 1. pytest_terminal_summary never reads files_ok, so the same run prints `shared-layout-integrity: clean (N consumer(s) checked)`. The output shows every test passing, a clean integrity line, and exit 1. A reader reaches that branch whenever the layout first appears during its call phase: a unittest.TestCase that calls get_or_produce_shared_layout() in its body. @pytest.mark.usefixtures(\"shared_reference_layout\") avoids it but is documented nowhere. Reproduced 2026-10-09 on origin/main 5caa16ca with a one-test scratch file and a control."
type: reference
category: reference
status: active
created: '2026-10-09'
last_updated: '2026-10-09'
components:
  - testing_quality
related_docs:
  - docs/known-issues/testing-quality.md
  - docs/known-issues/README.md
  - docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-3.yaml
  - docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-5.yaml
---

# KI-TQ-20261009-integrity-plugin-prints-clean-while-failing-the-session — the shared-layout integrity plugin prints "clean" and exits 1 when a reader produced the layout after setup, and unittest-style readers have no documented way to avoid that

> **Filed, not fixed.** The plugin is under active development (TQ-600a). This entry records
> two related defects so the TQ-600a work can pick them up. Index:
> [testing-quality.md](../testing-quality.md).

- **Severity:** high. A run fails with nothing in its output pointing at the reason: every test
  passed, and the only plugin line says `clean`. That sends the reader looking for a failure that
  does not exist, and it is the "check reports one thing while doing another" shape this register
  exists for.
- **Status:** open, no AC. TQ-600a-3 ("Read-only is proved, not promised...", `work_status: done`)
  owns the plugin.
- **Occurrences:** 1 live (2026-10-08, see below) and 1 deliberate reproduction (2026-10-09).
- **First seen:** 2026-10-08 · **Last seen:** 2026-10-09
- **Where:** `scripts/suite_performance/shared_layout_integrity.py`. `pytest_runtest_setup`
  `:139-166`, `pytest_runtest_teardown` `:169-196`, `_final_report` `:199-243` (defensive branch
  `:224-237`), `pytest_sessionfinish` `:246-276` (`:275-276` sets the exit status), and
  `pytest_terminal_summary` `:279-296`.

## Defect (a): the summary line contradicts the exit status

`_final_report()` has three outcomes. With zero readers it reports `files_ok: True`. With readers
and a captured baseline it compares. With readers but **no captured baseline**
(`_captured_record is None or _shared_root is None`) it returns `files_ok: False`, and the
comment there says "Fail loudly rather than silently reporting clean over an unknown state".
`pytest_sessionfinish` then sets `session.exitstatus = 1`.

`pytest_terminal_summary` does not call `_final_report()` and does not read `files_ok`. It
prints `DIRTIED by <nodeid>` if `_offending_test` is set, otherwise
`clean (<N> consumer(s) checked)` whenever `_consumer_count > 0`. In the no-baseline branch
`_offending_test` is always None, because teardown returns early at `:192-193` before it can
compare anything. So that branch always prints `clean`, and "N consumer(s) checked" is untrue
because nothing was compared. The run does fail, but its output says the opposite of what
happened.

## Defect (b): unittest-style readers cannot request the fixture at setup, as far as the docs say

The baseline is captured in a `pytest_runtest_setup` hookwrapper, after the first
`shared_layout_reader`-marked test's setup has run (`:156-166`). It calls
`check_published(_published_path())`, which returns None if the layout has not been published
yet. A pytest-style function that takes `shared_reference_layout` as an argument produces the
layout during setup, so the baseline is captured. A `unittest.TestCase` method cannot take
fixture arguments. For a caller "outside fixture context", CLAUDE.md's shared-layout section
says to "call `get_or_produce_shared_layout()` directly". A reader that does so produces the layout in its
**call** phase, after the capture point. With one reader in the session, the baseline is never
captured, which is defect (a)'s branch.

`@pytest.mark.usefixtures("shared_reference_layout")` on the class makes pytest set the fixture
up before the method runs, so the baseline is captured. CLAUDE.md does not mention it (`grep -n
usefixtures CLAUDE.md` returns nothing), and no test in `unit_tests/` or `tests/` on main uses
it with this fixture.

**Inferred from reading, not reproduced:** with **two or more** body-producing readers, setup
for the second reader would find the layout already published and capture it then. The run would
pass, but the first reader's call phase would never be compared.

## Evidence

**Live occurrence (2026-10-08).** `unit_tests/commit_guardian/test_ge_118f.py`, class
`TestGe118fDeployedLayout`, on the GE-118f branch (not on main): `4 passed`,
`shared-layout-integrity: clean (1 consumer(s) checked)`, exit code **1**. Bisecting by file
showed that an unmarked sibling test file exited 0. Adding
`@pytest.mark.usefixtures("shared_reference_layout")` to the class made the run exit 0. That fix
is in the working copy at `worktrees/km-kgs-100d-3/unit_tests/commit_guardian/test_ge_118f.py:250-257`,
with a comment explaining why. That evidence comes from the build drive. The file itself was
checked on 2026-10-09.

**Reproduction (2026-10-09, origin/main `5caa16ca`).** Two scratch test files were written
outside the repository and run with the repository's own `pytest.ini`
(`python3 -m pytest -c <wt>/pytest.ini --rootdir <wt> -p no:cacheprovider <file> -q`, from the
worktree root):

| File | Shape | Output | Exit |
|---|---|---|---|
| no-baseline | `@pytest.mark.shared_layout_reader` on a `unittest.TestCase`, body calls `get_or_produce_shared_layout()` | `1 passed in 96.51s` · `shared-layout-integrity: clean (1 consumer(s) checked)` | **1** |
| control | same, plus `@pytest.mark.usefixtures("shared_reference_layout")` on the class | `1 passed in 83.23s` · `shared-layout-integrity: clean (1 consumer(s) checked)` | **0** |

The two runs printed the same summary line and exited differently. The only difference between
the files is the `usefixtures` line.

**Exposure on main today:** `grep -rln mark.shared_layout_reader unit_tests tests` finds only the
plugin's own three suites (`unit_tests/suite_performance/test_tq_600a_1.py`,
`test_tq_600a_1_multiworker.py`, `test_tq_600a_3_integration.py`), which write their reader tests
into scratch files. No real reader on main was found in the trap. The first real one was
GE-118f, and the trap will catch the next unittest-style reader that follows the documented
guidance.

## Detection

A pytest run that exits non-zero with no failed or errored test, and whose terminal summary
includes `shared-layout-integrity: clean`. With `LEAFCUTTER_SHARED_LAYOUT_INTEGRITY_REPORT` set,
the JSON report shows `"files_ok": false, "compared_count": 0, "had_consumers": true`. That
combination appears only in the no-baseline branch.

## Workaround

Put `@pytest.mark.usefixtures("shared_reference_layout")` next to `@pytest.mark.shared_layout_reader`
on any `unittest.TestCase` reader class.

## Fix direction

1. **(a)** Have `pytest_terminal_summary` print from the same `_final_report()` that decides the
   exit status. When `files_ok` is False with no offender, name the actual state, for example
   `shared-layout-integrity: FAILED, no baseline captured: N reader(s) ran but the layout first
   appeared after setup (request shared_reference_layout at setup, e.g. via usefixtures)`. Never
   print `clean` unless a comparison actually ran and passed.
2. **(b)** Document the `usefixtures` form in CLAUDE.md's shared-layout section, as the required
   way for a `unittest.TestCase` reader to declare itself. Or capture the baseline lazily, at the
   first moment the layout is published (for example from inside `get_or_produce_shared_layout()`),
   instead of only at reader setup.
3. Add a behavioural test for the no-baseline branch that asserts both the exit status and the
   summary text, so the two cannot disagree again.

**Pattern:** a check that decides pass/fail in one place and reports its verdict from another,
with the two reading different state.
