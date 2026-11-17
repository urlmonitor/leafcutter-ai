---
title: "KI-BO-20261102-fast-lane-green-gate-cannot-see-uncommitted-code — the fast lane's green gate runs before the commit, so a test that builds the package from HEAD always tests the old code and the run halts"
description: "high — fast-lane-ship.js runs verify_green_and_coverage on the uncommitted working tree and commits only afterwards; the BP-1500d harnesses build the package with git archive HEAD, so every AC whose tests use them reads green=false and halts with no PR, however correct the code is."
type: reference
category: reference
status: active
created: '2026-11-02'
last_updated: '2026-11-02'
components:
  - build_orchestration
related_docs:
  - docs/known-issues/build-orchestration.md
---

# KI-BO-20261102-fast-lane-green-gate-cannot-see-uncommitted-code — the fast lane's green gate runs before the commit, so a test that builds the package from HEAD always tests the old code and the run halts

- **Severity:** high. Every AC whose tests build the package through the shared out-of-package
  harness cannot pass the fast lane. The run halts after the coder, releases the AC to todo and
  opens no PR, however correct the code is.
- **Status:** open. No AC.
- **Occurrences:** 1 (`/fast-lane-build BP-1500d-2`, run `wf_43478e06-640`, 2026-11-02)
- **First seen:** 2026-11-02 · **Last seen:** 2026-11-02
- **Where:** `templates/workflows-js/fast-lane-ship.js` at origin/main `df03a5682`: the green gate
  at `:1312` runs before the review (`:1496`) and the commit (`:1777`).
  `unit_tests/portability/_bp1500d1_harness.py` (`git archive HEAD`, `:265`) and
  `unit_tests/portability/_bp1500d1i_harness.py` build the producing package from the last commit.

## Symptom

The coder finished BP-1500d-2. `verify_green_and_coverage` answered `green=false, coverage_ok=true`
with 5 of the 6 new tests red. The tests had built the package from `HEAD`, which was still
origin/main, so they checked the code from before the change. After a hand commit the same tests
passed on Windows and on Linux (Docker, CI image).

## Why

The harness archives `HEAD` on purpose: its docstring records `git archive $(git stash create)` as
evaluated and not adopted, because it misses untracked files and changes a shared fixture. The
fast lane commits only after every gate, so at gate time `HEAD` never holds the change.

## Workaround

Commit the work in the workspace through the commit agent, re-run the tests against the commit,
then do the remaining steps (review, changelog, wrong-version runs, `mark_done`, PR) by hand.

## Suggested fix

1. **Commit before the green gate** on the lane branch (a local work-in-progress commit the final
   commit amends or follows), so `HEAD` holds the change when the gate runs.
2. Or let the harness take the ref to archive from an environment variable that the gate sets to a
   temporary commit of the working tree (`git stash create` plus the untracked test files).
