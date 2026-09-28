---
title: "KI-BO-20260928-fast-lane-worktree-step-runs-another-clones-script — fast-lane-ship's worktree step gives the agent a cwd-relative script path and no repository anchor, so from a deleted cwd the agent found another leafcutter-ai clone and opened the build worktree inside an unrelated project"
description: "high — the worktree prompt says 'run from the repository root' but never names that root, and setup_ticket_worktree.py resolves the repository from its own file location. When the session cwd was a just-deleted worktree, the worktree-agent located a different clone (inside the Bybit-Trader workspace) and the run created its worktree there. Code verified on main at 8ed47463; the incident is session observation."
type: reference
category: reference
status: active
created: '2026-09-28'
last_updated: '2026-09-28'
components:
  - build_orchestration
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/known-issues/build-orchestration/open-high-ki-bo-20260921-worktree-base-resolver-defaults-to-cwd.md
  - docs/known-issues/ac-driven-dev/open-high-ki-acd-20260927-repo-anchor-picks-the-in-repo-install-copy.md
  - docs/known-issues/commit-guardian/open-high-ki-cg-20260925-shared-root-resolver-accepts-non-repo-workspace-parent.md
---

# KI-BO-20260928-fast-lane-worktree-step-runs-another-clones-script — fast-lane-ship's worktree step gives the agent a cwd-relative script path and no repository anchor, so from a deleted cwd the agent found another leafcutter-ai clone and opened the build worktree inside an unrelated project

- **Severity:** high. The run writes into a repository the user did not point it at. In this occurrence it stopped before any commit or push, but nothing in the workflow would have stopped it: that clone has the same `origin` (`https://github.com/urlmonitor/leafcutter-ai`), so every later check (`base_matches_origin_main`, the AC store lookup, the claim) would have passed against the wrong checkout.
- **Status:** open. No AC.
- **Occurrences:** 1 (fast-lane-ship, 2026-09-27/28, Windows 11; session observation, cleaned up by hand)
- **First seen:** 2026-09-28 · **Last seen:** 2026-09-28
- **Where:** `templates/workflows-js/fast-lane-ship.js:674-700` (the `fastlane-worktree` dispatch) · `scripts/setup_ticket_worktree.py:139-170` (`_git_toplevel`, anchored on `Path(__file__)`) and `:173-245` (`_resolve_installed_layout`)

## What happened (session observation)

`/fast-lane-ship` was launched while the session's working directory was a worktree that had just been removed. The worktree step did not fail. It opened `fast-lane/<slug>` in `C:\Users\Hendrik\Code\Bybit-Trader\Bybit-Trader Live\worktrees\`, using the leafcutter-ai clone at `C:\Users\Hendrik\Code\Bybit-Trader\Bybit-Trader Live\leafcutter-ai`. No commit or push happened. The worktree and branch were removed by hand.

## Mechanism (verified in code, main 8ed47463)

1. The prompt tells the agent: *"Run this single Bash command from the repository root: `python3 {{config.output_root}}/scripts/setup_ticket_worktree.py create-fastlane-worktree "<slug>"`"* (`fast-lane-ship.js:677-678`; deployed as `.leafcutter/scripts/...`). It never says which directory the repository root is. The workflow body has no subprocess access (E2), so it cannot compute one itself, and it does not pass one in `args`.
2. With the cwd gone, the relative path resolves to nothing. The `worktree-agent` went looking for the script and found a copy in another clone. Which copy it ran was not recorded. That clone has no `.leafcutter/scripts/setup_ticket_worktree.py` today (checked 2026-09-28), so it most likely ran the clone's own `scripts/` copy. That part is inference.
3. The script trusts its own location. `_git_toplevel()` runs `git -C <dir of this file> rev-parse --show-toplevel` (`:158-161`). So whichever copy runs decides which repository is used.
4. `_resolve_installed_layout()` then checks whether the clone's parent is a git repository (`:230-236`). `Bybit-Trader Live` is not one (no `.git`, checked 2026-09-28), so the dev layout applies and worktrees go to `<parent>/worktrees/`. That is `Bybit-Trader Live\worktrees\`, which is that project's own worktree folder.

Nothing in the step compares the resolved repository with the one the user invoked the lane from. The reply schema returns `worktree_path` and `base_matches_origin_main`. Neither can tell one clone of the same remote from another.

## Related, not the same

- `KI-BO-20260921-worktree-base-resolver-defaults-to-cwd`: build-feature omits a start path and resolves against the workspace parent. It fails loudly. This one succeeds in the wrong place.
- `KI-ACD-20260927-repo-anchor-picks-the-in-repo-install-copy`: plan-feature's repo-anchor snippet picks the wrong copy inside the right repository. This one picks a different repository.
- `KI-CG-20260925-shared-root-resolver-accepts-non-repo-workspace-parent`: the same family (root taken from ambient state) in the hooks.

## Detection

After any fast-lane run, compare the returned `worktree_path` with the repository you launched from. `git -C <worktree_path> rev-parse --git-common-dir` should resolve inside that repository. A path under another project's `worktrees/` is this defect.

## Workaround

Start the session (or `cd`) in a live checkout of the target repository before launching `/fast-lane-ship` or `/fast-lane-build`. Never launch from a worktree that has just been removed.

## Suggested fix

1. Resolve the repository root once, before the worktree step, and put it in the prompt as an absolute path (`cd <root> && python3 <root>/.leafcutter/scripts/...`). Refuse to continue when it cannot be resolved, rather than letting the agent search.
2. Tell the agent in the prompt not to search for the script. A missing script is a refusal (`outcome: null`), not a prompt to find a copy elsewhere.
3. Have `create-fastlane-worktree` accept `--repo-root` and fail when it differs from its own `_git_toplevel()`. The script and the repository it acts on must be the same checkout.

**Pattern:** a step that says "from the repository root" without naming it lets an agent pick the root. Given two clones of the same remote, every identity check the lane has passes on either.
