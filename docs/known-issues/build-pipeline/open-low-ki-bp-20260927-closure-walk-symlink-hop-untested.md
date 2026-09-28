---
title: "KI-BP-20260927 — the closure walk's second-hop symlink fix has no regression test, so a reintroduced `.resolve()` would only be caught by an unrelated CI failure"
description: "KI-BP-20260927 — the closure walk's second-hop symlink fix has no regression test, so a reintroduced `.resolve()` would only be caught by an unrelated CI failure"
type: reference
category: reference
status: active
created: '2026-09-27'
last_updated: '2026-09-27'
components:
  - build_pipeline
related_docs:
  - docs/known-issues/build-pipeline.md
  - docs/known-issues/README.md
---

# KI-BP-20260927 — the closure walk's second-hop symlink fix has no regression test, so a reintroduced `.resolve()` would only be caught by an unrelated CI failure

> Index: [build-pipeline.md](../build-pipeline.md).

- **Severity:** low. The defect itself is fixed; what is missing is the test that would keep it fixed.
- **Status:** open
- **Occurrences:** 1 (PR #918, 2026-09-27, CI "Test suite (pytest)": 42 failing tests, all from one aborted build)
- **Where:** `scripts/build_referential_integrity_closure.py`, `_closure_walk()`, the recursive call

**What happened.** `_closure_walk()` followed each deployed script's imports and recursed into
`candidate.resolve()`. In a tree where `install_shims` has made `scripts/commit_guardian` a symlink
into `.leafcutter/scripts/commit_guardian/`, the resolve crossed the symlink. The first hop was
already protected by `_relative_to_root_without_symlink_escape`, but every later hop was not: the
recursed script's own sibling imports came back `.leafcutter/`-prefixed, a path no deploy
declaration holds. BO-2900b-1 added the first second-level sibling import through that directory
(`_reachability_inventory.py` → `_reachability_invocation_collector.py`), and from then on every
`build.py --target-dir` run in CI aborted with `[CLOSURE GUARD] UNDEPLOYED DEPENDENCY`.

**Why no local run caught it.** The symlink only exists on Linux after an in-place self-host build.
On Windows `install_shims` copies instead of linking, and a fresh checkout has no shim at all. A
plain fresh `build.py --target-dir <tmp>` was clean on Windows, on Linux, and on the exact merged
tree. It reproduced only after an in-place `build.py` in a fresh Linux clone.

**The fix** (same PR): the walk recurses on the candidate as it was reached and dedupes on the
resolved path, so it cannot loop and never changes directory spelling mid-walk. The guard is not
widened.

**What is missing.** A test that builds a tree where `scripts/commit_guardian` is a symlink, has a
helper import a second sibling module through it, and asserts the build succeeds with the sibling
reported under `scripts/commit_guardian/`. It would need to skip on platforms without symlinks.
Until it exists, reintroducing `.resolve()` on the recursion is caught only by whichever unrelated
test next builds such a tree in CI.

**Pattern:** a path is resolved to its real location before it is turned into a
namespace-relative string. Resolving belongs in the visited-set check only. This is the second
time in this file (the first hop was fixed for BO-2900d on 2026-09-07).
