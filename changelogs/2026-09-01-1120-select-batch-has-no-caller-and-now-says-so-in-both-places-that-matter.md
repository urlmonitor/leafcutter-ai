---
title: select_batch has no caller, and now says so in both places that matter
date: "2026-09-01"
time: "11:20"
type: manual
components:
  - build_orchestration
  - ac_driven_dev
summary: "Records that select_batch has no production caller since the orphaned runner was deleted — in its own docstring so nobody deletes it as dead, and on ACD-2000b-4 so nobody builds an overlap rule onto a function nothing calls."
description: "Deleting fast-lane-build.js left select_batch with no caller. It looks like the next dead thing to remove, and it is not: its behaviour is covered by tests that execute it, and ACD-2000b-4 (active, todo) names it as the surface its overlap rule constrains. Meanwhile building that rule on it as things stand would produce a requirement that never fires. Both risks are now recorded where each reader will hit them. No behaviour changes."
---

## Entry

Deleting the orphaned `fast-lane-build.js` under `BO-2400c-1-v` left `select_batch` in `scripts/build_orchestration/fast_lane.py` with no production caller. It looks like the obvious next thing to delete. It is not, and the reasons cut both ways.

### Why it must not be deleted

Unlike the orphan it used to serve, `select_batch` is **dormant, not dead**:

- Its behaviour is covered by tests that **execute** it — `TestSelectBatchCli` in `test_fast_lane_cli.py` runs the CLI as a real subprocess, and `test_bo2400a_fast_lane.py` exercises it throughout. The deleted orphan's tests, by contrast, only asserted that certain names appeared inside it.
- **`ACD-2000b-4`** (`status: active`, `work_status: todo`) names it as *"the requirement-grain selection this rule constrains"* and requires its determinism guarantee be preserved.

`select_connected`, which the live lane does call, is **not** a replacement. It resolves one AC's connected build set; `select_batch` picks up to N ready ACs from the whole store. Different operations. The lane stopped calling it because `BO-2400f` moved from batch-mode to single-AC-mode, not because anything superseded it.

Deleting it would retire a tested capability that live planned work depends on — precisely the mistake `KI-BO-006` exists to prevent, and it would have been the third instance of that shape in two days.

### Why it must not be silently built on either

The symmetric risk is the one worth naming. `ACD-2000b-4` intends to add an overlap rule to `select_batch`. Implement it there as things stand and **the rule never fires in production**, because nothing calls that function. A real requirement, correctly built, on a surface no run reaches — phantom-done by a different route than usual.

Where the rule *should* live is a genuine open choice: batch-mode selection (`select_batch`, dormant), the lane's connected-set resolution (`select_connected`), or `build-feature.js`'s ticket batching, which is where parallel dispatch actually happens today. This change does not make that choice; it records that the choice is unmade.

### What changed

Nothing behavioural. Two annotations, placed where each reader will actually hit them:

- **`select_batch`'s docstring** — for whoever is deciding whether to delete it.
- **`ACD-2000b-4`'s `doc_links` relevance** — for whoever is deciding how to build it.

A known-issues entry was considered and skipped: the register is for defects someone must act on, and this is a standing fact about two artifacts. Recorded on the artifacts themselves, it cannot drift out of sight the way a register entry can.
