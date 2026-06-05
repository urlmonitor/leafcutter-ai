---
name: ship
description: Merge a completed feature worktree back to main and clean up
disable-model-invocation: true
allowed-tools: Bash(git *), Bash(cd *), Bash(gh *), Bash(poetry run *), Bash(python *), Bash(ls *), Bash(pwd)
---

# Ship Feature

Merge the current feature worktree back to main and clean up.

**This skill can ONLY be invoked by the user.** Never call this yourself - the user must explicitly say the feature is ready.

## Pre-flight Checks

1. **Confirm we're in a worktree** (not the main repo):
   ```
   git worktree list
   ```
   The current directory should be a worktree, not the main working tree. If we're in the main repo, abort with a clear message.

2. **Get the current branch name** and the main repo path from `git worktree list`.

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

8. **Clean up the worktree**:
   - Switch working directory back to the main repo
   - `git worktree remove <worktree-path>`
   - `git branch -d feature/<name>` (only if merged)

9. **Confirm** to the user:
   - What was merged
   - That the worktree is removed
   - That we're back in the main repo

## Abort

If anything fails (tests, merge conflicts, etc.), STOP immediately and report the issue. Let the user decide how to proceed. Never force-push or force-delete.
