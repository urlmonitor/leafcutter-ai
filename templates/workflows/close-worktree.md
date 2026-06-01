---
description: Close a git worktree safely — checks for uncommitted changes, merges to main if needed, then removes the worktree and deletes the branch.
---

# Close Worktree

**Goal:** Safely close a git worktree by ensuring all work is committed, merged to `main`, and then cleaning up the worktree and its branch.

// turbo-all

---

### PHASE 1: IDENTIFY THE WORKTREE

1.  **List active worktrees:**
    ```bash
    git worktree list
    ```
2.  **Ask the user** which worktree to close (if not already specified).
    *   Note the **worktree path** and **branch name** from the output.

---

### PHASE 2: CHECK FOR UNCOMMITTED CHANGES

1.  **Navigate to the worktree** and check status:
    ```bash
    git -C "<worktree-path>" status --porcelain
    ```
2.  **If output is non-empty** (uncommitted changes exist):
    *   **STOP.** Tell the user:
        > ⚠️ There are uncommitted changes in `<branch>`. Please commit or stash them before closing.
    *   List the uncommitted files for the user.
    *   **Do NOT proceed** until the user confirms the changes are handled.
3.  **If output is empty** → proceed to Phase 3.

---

### PHASE 3: CHECK MERGE STATUS

1.  **Fetch latest from remote:**
    ```bash
    git -C "<worktree-path>" fetch origin main
    ```
2.  **Check if the branch is already merged into main** using `git cherry`, which correctly identifies squash-absorbed commits:
    ```bash
    UNMERGED_CHERRY=$(git -C "<worktree-path>" cherry origin/main HEAD | grep '^+')
    ```
    `git cherry` prefixes each commit with:
    - `+` = commit whose diff is NOT yet on `origin/main` (genuinely unmerged)
    - `-` = commit whose diff IS already absorbed by `origin/main` (squash-merged or cherry-picked; safe to ignore)

    > **Why `git cherry` instead of `git log origin/main..<branch>`**: after a squash-merge, `git log` still lists the pre-squash SHAs as "unmerged" even though their diffs are already on main. `git cherry` compares patch content, so squash-absorbed commits appear with a `-` prefix and are correctly excluded. Manual verification of the squash commit on main was required in TICKET-20260513 before this fix.

3.  **If `$UNMERGED_CHERRY` is empty** → branch is already merged (all commits have `-` prefix or none remain). Skip to Phase 4.
4.  **If `$UNMERGED_CHERRY` is non-empty** (genuinely unmerged commits exist):
    *   Show the user the unmerged commits (the `+`-prefixed lines).
    *   Ask: *"These commits on `<branch>` are not yet on `main`. Do you want me to merge `<branch>` into `main`?"*
    *   **If user confirms**, proceed with the merge:
        ```bash
        git -C "<main-worktree-path>" pull origin main
        git -C "<main-worktree-path>" merge <branch-name>
        git -C "<main-worktree-path>" push origin main
        ```
    *   **If merge conflicts occur** → STOP and inform the user. Do NOT force-resolve.
    *   **If user declines** → STOP. Do NOT close the worktree.

---

### PHASE 3.5: SWEEP RESIDUAL PROCESSES AND LOG FILES

Run this phase between Phase 3 (check merge status) and Phase 4 (remove the
worktree). It ensures no orphaned background workers or residual log files
prevent a clean `git worktree remove`.

1.  **Locate the config** (if present):
    ```bash
    # Auto-detected from <project-root>/.claude/skills_config.json
    # or falls back to leafcutter/config/skills_config.default.json
    SKILLS_CONFIG="<project-root>/.claude/skills_config.json"
    ```

2.  **Run the sweep script:**
    ```bash
    python leafcutter/scripts/worktree/sweep_processes.py \
        "<worktree-path>" --config "$SKILLS_CONFIG"
    ```
    Parse the JSON `SweepResult` from stdout.

3.  **Branch on result:**
    *   **`SweepResult.error` is non-null** — STOP. Surface the error verbatim
        and refuse to proceed to Phase 4. Instruct the user to resolve the
        conflict (e.g. manually kill the listed processes) and retry.
    *   **`SweepResult.conflict_pids` is non-empty** — STOP. Show the conflict
        table to the user:

        | PID | Command line | Reason |
        |-----|-------------|--------|
        | `<pid>` | `<cmdline>` | `<reason>` |

        Refuse to proceed to Phase 4 until all conflicts are resolved.
    *   **Clean sweep** — log the result and continue to Phase 4:
        > Sweep complete: `<N>` process(es) killed, `<M>` log file(s) removed.

---

### PHASE 4: REMOVE THE WORKTREE

1.  **Remove the worktree:**
    ```bash
    git -C "<main-worktree-path>" worktree remove "<worktree-path>"
    ```
2.  **If removal fails** (e.g., locked), try with `--force`:
    *   Ask the user first: *"Worktree removal failed. Force remove?"*
    ```bash
    git -C "<main-worktree-path>" worktree remove --force "<worktree-path>"
    ```
3.  **Windows-only escape hatch: `Filename too long` (MAX_PATH).** On Windows,
    `git worktree remove` can fail with `error: failed to delete '<path>':
    Filename too long` when a nested file inside the worktree exceeds the
    260-character path limit (common when worktrees live under
    `C:\Users\<long-name>\Code\<long-folder>\worktrees\<long-branch>\…`).

    By the time you see this error, git has typically already **unregistered**
    the worktree admin entry, so a retry with `--force` returns
    `fatal: 'path' is not a working tree`. The git side is already done — only
    the filesystem directory remains.

    Clean up the leftover directory using PowerShell's `\\?\` long-path prefix,
    which bypasses the Win32 MAX_PATH check:

    ```powershell
    $path = "\\?\<absolute-worktree-path-with-backslashes>"
    Remove-Item -LiteralPath $path -Recurse -Force -ErrorAction Stop
    ```

    Then prune the stale worktree admin entry (no-op if git already cleaned it):

    ```bash
    git -C "<main-worktree-path>" worktree prune
    ```

    Continue to Phase 5 once the directory is gone.

---

### PHASE 5: CLEAN UP THE BRANCH

**Default policy:** always delete both local and remote unless the user explicitly opts out. Remote auto-delete-on-merge is enabled on `origin`, so the remote branch is usually already gone by the time you reach this phase — that is expected, not an error.

1.  **Delete the local branch:**
    ```bash
    git -C "<main-worktree-path>" branch -d <branch-name>
    ```
2.  **Delete the remote branch (best-effort):**
    ```bash
    git -C "<main-worktree-path>" push origin --delete <branch-name> 2>&1 || true
    ```
    *   A `remote ref does not exist` error here is **expected and benign** — GitHub auto-delete-on-merge already removed it. Log it and continue.
    *   Any other error → surface it to the user before exiting.
3.  **Prune stale remote-tracking refs:**
    ```bash
    git -C "<main-worktree-path>" fetch --prune
    ```

---

### PHASE 6: CONFIRMATION

End your response with:
> Worktree `<branch>` has been closed.
> - All changes merged to `main`: Yes/No
> - Residual processes swept: `<N>` killed, `<M>` log files removed
> - Worktree directory removed: `<worktree-path>`
> - Branch `<branch>` deleted (local + remote)
