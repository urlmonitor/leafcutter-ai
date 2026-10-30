---
title: "KI-TQ-20261030-test-designer-trap-fixture-has-no-reference-test — the pre-pass report of the test-designer new-behaviour row names no neighbouring test file, so a designer that follows its template blocks and the trap row fails designer_design_written"
description: "low — the TQ-200d-3 new-behaviour row (TDE-9703, 'export the report as CSV') declares only scripts/report_export.py as to_be_created, so the template requires a convention_test_file the designer opened. design_prepass.py run on the fixture reports reference_files: [] (only it_requirements.reference_file_path or, under the 'reference file pending' marker, same-suffix source siblings are listed) and test_dirs unit_tests/scripts with exists: false (the test dir is derived from the declared file's parent directory name, while the fixture keeps its neighbour at unit_tests/reporting/existing_reporting.py.recorded). The pre-pass never lists the files inside a test dir and the dispatch input adds none, so under the search ban the designer cannot reach the neighbour and is told to report blocked. Live run 2026-10-30: status blocked, no design, designer_design_written failed; three other live runs (2026-10-29, 2026-10-30) passed. A correct, rule-following agent can score the trap row falsely red."
type: reference
category: reference
status: active
created: '2026-10-30'
last_updated: '2026-10-30'
components:
  - testing_quality
related_docs:
  - docs/known-issues/testing-quality.md
  - docs/known-issues/README.md
  - docs/known-issues/testing-quality/open-low-ki-tq-20261025-test-designer-eval-residual-gaps.md
---

# KI-TQ-20261030-test-designer-trap-fixture-has-no-reference-test — the new-behaviour row's pre-pass report names no neighbouring test, so a rule-following designer blocks

> Filed 2026-10-30. Index: [testing-quality.md](../testing-quality.md).
> Filename severity is the three-level index bucket (`low`); the original grading is the
> `**Severity:**` line below.

- **Severity:** low. One eval row (the new-behaviour trap of the test-designer set) can fail on a
  correct agent, so a live test-designer score can be falsely red. The eval is local only and
  user-triggered; no gate reads it. Recorded gold scoring is unaffected.
- **Status:** open, no AC.
- **Occurrences:** 1 (live test-designer eval run, 2026-10-30). The same row passed in three other
  live runs on 2026-10-29 and 2026-10-30.
- **First seen:** 2026-10-30 · **Last seen:** 2026-10-30
- **Where** (line numbers on `fastlane/tq-500f-2-ii`, on top of `d62440669`):

| Part | Site | What it does |
|---|---|---|
| Fixture record | `scripts/evals/sets/test-designer/projects/new-behaviour/eval_store/TDE-9703.yaml` | One declared file, `scripts/report_export.py`, `state: to_be_created`; no `it_requirements.reference_file_path`, no `hold_reason`, no `test_spec`. |
| Fixture neighbour | `scripts/evals/sets/test-designer/projects/new-behaviour/unit_tests/reporting/existing_reporting.py.recorded` (and `__init__.py`) | The only test-shaped file in the project. It sits under `unit_tests/reporting/`, and the fixture has no `scripts/` directory at all. The `.py.recorded` suffix is kept in the sandbox: `build_sandbox` copies the fixture as is (`scripts/evals/produced_tests_runs.py`:120); only gold outputs are renamed (`place_outputs` :170-172). |
| Test dirs | `named_test_dirs` (`scripts/ac_store/design_prepass.py`:131-144, :139-143) | Derives one test dir per declared file as `<test-root>/<name of the file's parent directory>`, so `scripts/report_export.py` gives `unit_tests/scripts`, which the fixture does not have: `exists: false`. `unit_tests/reporting` is never named. |
| Reference files | `reference_files` (`design_prepass.py`:121-128), `_candidates` (:106-118) | Lists only `it_requirements.reference_file_path` and, for a record with `hold_reason: reference file pending` (:126), up to ten same-suffix siblings of the deliverable in the deliverable's own directory. TDE-9703 has neither, so the list is empty. Even with the marker, the candidates are source siblings under `scripts/`, never test files. |
| Test files | (none) | The pre-pass never lists the files inside a test dir, so no neighbouring test file can appear in the report under any record shape. |
| Dispatch input | `build_dispatch_input` (`scripts/evals/designer_eval/dispatch.py`:37-50) | Sends the row input, the record id, the verbatim pre-pass stdout (:26-34) and `ac_store_path`; it names no test file. |
| Template rules | `templates/agents/test-designer.md`:119-123, :125-128, :67-73, :452-454 | `target_dir` must come from the report's test_dirs; a clause about code that does not exist yet must cite in `convention_test_file` an existing neighbouring test file that was opened; the search ban forbids finding a file the report does not name ("a gap to report, not something to hunt for"); a record that cannot be grounded in the pre-pass report is reported `blocked`. |

