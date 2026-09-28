---
title: "Migrating every worktree call site to the standalone script, with a behavioural test matrix"
description: "The order in which the existing worktree call sites switch to the standalone workspace script, what gets deleted, and the behavioural test matrix that proves it works from any directory and platform. Part of the worktree-consolidation analysis."
type: explanation
status: active
created: 2026-09-25
last_updated: 2026-09-25
components:
  - worktree_manager
  - build_orchestration
---

# Migrating every worktree call site to the standalone script, with a behavioural test matrix

Part of [the worktree-consolidation analysis](2026-09-25-worktree-creation-consolidation.md). The decisions taken on 2026-09-25
(per-feature clones, real install files, `origin/main` everywhere, one script run from a skill)
are in section 8 of that page and in [the decision memo](2026-09-25-worktree-isolation-decision-memo.md);
where they change what is written here, they win.

## 6. Migration plan

Each step is a ticket, per the CLAUDE.md ticket mandate. Order by blast radius: the incident
path first, deletions last.

1. **Build the component and its behavioural test suite** (6.1), alongside the existing
   script. No caller changes yet.
2. **plan-feature.js.**
   - Replace `:2437-2514` with `ensure --kind ac` through the shared helper; halt on non-ok.
   - Delete the null-worktree mode.
   - Move `detect-current-branch`, the orphan and committed-stage scans, the branch check and
     pause-store dispatches off status-checker.
   - Make `templates/commands/plan-feature.md:19` run the pre-flight or go through the skill.
   - Include KI-ACD-007: anchor the product-truth phase writes to the worktree.
3. **fast-lane-ship.js** (`:668-851`): `ensure --kind fastlane`; drop the second git
   verification call and the fallback at `:841`, since the component verifies.
4. **build-feature.js** (`:1404-1452`) and `build-ticket.js`: replace `worktree_repo_facts` and
   the free-text LLM create with `locate`, then `ensure --kind epic|ticket`. This removes
   F10 and F12 on that path.
5. **quick-fix.js and the quick-fix skill**: `ensure --kind feature` with the component's
   own staleness handling; delete the two-location lookup (`quick-fix.js:283-284`).
6. **worktree-agent.md, feature skill, build-single-ticket, build-backlog**: one line each,
   calling `worktree.py ensure`. Delete the feature skill's epic recipe
   (`feature/SKILL.md:70-142`) and the `import settings` leftover.
7. **finalize-feature.js**:
   - `ensure --kind scratch` for the baseline and recovery worktrees (with a fetch);
   - `remove` for teardown;
   - halt on the `"unknown"` fallback (`:541-548`);
   - route Step 7 through `remove`, using a pre-authorised flag the caller supplies.
8. **Docs**: rewrite the manual recipes to "run `worktree.py ensure`" and delete the
   OR-check. Covers `CLAUDE.md:546-595`, `docs/how-to/drive-epic-manually.md:87-93`
   (`EnterWorktree` with no bootstrap), and the stale claims in
   `docs/how-to/verify-precommit-active.md` and `build-feature-ops-notes`.
9. **Delete**:
   - `scripts/setup_ticket_worktree.py`;
   - `templates/scripts/setup_ticket_worktree.py`, or keep it as a thin shim that calls
     `worktree.py` for one release;
   - `worktree_repo_facts.py base`;
   - the resolution snippets in plan-feature (`:2062-2138`);
   - `test_fastlane_template_deploy_parity.py:90-100`.
10. **Retire or merge the KIs this closes**: KI-ACD-007, KI-BO-017, KI-BO-027,
    KI-BO-20260831-1331, KI-BO-20260921 (both), KI-BP-20260826-worktree-hooks-only-on-one-path,
    KI-BP-20260907-bootstrap-swallows-build-failure, and parts of KI-CG-009 / KI-BP-017.

### 6.1 Behavioural test matrix

Every test runs the **deployed** `worktree.py` as a subprocess against real temporary git
repositories with a bare `origin` (the setup used for this page's sandbox). No mocks of git,
no grep of sources (CLAUDE.md "Verify Behaviorally", `:261-278`).

Temporary repositories are created under `tmp_path`, never as worktrees of the real
repository, and each test asserts afterwards that the real repository's `git worktree list`
is unchanged (F14).

| Axis | Values |
|---|---|
| Invocation cwd | main checkout · workspace parent (repository is a child, as in ADR-001) · a sibling scratch directory · inside another linked worktree · inside the target worktree itself · an unrelated directory (expects `NO_REPO`) · a parent with two repositories (expects `AMBIGUOUS_REPO`) |
| Script location | inside the repository's `.leafcutter/scripts` · in the workspace `.leafcutter/scripts` (outside every repository) · in a consumer's `.leafcutter/scripts` |
| Layout | dev (non-repo parent) · consumer (package as a submodule or subdirectory) |
| Prior state | nothing · worktree registered and healthy · registered but un-bootstrapped (the F5 state) · branch without worktree · branch behind `origin/main` · path occupied by a foreign directory · path occupied by another branch's worktree · a pruned directory that git still lists |
| Environment | symlinks allowed · symlinks denied (simulated by a failing `os.symlink`, and run for real on a Windows CI runner without Developer Mode) · `origin` unreachable · `build.py` exits non-zero · path with spaces · Git Bash vs PowerShell vs WSL path spelling of `--repo-root` |

Assertions for every cell:

- stdout parses as **exactly one** JSON object;
- the exit code matches `status`;
- on `ok`, `git -C <worktree_path> rev-parse --git-common-dir` equals the repository's;
- the branch equals the expected name and is not `main`;
- `.pre-commit-config.yaml` is a regular file at the worktree root, and a commit of a
  known-bad file inside the worktree is rejected by a real hook (proves hooks run, not just
  that a file exists);
- `base_commit` equals `origin/main` after a fetch;
- on non-ok, no new worktree or branch remains, unless the code is `refused` for an
  occupant that was there before.

Workflow-level tests (through `_workflow_engine_harness.py`) add the case the current harness
cannot express: the setup agent **refuses**, returns prose, returns exit 0 with a non-JSON
path, or returns a JSON object without `status`. Each must end the workflow with
`status: "error"` before any authoring, phase or commit agent is dispatched. Assert this on
the recorded dispatch list, not on source text.
