---
title: "KI-ACD-20260927-repo-anchor-picks-the-in-repo-install-copy — in the self-hosting layout, /plan-feature's repository-anchored resolution runs the gitignored .leafcutter/ copy inside the repo, not the install the session is running, so one run mixes two builds"
description: "high — the KI-ACD-004 fix turned a loud failure into a silent one. _buildRepoRootResolutionSnippet() finds the repo one level down and uses <repo>/.leafcutter/scripts/, a gitignored build output nothing keeps current, while the workflow itself runs from the workspace parent's .leafcutter/. Code verified at main 93bd801c; file dates are machine observations."
type: reference
category: reference
status: active
created: '2026-09-27'
last_updated: '2026-09-27'
components:
  - ac_driven_dev
related_docs:
  - docs/known-issues/ac-driven-dev.md
  - docs/known-issues/ac-driven-dev/resolved/resolved-blocker-ki-acd-004.md
  - docs/architecture/adrs/ADR-001-self-hosting-boundary.md
  - docs/reference/plan-feature-layout-and-startup-checks.md
---

# KI-ACD-20260927-repo-anchor-picks-the-in-repo-install-copy — in the self-hosting layout, /plan-feature's repository-anchored resolution runs the gitignored .leafcutter/ copy inside the repo, not the install the session is running, so one run mixes two builds

- **Severity:** high. Silent wrong behaviour. In the ADR-001 self-hosting layout, every `/plan-feature` run executes support scripts from a build that may be weeks older or newer than the workflow calling them. Nothing reports which copy ran. Limited to the self-hosting layout: an adopter's repo-root `.leafcutter/` is its install, so there is only one copy.
- **Status:** open. No AC. `ACD-2100a-1`'s criteria (`done`) specify the current behaviour: *"Then the copy that executes is the one inside the repository being operated on"*. A fix therefore amends that AC.
- **Occurrences:** 1 (`/plan-feature` run `wf_734389cf-248`, 2026-09-25; session observation)
- **First seen:** 2026-09-25 · **Last seen:** 2026-09-25
- **Where:** `templates/workflows-js/plan-feature.js:2091-2124` (`_buildRepoRootResolutionSnippet`), consumed by `buildRepoAnchoredResolutionCommand()` (`:2156-2168`, worktree setup via `resolveRepoAnchoredScriptPath`, `:2242`, called at `:2478`) and `buildPauseStoreCommand()` (`:2207`).

## Mechanism (verified in code)

Session cwd is the workspace parent (`C:\Users\Hendrik\Code\leafcutter`), which is not a git repository. Step 1 (`git rev-parse --git-common-dir`) is empty. Step 2 probes `for d in */` and finds `leafcutter-ai/`, so `REPO_ROOT=<parent>/leafcutter-ai`. The command then uses `SCRIPT="$REPO_ROOT/.leafcutter/scripts/setup_ticket_worktree.py"` (`:2160`) and, for pause-store, `$REPO_ROOT/.leafcutter/scripts/pause_store.py` plus `STORE_DIR=$REPO_ROOT/.leafcutter/paused_runs`.

`leafcutter-ai/.leafcutter/` is gitignored (`.gitignore:3`, confirmed with `git check-ignore -v`). It is refreshed only when someone happens to build into it. The workflow the session runs is loaded from the workspace parent's install. So a single run takes its workflow from one build and its scripts from another.

## Machine observations (not reproducible from the repo)

- During run `wf_734389cf-248` (2026-09-25), the session recorded `leafcutter-ai/.leafcutter/workflows/plan-feature.js` as dated 2026-09-09 and the parent's `.leafcutter/workflows/plan-feature.js` as 2026-09-24. The run resolved `setup_ticket_worktree.py` from the 2026-09-09 tree.
- On 2026-09-27 the inner tree is dated 2026-09-25 09:31 local. It was rebuilt after the run, and the parent's is 2026-09-24. They still differ: `diff -rq .leafcutter/scripts leafcutter-ai/.leafcutter/scripts` reports e.g. `changelog/__init__.py` differing and `background_worker*` present only in the parent. Which copy is newer changes over time. The defect is that the selection does not depend on it.

## How this differs from KI-ACD-004

`KI-ACD-004` (resolved 2026-09-14) was the cwd-relative path selecting the **parent's** copy, whose `_git_toplevel()` then failed with exit 128. That was loud, and nothing ran. The fix anchored resolution to the repository, and in this layout that selects the **in-repo** copy. The script now finds git and succeeds, so the wrong-copy class moved from "fails" to "runs the wrong build". `test_acd_2100a_1.py:453` (`test_worktree_step_runs_the_in_repo_copy_from_an_untracked_cwd`) asserts the in-repo copy wins. That is right for a fixture whose in-repo copy is the real one, and it is the wrong premise for the self-hosting layout.

## Detection

In the self-hosting layout, compare `ls -l --time-style=long-iso .leafcutter/scripts/<x>.py leafcutter-ai/.leafcutter/scripts/<x>.py`, or `diff -rq` the two trees. A run's `worktree-setup` record names the absolute script path it used. A path under `leafcutter-ai/.leafcutter/` means the in-repo copy ran.

## Workaround

Rebuild the in-repo copy before running `/plan-feature` from the workspace parent, so the two trees match. Or run `/plan-feature` with cwd inside `leafcutter-ai/`, so only one install is in play.

## Suggested fix

Resolve support files relative to **the install the running workflow came from**, not the repository. For example, the build could stamp the workflow with its own output root, or the snippet could prefer `$PWD/.leafcutter/` when cwd is the ADR-001 workspace parent. The pause store must stay repository-anchored (KI-ACD-009 cause 1), so separate "where the scripts live" from "where the data lives". Amend `ACD-2100a-1` and its test to cover the two-install layout. At minimum, emit the resolved path and its build stamp on stderr, so a skewed run is visible.

**Pattern:** a wrong-copy fix that picks a different wrong copy in the one layout the original defect was about.
