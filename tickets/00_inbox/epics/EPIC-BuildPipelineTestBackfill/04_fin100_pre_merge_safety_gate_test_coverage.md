---
title: "Backfill green test coverage for FIN-100 (pre-merge-safety-gate) ACs"
status: todo
components:
  - build_pipeline
created: 2026-07-15
depends_on: []
priority: high
requires_diagram: false
requires_adr: false
test_required: true
source_ac: FIN-100a-1
ac_coverage:
  - FIN-100a-1
  - FIN-100a-2
  - FIN-100a-3
  - FIN-100b-1
  - FIN-100b-2
  - FIN-100b-3
  - FIN-100c-1
  - FIN-100c-2
  - FIN-100c-3
  - FIN-100d-1
  - FIN-100d-2
  - FIN-100d-3
  - FIN-100f-1
  - FIN-100f-2
files_touched:
  - unit_tests/workflows/test_finalize_pre_merge_safety_gate.py
  - templates/workflows-js/finalize-feature.js
  - templates/agents/test-failure-triage.md
agents:
  architect-review: not_needed
  test-writer: needed
  python-coder: not_needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# 04: Green test coverage for FIN-100 (pre-merge-safety-gate)

## Actor / Goal

As the AC store, I want every FIN-100 AC in `ac_coverage` to have a real, green unit
test that **names the AC** (`# covers: <AC>`), so its `work_status: done` is honestly
backed by verifiable coverage (per the 2026-07-14 test-truth rule).

## Test Backfill Context

**Nature: CODE_NO_TEST.** Per the 2026-07-14 audit, the finalize safety-gate logic is
fully coded in `templates/workflows-js/finalize-feature.js` +
`templates/agents/test-failure-triage.md`, but mostly untested — only a-4, e-3, g-1 are
tested today. **Do NOT rewrite the finalize logic.** Author asserting tests for the 14
CODE_NO_TEST leaves. (e-1/e-2 are NOT_IMPLEMENTED / opposite-behaviour and are excluded.)

The surfaces under test (read-only):
- `templates/workflows-js/finalize-feature.js` (Step 0 baseline capture/cleanup, Step 2
  merge, Step 3 triage + halt gate, Step 4 defensive guard, sequential ordering)
- `templates/agents/test-failure-triage.md` (pre_existing vs regression classification)

**Testing-approach call-out (important):** the classification logic in **FIN-100c-1 / c-2 /
c-3** lives in an **LLM agent prompt** (`test-failure-triage.md`), not in deterministic
JS/Python. A pure unit test cannot exercise an LLM's reasoning. Cover c-1/c-2/c-3 with a
**behavioural / replay test harness**: feed the triage agent (or a deterministic replay of
its documented decision rule) fixed `baseline_failures` + `post_merge_failures` inputs and
assert the emitted classification (pre_existing / regression / conservative-on-null) and
`blocks_finalization` value. If a live-agent harness is out of scope for this ticket, the
minimum acceptable substitute is a source-contract test asserting the prompt documents each
required classification rule verbatim — but flag that as weaker coverage in the completion
report. The remaining ACs (a-*, b-*, d-*, f-*) are JS control-flow and can be covered by
source-contract assertions over `finalize-feature.js` (or a JS-runtime harness where feasible).

## What each test must assert

Read each AC's `criteria` in
`docs/acceptance-criteria/build_pipeline/FIN-100-pre-merge-safety-gate/<AC>.yaml`. Summary:

- **FIN-100a-1** — Step 0 creates a temp detached worktree at origin/main, runs the suite,
  records baseline_sha + baseline_failures (file::test) + baseline_run_at, removes the
  worktree, forwards baseline to triage.
- **FIN-100a-2** — Step 0 degrades gracefully on failure: baseline_failures=null, logs a
  warning, does NOT halt (continues to Step 1); triage then treats all failures as regressions.
- **FIN-100a-3** — the temp baseline worktree is removed on every exit path (success or any
  early halt); no stale `/tmp/leafcutter-main-baseline-*` dirs remain.
- **FIN-100b-1** — clean `git merge origin/main --no-commit --no-ff` yields combined state,
  no merge commit, proceeds to Step 3, merge_strategy="merged_main".
- **FIN-100b-2** — conflict path runs `git merge --abort`, returns halted (step 2,
  reason="merge_conflict"), cleans up baseline worktree, does NOT merge the PR.
- **FIN-100b-3** — already-up-to-date (`merge-base --is-ancestor` exit 0) skips merge,
  merge_strategy="already_up_to_date", proceeds to Step 3, no `git merge` run.
- **FIN-100c-1** — tests failing in BOTH baseline and post-merge → classified "pre_existing";
  do NOT block (blocks_finalization stays false); listed in pre_existing array.
- **FIN-100c-2** — tests failing post-merge but absent from baseline → "regression";
  blocks_finalization=true; every new id in regressions array.
- **FIN-100c-3** — null baseline → all post-merge failures "regression"; blocks_finalization=
  true; summary notes conservative classification.
- **FIN-100d-1** — blocks_finalization=true halts immediately (status halted, step 3,
  reason="test_regression") with full triage_report + raw output + fix-and-rerun message;
  Step 4 never reached.
- **FIN-100d-2** — blocks_finalization=false marks Step 3 complete, proceeds to Step 4;
  triage_report preserved for Step 6.
- **FIN-100d-3** — defensive guard at Step 4 catches blocks_finalization=true that bypassed
  Step 3: halted (step 4, reason="test_regression"), message states "Defensive guard
  triggered", PR not merged, baseline cleanup runs.
- **FIN-100f-1** — Step 4 (PR merge) is structurally unreachable when Step 3 halt fires:
  Step 3 uses an early `return`; Step 4 code is physically after it in source.
- **FIN-100f-2** — strictly sequential await ordering: Step 2 before 3 before 4; no
  `parallel()` for those steps.

## Acceptance Criteria

For each AC in `ac_coverage`: a green test names it (`# covers: <AC>`) and asserts its
behaviour/contract; its `covered_by` records the test path (`::test_function`);
`work_status: done` only after green (mark-done is a follow-up).

## Test Requirements

```yaml
tests:
  - name: test_finalize_pre_merge_safety_gate
    file: unit_tests/workflows/test_finalize_pre_merge_safety_gate.py
    covers: [FIN-100a-1, FIN-100a-2, FIN-100a-3, FIN-100b-1, FIN-100b-2, FIN-100b-3, FIN-100c-1, FIN-100c-2, FIN-100c-3, FIN-100d-1, FIN-100d-2, FIN-100d-3, FIN-100f-1, FIN-100f-2]
    asserts: >
      Each listed AC has at least one green test naming it. a-*/b-*/d-*/f-* assert the
      finalize-feature.js control-flow branch, halt/return placement, cleanup, or ordering
      required by the criteria. c-1/c-2/c-3 assert the triage classification via a
      behavioural/replay harness (fixed baseline+post-merge inputs → expected
      classification + blocks_finalization), or, as a weaker fallback, a source-contract
      assertion over test-failure-triage.md.
```

## Sign-offs

- [ ] test-writer
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments
