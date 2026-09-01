---
title: The orphan cannot be deleted until two test files stop pointing at it
date: "2026-09-01"
time: "00:10"
type: manual
components:
  - build_orchestration
summary: "A fast-lane coder deleted the orphaned runner, ran the full covering-test set, and measured a done-proof regression for three ACs that no prior reading had confirmed. The finding and the AC's three-test red baseline are preserved; the deletion is not made."
description: "BO-2400c-1-v's two recorded blockers were both discharged, so the lane reached its coder phase and the coder attempted the deletion for real. Running the full covering-test set rather than the AC's own three tests showed the removal regresses done-proof for BO-2400a-1, BO-2400a-5 and BO-2500d-2. The prior amendment had claimed the BO-2500d half was resolved on 2026-08-18/19 — true of the AC records, false of the test file, whose _FAST_LANE_PATH constant still names the orphan. Test migration is a hard prerequisite; test-writer must run first."
---

## Entry

`BO-2400c-1-v` removes the orphaned second fast-lane runner. Two blockers had been recorded against it and both were discharged — the `BO-2500d` half by amendment on 2026-08-18/19, the telemetry half on 2026-08-31. With the record reconciled the lane reached its coder phase, and the coder did the thing no previous pass had done: **it deleted the orphan and ran the full covering-test set**, rather than reasoning about what deletion would do.

It found a third blocker, and this one holds.

### What the measurement showed

Deleting `templates/workflows-js/fast-lane-build.js` regresses done-proof for three acceptance criteria:

- **`BO-2400a-1`** and **`BO-2400a-5`** — sole proof lives in `unit_tests/workflows/test_bo2400a_runner_structure.py`, whose 17 tests all fail file-not-found. Both are `work_status: done`.
- **`BO-2500d-2`** — `work_status: done`; five of its six covering tests target heavy-pipeline files and are unaffected, but `test_ac_d2_fast_lane_has_no_phase_order_array` uses `_FAST_LANE_PATH` and fails.

The blast radius is **narrower** than the 2026-08-18 note's worst case of six ACs, and it was corrected downward by running the suites rather than counting `# covers:` tags.

### Why a naive re-point does not work

The obvious repair — change the path constant to `fast-lane-ship.js` — was checked empirically and fails. The live lane has **20** non-comment `agent()` call sites against the orphan's exactly **2**, so `test_ac1_exactly_two_agent_calls` breaks outright. `test_ac3_red_baseline_referenced_before_coder` breaks too, because it compares raw string positions and a JSDoc mention of a coder type appears earlier in the file than the real gate call. And `select_batch`/`selectBatch` appears nowhere in the live lane.

The semantic invariant probably still holds — `testWriterResult` and `coderResult` are each single call sites — but proving it needs assertions that **count test-writer and coder dispatches specifically** and **locate gate invocations in control flow**, not a mechanical constant swap. That is test authorship, which the coder is not permitted to perform directly under Test Delegation.

### The error this corrects

The 2026-08-31 amendment asserted the `BO-2500d` half was "resolved separately when BO-2500d-1/-1-i/-3 were amended on 2026-08-18/19."

That is **true of the AC records and false of the test file**. The three records did self-correct — they are `work_status: in_progress` today, changed on 2026-08-19 for exactly this reason. But `test_bo2500d_gate_retirement.py`'s module constant `_FAST_LANE_PATH` still reads `templates/workflows-js/fast-lane-build.js`, unchanged since 2026-08-18.

Checking that the records were amended and inferring the tests followed is the whole mistake. It is the same shape as the three record-drift defects this repository fixed the previous day — the most-read surface disagreeing with the ground truth — except here the two surfaces are a *specification* and its *proof*, which is the pairing the AC store exists to keep honest.

### What is preserved here, and what is not

**Preserved:** the coder's finding as an `amended_by` entry on `BO-2400c-1-v`.

**Deliberately NOT merged: the red baseline.** `test_bo2400c1v_orphan_runner_removal.py` was authored by test-writer and holds the three tests named in the AC's `test_spec`. It cannot land on `main` yet, and the reason is a design decision rather than a defect. Locally the three report `3 xfailed`, because `pytest_ac_enforcement` masks AC-tagged failures while the AC is not `done`. **CI does not do that** — `.github/workflows/ci.yml` sets `AC_ENFORCE_STRICT: "1"` on the pytest job precisely so the masking is off, and under strict mode the same three are hard failures that block the required gate.

So a red baseline for a not-done AC is structurally unmergeable here, and that is correct: `main` should not carry known-red tests. The baseline belongs in the same change as the implementation that turns it green, which is the ordering the fast lane already uses. The file is retained on branch `spec/bo-2400c-1-v-test-migration-prerequisite` at commit `cd3de7b75` and will land with the build.

The wider lesson is about the evidence, not the file: a local `xfail` is a local convenience and proves nothing about mergeability. Only a strict-mode run answers that question, which is what `AC_ENFORCE_STRICT=1` is for.

**Not done:** nothing is deleted. The orphan and `test_bo2400a_runner_wiring.py` were restored to `HEAD` before the coder finished. `work_status` stays `todo`, `covered_by` and `implemented_by` stay empty — the criterion is not built and nothing here claims it is.

### Next

Dispatch `test-writer` to (a) migrate `test_bo2400a_runner_structure.py`'s semantic-invariant tests to assert against the live lane's real dispatch structure, and (b) re-point the one `BO-2500d-2` method. **Both before the orphan is deleted**, so all three ACs keep passing proof throughout. Everything else the criterion asks for — delete the orphan, delete `test_bo2400a_runner_wiring.py`, re-point the `build_referential_integrity.py` example comment, record the decision in `KI-BO-006` — is unblocked and mechanically small once that lands.
