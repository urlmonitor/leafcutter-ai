---
name: ship
description: Merge a completed feature worktree back to main and clean up
disable-model-invocation: true
allowed-tools: Bash(git *), Bash(cd *), Bash(gh *), Bash(poetry run *), Bash(python *), Bash(ls *), Bash(pwd)
---

# Ship Feature

Merge the current feature workspace back to main and clean up. The workspace comes from, and is cleared by, the workspace maker `scripts/worktree.py`, see `docs/how-to/get-a-workspace.md`.

**This skill can ONLY be invoked by the user.** Never call this yourself - the user must explicitly say the feature is ready.

## Pre-flight Checks

1. **Confirm we're in a workspace** (not the main repo). Ask the workspace maker `scripts/worktree.py`, see `docs/how-to/get-a-workspace.md`:
   Run ONE exact command with the ABSOLUTE, quoted path to the deployed maker, unchanged, and return its stdout verbatim. The path is `<project root>/.leafcutter/scripts/worktree.py`, with the project root from `git rev-parse --show-toplevel`. Never a cwd-relative path.
   ```
   python "<project root>/.leafcutter/scripts/worktree.py" locate --kind feature --slug "<name>"
   ```
   The `workspace_path` of the ok answer must be the current directory. If we're in the main repo, abort with a clear message.

2. **Get the current branch name** from `git branch --show-current`; the main repo path is the project the workspace was made from (the answer's `repo_root`).

3. **Run tests** to make sure everything passes:
   ```
   poetry run python -m unittest discover -s unit_tests/live_trader -t . -p "test_*.py"
   ```
   If tests fail, STOP and report the failures. Do NOT proceed with merge.

4. **Check for uncommitted changes**. If there are any, ask the user whether to commit them first or abort.

## Ship It

5. **Push the feature branch** to origin:
   ```
   git push -u origin feature/<name>
   ```

6. **Ask the user** how they want to merge:
   - **Create a PR** (recommended): Use `gh pr create` with a summary of changes
   - **Direct merge**: Switch to main repo, merge, push

7. **If direct merge chosen**:
   - Switch to the main repo directory
   - `git checkout main`
   - `git pull origin main`
   - `git merge --no-ff feature/<name>` (preserve merge commit)
   - `git push origin main`

8. **Clear the workspace** with the workspace maker `scripts/worktree.py`, see `docs/how-to/get-a-workspace.md`, never by hand:
   - Switch working directory back to the main repo, then recompute the project root there: `git rev-parse --show-toplevel` (ONE exact command, run unchanged, stdout verbatim)
   - `python "<project root>/.leafcutter/scripts/worktree.py" remove --path "<workspace-path>"` (ONE exact command: the absolute, quoted maker path built from the project root just recomputed, run unchanged, stdout verbatim) (if it refuses with `UNSENT_WORK`, stop and report; see `docs/how-to/clear-a-workspace.md`)
   - `git branch -d feature/<name>` in the main repo (only if merged)

9. **Confirm** to the user (workspace maker `scripts/worktree.py`, see `docs/how-to/get-a-workspace.md`):
   - What was merged
   - That the workspace is cleared
   - That we're back in the main repo

## Abort

If anything fails (tests, merge conflicts, etc.), STOP immediately and report the issue. Let the user decide how to proceed. Never force-push or force-delete.
