---
title: "KI-BO-20261014-fast-lane-dependency-walk-omits-a-prerequisites-children — when the fast lane pulls in a not-done L2 prerequisite through depends_on, it adds the L2 alone and never its children, then marks it done and reports all_done, leaving a done composite over an unbuilt child"
description: "high — resolve_connected_build_set() walks depends_on with a level-based _is_leaf: an L2 or L3 prerequisite is added as a single id (fast_lane.py:251-254) and only L0/L1 prerequisites are expanded through traverse_ac_tree (:255-261), which is the only path that follows covered_by. So a prerequisite L2's own children never enter the set. mark_done_built_acs flips every covered built id without looking at children, and check_no_stale_todo checks only the built ids, so the run reports all_done. Observed in the GE-127g-5 lane on 2026-10-14: GE-127g-2 was marked done while its child GE-127g-2-i was unbuilt. Reproduced read-only against the current store; --exclude-structural-parent plays no part."
type: reference
category: reference
status: active
created: '2026-10-14'
last_updated: '2026-10-14'
components:
  - build_orchestration
  - ac_store
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/known-issues/README.md
  - docs/acceptance-criteria/guardrail-engine/GE-127-files-stay-workable/GE-127g-2.yaml
  - docs/acceptance-criteria/guardrail-engine/GE-127-files-stay-workable/GE-127g-5.yaml
---

# KI-BO-20261014-fast-lane-dependency-walk-omits-a-prerequisites-children — the fast lane marks a prerequisite L2 done without building its children

> Filed 2026-10-14 from the GE-127g-5 lane. Index: [build-orchestration.md](../build-orchestration.md).
> Filename severity is the three-level index bucket (`high`).

- **Severity:** high. Phantom-done produced by the tool: a composite is written `work_status: done`
  over a `todo` child, and the run's own stale-todo guard reports success. This is the
  falsely-done-composite shape `CLAUDE.md` describes for `ACD-400a`, made by the lane rather than by
  an author.
- **Status:** open, no AC.
- **Occurrences:** 1 (GE-127g-5 fast lane, 2026-10-14). Reconciled afterwards with
  `mark_ac_done.py --test-root` in `8d9aea24e` (GE-127g-2 set back to `in_progress`). GE-127g-2-i was
  built later in its own lane (`9c5d72876`).
- **First seen:** 2026-10-14 · **Last seen:** 2026-10-14
- **Where:**
  - `scripts/build_orchestration/fast_lane.py:232-235`: step 1, the aimed-at AC's subtree, through
    `traverse_ac_tree`, which does follow `covered_by`.
  - `fast_lane.py:237-261`: step 2, the `depends_on` closure. For each not-done prerequisite,
    `_is_leaf(dep_rec)` (`:251`) decides. True means the prerequisite is added as one id
    (`:252-254`). Only when it is false is `traverse_ac_tree` called (`:255-261`).
  - `scripts/ac_store/scan_ac_store.py:155-164`: `_is_leaf` returns True for any `L2` or `L3`, whatever
    its `covered_by` holds (imported through `scripts/build_orchestration/_fl_common.py:81-87`).
  - The worklist then re-expands only the added id's `depends_on` (`fast_lane.py:245`), never its
    `covered_by`. A child links to its parent through the child's own `depends_on`, so nothing walking
    from the parent reaches it.
  - `scripts/build_orchestration/_fl_lifecycle.py:476-528` (`mark_done_built_acs`): flips every built id
    whose coverage gate passed. It does not look at children. `:531-578` (`check_no_stale_todo`)
    checks only the built ids, so `all_done` is true (`fast_lane.py:563-580`).

## What happened

The lane was aimed at GE-127g-5, whose `depends_on` is `[GE-127g, GE-127g-1, GE-127g-2]`. GE-127g-2
was a not-done L2 whose `covered_by` listed GE-127g-2-i on the store as it stood at the time
(unchanged since `044459c67`, 2026-10-09). The lane built GE-127g-5 and GE-127g-2, marked both done and
reported `all_done: true`. GE-127g-2-i was never in the set.

## Reproduced (read-only, 2026-10-14, origin/main `95961b718`)

`resolve_connected_build_set("GE-127g-5", ...)` was run against the current store with the loader
patched in memory so that GE-127g-2, GE-127g-2-i and GE-127g-5 read as `todo`. No file was written.

```text
exclude_structural_parent=True:  ['GE-127g-2', 'GE-127g-5']
exclude_structural_parent=False: ['GE-127g-2', 'GE-127g-5']
```

GE-127g-2-i is missing either way. The `--exclude-structural-parent` flag the lane always passes
(`fast-lane-ship.js:1007-1009`, BO-2600b-1) only skips a `depends_on` entry that is the expanding
node's own structural parent (`fast_lane.py:247-248`). Here that skips GE-127g, which is correct and
irrelevant. The flag's docstring (`:184-195`) says the aimed-at AC's own children always enter through
the subtree step. That is true, and it is why the gap shows only for a prerequisite's children.

## Detection

After a fast-lane run, for every id in `marked_done`, check that each id in its `covered_by` is
`done`. No existing command does this for a run's output. Read each built record's `covered_by` by
hand, or run `mark_ac_done.py` on it: that script refuses `done` over an unfinished child, which is
how this occurrence was noticed. A built L2 whose `covered_by` is non-empty is the case to check.

## Workaround

Reconcile with `mark_ac_done.py --test-root`, which refuses `done` over an unfinished child, and set
the composite back to `in_progress`. Then build the child in its own lane.

## Suggested fix

1. **Expand a prerequisite's subtree, not just the prerequisite.** In step 2, call
   `traverse_ac_tree(dep, ...)` for every not-done prerequisite, leaf-level or not. It already emits an
   L2 and then its L2/L3 descendants (`scan_ac_store.py:540-546`), which is what step 1 does for the
   aimed-at AC.
2. **Refuse done over an unfinished child at mark time.** `mark_done_built_acs` should apply the same
   child check `mark_ac_done.py` applies, so a set that is wrong for any reason cannot write a falsely
   done composite.
3. **Make `check_no_stale_todo` look one level down.** A built id whose `covered_by` holds a not-done
   child is stale, whether or not the child was in the set.
4. Add a test: a target that depends on a not-done L2 that has a not-done L3 child must resolve to all
   three ids.

**Pattern:** two walks over the same tree with different ideas of where a node's work ends. The
subtree walk follows `covered_by`. The dependency walk stops at the first L2.
