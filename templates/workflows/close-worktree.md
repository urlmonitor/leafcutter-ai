---
description: Close a workspace safely — checks for uncommitted changes, merges to main if needed, sweeps residual processes, then asks the workspace maker (scripts/worktree.py, docs/how-to/get-a-workspace.md) to clear it.
---

# Close Workspace

**Goal:** Safely close a workspace by ensuring all work is committed, merged to `main`, and then asking the workspace maker (`scripts/worktree.py`; see `docs/how-to/get-a-workspace.md` and `docs/how-to/clear-a-workspace.md`) to clear it. Never delete a workspace folder by hand.

// turbo-all

---

### PHASE 1: IDENTIFY THE WORKSPACE

Finding a workspace is the maker's `locate` verb (`scripts/worktree.py`; see `docs/how-to/get-a-workspace.md`).

1.  **Ask the user** which workspace to close (if not already specified), by kind and slug.
2.  **Locate it** with the workspace maker `scripts/worktree.py`, see `docs/how-to/get-a-workspace.md`:
    ```bash
    python scripts/worktree.py locate --kind <kind> --slug <slug>
    ```
    *   Take the **workspace path** and **branch name** from the `"status": "ok"` answer only.

---

### PHASE 2: CHECK FOR UNCOMMITTED CHANGES

1.  **Check the status** of the workspace:
    ```bash
    git -C "<workspace-path>" status --porcelain
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
    git -C "<workspace-path>" fetch origin main
    ```
2.  **Check if the branch is already merged into main** using `git cherry`, which correctly identifies squash-absorbed commits:
    ```bash
    git -C "<workspace-path>" cherry origin/main HEAD
    ```
    `git cherry` prefixes each commit with:
    - `+` = commit whose diff is NOT yet on `origin/main` (genuinely unmerged)
    - `-` = commit whose diff IS already absorbed by `origin/main` (squash-merged or cherry-picked; safe to ignore)

    > **Why `git cherry` instead of `git log origin/main..<branch>`**: after a squash-merge, `git log` still lists the pre-squash SHAs as "unmerged" even though their diffs are already on main. `git cherry` compares patch content, so squash-absorbed commits appear with a `-` prefix and are correctly excluded.

3.  **If no line starts with `+`** → branch is already merged (all commits have `-` prefix or none remain). Skip to Phase 4.
4.  **If any line starts with `+`** (genuinely unmerged commits exist):
    *   Show the user the unmerged commits (the `+`-prefixed lines).
    *   Ask: *"These commits on `<branch>` are not yet on `main`. Do you want me to merge `<branch>` into `main`?"*
    *   **If user confirms**, deliver the work through the project's normal merge route (the pull request flow), not by hand-merging in the workspace (workspace maker `scripts/worktree.py`, see `docs/how-to/get-a-workspace.md`).
    *   **If merge conflicts occur** → STOP and inform the user. Do NOT force-resolve.
    *   **If user declines** → STOP. Do NOT clear the workspace (workspace maker `scripts/worktree.py`, see `docs/how-to/get-a-workspace.md`).

---

### PHASE 3.5: SWEEP RESIDUAL PROCESSES AND LOG FILES

Run this phase between Phase 3 (check merge status) and Phase 4 (clear it
with the maker; workspace maker `scripts/worktree.py`, see `docs/how-to/get-a-workspace.md`). It ensures no orphaned background workers or residual log files
keep the maker's `remove` verb from finishing (a `PROCESS_HOLDS_FILES` refusal).

1.  **Locate the config** (if present):
    ```bash
    # Auto-detected from <project-root>/.claude/skills_config.json
    # or falls back to leafcutter/config/skills_config.default.json
    SKILLS_CONFIG="<project-root>/.claude/skills_config.json"
    ```

2.  **Run the sweep script:**
    ```bash
    python leafcutter/scripts/worktree/sweep_processes.py \
        "<workspace-path>" --config "$SKILLS_CONFIG"
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

### PHASE 4: CLEAR IT WITH THE MAKER

Clearing is the workspace maker's `remove` verb only (`scripts/worktree.py`; see `docs/how-to/clear-a-workspace.md` and `docs/how-to/get-a-workspace.md`).

1.  **Ask the maker to clear it** (workspace maker `scripts/worktree.py`, see `docs/how-to/get-a-workspace.md`):
    ```bash
    python scripts/worktree.py remove --path "<workspace-path>"
    ```
2.  **If the answer is `UNSENT_WORK`**, the maker has refused and left the workspace as it was (workspace maker `scripts/worktree.py`, see `docs/how-to/get-a-workspace.md`). Show the user the listed `unsent` commits and files. Deliver the work first and ask again; repeat the request with the answer's `discard_token` only on the user's explicit instruction to throw that work away.
3.  **Any other refusal** (for example `PROCESS_HOLDS_FILES`): surface the answer's `code` and `message` verbatim and STOP. Never delete the folder by hand and never retry with `--force`; the maker ignores it.

---

### PHASE 5: CLEAN UP THE REMOTE BRANCH

**Default policy:** delete the remote branch unless the user explicitly opts out (workspace maker `scripts/worktree.py`, see `docs/how-to/get-a-workspace.md`). Remote auto-delete-on-merge is enabled on `origin`, so the remote branch is usually already gone by the time you reach this phase — that is expected, not an error. The branch itself lived inside the cleared workspace and went with it.

1.  **Delete the remote branch (best-effort):**
    ```bash
    git push origin --delete <branch-name>
    ```
    *   A `remote ref does not exist` error here is **expected and benign** — GitHub auto-delete-on-merge already removed it. Log it and continue.
    *   Any other error → surface it to the user before exiting.
2.  **Prune stale remote-tracking refs:**
    ```bash
    git fetch --prune
    ```

---

### PHASE 6: CONFIRMATION

End your response with:
> Workspace `<branch>` has been closed.
> - All changes merged to `main`: Yes/No
> - Residual processes swept: `<N>` killed, `<M>` log files removed
> - Workspace cleared by the workspace maker (`scripts/worktree.py`; `docs/how-to/get-a-workspace.md`): `<workspace-path>`
> - Remote branch `<branch>` deleted