Reproduced 2026-10-30 by copying each fixture project to a scratch directory and running
`design_prepass.py --ids <id> --store-root <copy>/eval_store --repo-root <copy>` from the copy, as
`dispatch.py` does. For TDE-9703 the report is:

```json
{"batch": ["TDE-9703"], "records": [{"id": "TDE-9703",
  "declared_files": [{"path": "scripts/report_export.py", "state": "to_be_created"}],
  "reference_files": [],
  "test_dirs": [{"exists": false, "path": "unit_tests/scripts"}]}]}
```

TDE-9701 (bug fix) and TDE-9702 (gate) get the same empty `reference_files` and the same
`unit_tests/scripts` with `exists: false`, but their declared files exist
(`scripts/refresh_gate.py`, `scripts/trade_gate.py`), so the template asks for no
`convention_test_file` there and those rows are not hit. Only the new-behaviour row has a
to_be_created code file.

The recorded gold design for the row
(`scripts/evals/sets/test-designer/recorded/new-behaviour/files/eval_store/TDE-9703.yaml`) cites
`convention_test_file: unit_tests/reporting/existing_reporting.py.recorded` and
`target_dir: unit_tests/reporting/`, neither of which the pre-pass report names. The passing live
runs most likely did the same, reaching the file from outside the report; their transcripts were
not re-read for this entry.

## Symptom

The test-designer live eval's `new-behaviour` row fails `designer_design_written` because the
agent returned `status: blocked` and wrote no design. From the 2026-10-30 session log:

> The only declared file (scripts/report_export.py) is to_be_created, and the pre-pass report lists
> no reference_files and a non-existent test directory (unit_tests/scripts), so no existing
> neighbouring test file is available to ground the required convention_test_file citation. The
> search ban forbids discovering one outside the pre-pass report.

That is the template's own rule applied correctly. The row passes only when the agent steps
outside the report, so the trap row's result depends on whether the agent bends the search ban,
not on whether it leaves must_catch off new behaviour.

## Detection

A `new-behaviour` row whose only failing assertion is `designer_design_written`, with a reply of
`status: blocked` that names `convention_test_file`, `reference_files` or `unit_tests/scripts`, is
this issue. `designer_states_neither` and `designer_record_schema_valid` usually pass on such a run,
since the untouched fixture record carries no must_catch.

## Workaround

Read a blocked `new-behaviour` row by hand. If the reason is the missing neighbouring test, count
the run as a fixture failure, not an agent failure, and re-run the row.

## Suggested fix

Directions only; nothing here is applied.

- **Fixture:** give the project a neighbouring test the pre-pass reports. Move the neighbour to the
  directory the pre-pass derives, `unit_tests/scripts/`, and give it a name that is not collected
  (for example `existing_reporting.py` or keep `.py.recorded`; the guard
  `unit_tests/evals/tq200d4/test_tq200d4_fixture_layout.py`:13 forbids `test_*.py`, `*_test.py`
  and `conftest.py` anywhere under `scripts/evals/sets/`). Then make the file itself appear in the
  report, for example by setting `it_requirements.reference_file_path` on TDE-9703 to it, which
  `reference_files` lists with `exists: true`. Note that `reference_file_path` belongs to the
  file-findings group and is judged against the deliverable's type and area, so this borrows the
  field.
- **Dispatch:** alternatively have `build_dispatch_input` name the neighbour from a row field (for
  example `expected.convention_test_file`). This widens the gap between the eval's input and
  plan-feature.js `dispatchTestDesign` that OQ-13 accepts.
- **Pre-pass (product):** the gap is not specific to the eval. For any to_be_created record the
  pre-pass names no test file, so the designer reaches a convention test only when the record
  happens to carry `reference_file_path` or the agent breaks the search ban. Listing the files of
  each existing test dir (or a same-area test candidate) in the report would close it for both the
  pipeline and the eval; that needs its own AC.

**Related.** `KI-TQ-20261025-test-designer-eval-residual-gaps` is the same eval's scoring gaps;
this entry is a fixture and pre-pass gap of the same set.

**Pattern:** an eval fixture whose required evidence is reachable only by breaking the rule the
agent is scored under, so the rule-following run fails and the rule-bending run passes.
