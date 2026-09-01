---
title: The second fast-lane runner is gone, and the docs describing it were wronger than a rename
date: "2026-09-01"
time: "09:40"
type: manual
components:
  - build_orchestration
  - doc_compliance
summary: "Deletes the orphaned fast-lane runner and its grep-only test file, closes KI-BO-006 with the decision it asked for, repairs six ACs whose implemented_by pointed at the deleted file, and rebuilds three C4 diagrams whose claims about the lane turned out to be false rather than merely stale."
description: "BO-2400c-1-v completes. The removal itself is small; the sweep was not. Six done ACs had the deleted path in implemented_by — a live machine-read field, not historical prose. Three architecture diagrams asserted six load-bearing claims that were false of the running lane, and one diagram's central thesis (no LLM makes a review judgment in the fast lane) had been falsified by PR #485 without anyone updating it."
---

## Entry

`templates/workflows-js/fast-lane-build.js` was an orphaned second fast-lane runner. Nothing ever dispatched it — `/fast-lane-build` has always routed to `fast-lane-ship.js`. It is now deleted, along with `unit_tests/workflows/test_bo2400a_runner_wiring.py`, whose only assertions were that certain names appeared inside it.

The deletion is four lines of `git rm`. Everything else here is the sweep, and the sweep is where the surprises were.

### KI-BO-006 asked for a decision; this is it

The entry offered two honest options: wire the prompt-caching layer into the running lane and delete the orphan, or delete both and say plainly that prompt caching is gone. **The first was taken** — `BO-2400c-1-iii` wired the layer, and the orphan holds nothing the live lane does not. No capability was retired. Verified against a clean build: `.leafcutter/scripts/injection_builders.py` still deploys and its `assemble-bundle` CLI still executes.

The entry's own size estimate was wrong in both directions, and correcting it is the useful part. It was written by *reading* the two test files. The real number came from *deleting the orphan and running the covering tests*:

- **Overstated** — not eight criteria. Only `BO-2400a-1` and `BO-2400a-5` had sole proof there. `test_bo2400a_runner_wiring.py` held no criterion's sole proof at all.
- **Understated** — it missed a third file entirely, `test_bo2500d_gate_retirement.py`, carrying sole proof for `BO-2500d-2`.

Three ACs, not eight, and one the entry never named.

### Six records were pointing at a file that no longer exists

`implemented_by` is a live, machine-read claim that a file implements a criterion — not historical prose. Six `done` records named the deleted path: `BO-2400a-1`, `-3`, `-3-v`, `-4`, `-5`, and `BP-900g-6`. Each was re-pointed at `fast-lane-ship.js` or, where the lane was already listed, had the dead entry dropped. `BO-2400a-5` would otherwise have been left with an **empty** `implemented_by`.

This is exactly the "a dangling reference to a deleted workflow is the next KI" case the AC warns about, and it was invisible until the deletion made it so.

### The diagrams were false, not stale

Three C4 diagrams described the orphan. The expectation was a rename. What was actually there:

**`c2-fast-lane-build-path-components.md`** carried six load-bearing claims that are false of the running lane — "exactly two LLM agents", "three deterministic Python gates", "no per-ticket worktree isolation", "single shared worktree for the whole batch", "the actual `git commit` is external to the fast-lane workflow", and "PR creation: absent". The real lane has 11 happy-path dispatches plus 9 release-on-failure sites.

**`c2-fast-vs-heavy-lane-phases.md`** had its central thesis falsified. The document existed to say the fast lane relies exclusively on deterministic gates and **no LLM makes a review judgment**, listing `pr-reviewer` as heavy-pipeline-only. PR #485 added `pr-reviewer` at Phase 4.5 on explicit instruction and nobody updated the diagram. The thesis was restated rather than patched: mechanical gates first and unconditional, then one LLM review before commit. A validity constraint attributed to the orphan's `meta.description` — "must not be used when independent LLM review is required" — was removed because it **does not exist** in the live file and is now self-contradictory.

**`c3-fast-lane-build-loop-sequence.md`** was rebuilt around the real participants. The "exactly 2 LLM dispatches" claim was kept but scoped down to the inner build loop, where the live `meta.description` still says it, rather than deleted at an altitude where it is true.

### Three things found in passing, none fixed here

- **`select_batch` is now orphaned too.** The function and its CLI subcommand still exist in `fast_lane.py`; their only caller was the deleted file. The live lane uses `select_connected`.
- **No lane emits telemetry.** `agent_telemetry.py` exists and claims one record per invocation, but nothing in `fast-lane-ship.js` references it. This independently corroborates `KI-BO-012`.
- **The diagrams now exceed the complexity warning thresholds** (24, 21 and 28 against limits of 17, 16 and 25). Two of the three already warned before this change. The real lane has roughly five times the phases of the orphan, so accuracy was chosen over the threshold; the honest fix is a split, which is a restructure and belongs in its own ticket.

Also corrected: `KI-TQ-012`'s occurrence count. The fixture git-identity leak is **two** files and **six** call sites, not four in one — a third misattributed commit landed under `GE-120e-1-i fixture`, a different fixture from the one first filed.
