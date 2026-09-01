---
title: Two suites stop proving things about a file nobody runs
date: "2026-09-01"
time: "08:30"
type: manual
components:
  - build_orchestration
  - testing_quality
summary: "Migrates test_bo2400a_runner_structure.py and one method of test_bo2500d_gate_retirement.py off the orphaned fast-lane runner and onto the lane that actually executes, so the orphan can be deleted without three done ACs losing their proof."
description: "A blunt path swap does not work: the live lane has ~20 agent() call sites against the orphan's 2, and the ordering assertion compared raw string positions where a JSDoc mention precedes the real gate call. The count assertion becomes one-test-writer-and-one-coder anchored on unique dispatch labels; the ordering assertion strips comments and anchors on the dispatch label. One BO-2500d-2 method moves; the in_progress siblings deliberately stay on the orphan."
---

## Entry

`templates/workflows-js/fast-lane-build.js` is an orphaned second fast-lane runner. Nothing invokes it — `/fast-lane-build` routes to `fast-lane-ship.js`. `BO-2400c-1-v` deletes the orphan, and the measurement recorded in the previous change showed the deletion would strip the sole proof from three ACs. This is that prerequisite.

### The path swap that does not work

The obvious repair is to re-point the path constants. It fails, because the two files are not shaped alike.

`fast-lane-ship.js` has roughly **20** non-comment `agent()` call sites — worktree, resolver, producibility, claim, context-bundle, test-writer, coder, review, changelog, commit, PR, plus release retries. The orphan had exactly **two**. So `test_ac1_exactly_two_agent_calls` fails outright.

The ordering assertion fails for a subtler reason. It compared raw string positions across the whole file, and on the live lane that gives a **false** answer:

| probe | raw position |
|---|---|
| `content.find("python-coder")` | 832 |
| `content.find("verify_red_baseline")` | 952 |

So the un-migrated assertion reports the coder first — while real control flow is correct (comment-stripped: red-baseline at 336, coder dispatch at 28512). The early match is a JSDoc mention plus the `RELEASE_EXECUTOR_AGENT_TYPE` constant.

### What replaced them

The count assertion became `test_ac1_single_test_writer_and_single_coder_dispatch`. The invariant worth keeping was never "exactly two `agent()` calls" — it is **one test-writer dispatch and one coder dispatch, neither multiplied by batch size N**. It now counts the unique anchors `label: "test-writer-connected"` and `label: "coder-connected"`, each asserted `== 1`, both verified to occur exactly once.

The ordering assertion now strips comment and JSDoc lines and anchors the coder side on the dispatch label rather than the bare substring `"python-coder"`, which appears twice more as decoys.

`select_batch` appears **nowhere** in the live lane; it resolves the connected build set via `fast_lane.py select_connected` — the same functional role under a different name. The assertion was broadened to accept both, with the judgment recorded in the test's own docstring rather than left implicit.

### The restraint on BO-2500d

Only **one** method moved: `test_ac_d2_fast_lane_has_no_phase_order_array`, the file's sole `done` AC. `_FAST_LANE_PATH` still points at the orphan for the `BO-2500d-1`/`-1-i`/`-3` tests, which are `in_progress`. `BO-2500d-1` asserts the fast lane contains no LLM review agent, and the live lane deliberately dispatches `pr-reviewer` at Phase 4.5 (PR #485, on explicit instruction) — re-pointing those would fail on a design decision rather than a defect.

### Nothing weakened, one thing named

No assertion was relaxed, skipped, xfailed, or re-aimed at a file that merely contains the same string. `BO-2400c-1-v` prohibits all four by name.

`test_ac5_not_three_command_three_worktree_pattern` passes **vacuously** on the live lane — its regex wants snake_case `worktree_path` while the lane uses `worktreePath`, so the only matches are output-field keys. It is documented in its own docstring as proving nothing rather than left looking like coverage. Strengthening it was out of scope.

### Proof

The decisive run is the one with the orphan **absent** — green with it present proves nothing. Orphan moved aside, both suites re-run under `AC_ENFORCE_STRICT=1` (CI's setting, which disables xfail-masking): **17 passed** for the structure file, and the migrated `BO-2500d-2` method passed. Orphan restored, `git diff -- templates/workflows-js/` empty, `ruff check` clean.
