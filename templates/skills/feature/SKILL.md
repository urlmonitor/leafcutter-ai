---
allowed-tools: Bash(git *), Bash(cd *), Bash(ls *), Bash(pwd), Bash(poetry *), Bash(ln
  *), Bash(mklink *), Bash(cp *), Bash(mkdir *), Bash(cmd *), Bash(grep *), Bash(awk
  *), Bash(sed *)
description: Create an isolated git worktree for a new feature branch, or reuse the
  existing epic worktree when given a ticket path
name: feature
---

# Create / Reuse Feature Worktree

> **IMPORTANT — `/quick-fix` exclusion (AC BP-600a-2):**
> This skill MUST NOT be invoked from the `/quick-fix` workflow or from any agent
> dispatched by it. The `feature` skill calls `git worktree add`, which violates
> the quick-fix worktree invariant (AC BP-600a-1: stay in the current worktree,
> never create a new one). Any `/quick-fix` implementation that loads this skill
> is non-compliant. See `docs/architecture/adrs/ADR-006-flatten-supervisor-chain.md`
> §Addendum for the full BP-600a-2 constraint specification.

Set up an isolated workspace for: **$ARGUMENTS**

## Routing

Inspect `$ARGUMENTS`:

- **Ticket path** — matches the pattern `tickets/.../EPIC-<NAME>/<NN>_*.md` (e.g., `tickets\01_todo\EPIC-DocTraceability\15_ticket_frontmatter.md`).
  - The whole epic shares **one** worktree because tickets within an epic normally have dependencies.
  - Extract `EPIC-<NAME>` and use **Epic Workflow**.

- **Anything else** — treat as a free-form feature name and use **Feature Workflow**.

If `$ARGUMENTS` is empty, ask the user what they want to work on.

---

## Epic Workflow

### 1. Extract the epic name

Parse the path to pull out the `EPIC-<NAME>` segment:

```bash
EPIC_NAME=$(echo "$ARGUMENTS" | grep -oE 'EPIC-[A-Za-z0-9_-]+' | head -1)
TICKET_FILE="$ARGUMENTS"
```

If `EPIC_NAME` is empty, fall through to the Feature Workflow with the basename of the ticket as the feature name.

### 2. Check whether the epic worktree already exists

```bash
git worktree list | grep -F "[$EPIC_NAME]"
```

- **If found** (a worktree is checked out on branch `$EPIC_NAME`):
  - Extract its path from the `git worktree list` output
  - `cd` into it
  - Confirm to the user:
    - "Reusing existing epic worktree at `<path>` (branch `$EPIC_NAME`)."
    - "Now working on ticket `<TICKET_FILE>`."
  - **Skip bootstrap** — the worktree is already set up.
  - Stop here. Done.

- **If not found**: continue to step 3.

### 3. Create the epic worktree

Convention: epic worktrees live at the **repo parent** (sibling of the main repo), with the branch named after the epic — matching the existing pattern (`EPIC-CentralizeTradingParameters`, `EPIC-StrategyPipelineOptimization`).

```bash
MAIN_REPO=$(pwd)                                         # current repo root
REPO_PARENT=$(dirname "$MAIN_REPO")
WORKTREE_PATH="$REPO_PARENT/$EPIC_NAME"

git fetch origin
git worktree add -b "$EPIC_NAME" "$WORKTREE_PATH" origin/main
```

### 4. Bootstrap the worktree

Same as the Feature Workflow bootstrap (step 5 below):

- Copy `.env` from `$MAIN_REPO`
- Copy `.mcp.json` from `$MAIN_REPO` if it exists
- `poetry install --no-root` (run from `$WORKTREE_PATH` using absolute path)
- Verify: `poetry run python -c "import settings; print('Settings OK')"`

#### Build outputs (mandatory)

After `poetry install --no-root` completes, run:

```bash
python scripts/build.py --target-dir .
```

This populates `.leafcutter/` (gitignored build outputs) including
`.leafcutter/.claude/workflows/` required for named workflow resolution
and creates the `.pre-commit-config.yaml` symlink via `install_shims()`.

**Post-build probe (AC-1 / AC-5 — mandatory, run immediately after build.py returns):**

Check that the pre-commit config exists and is not a dangling symlink:

```bash
python -c "import os, sys; p='.pre-commit-config.yaml'; sys.exit(0 if os.path.exists(p) else 1)"
```

Interpret the probe result as follows:

- **Probe passes** (file exists and resolves): bootstrap is complete. Package hooks
  will run on commits made inside this worktree.
- **Probe fails — build.py returned non-zero**: emit the following structured error
  and stop; do NOT claim the worktree is ready:

  ```
  BOOTSTRAP ERROR (AC-5): build.py ran but .pre-commit-config.yaml is missing.
  The build failed — package hooks will NOT run in this worktree.
  Resolution: re-run build.py manually inside the worktree, or run the package
  hooks manually against the branch diff before merge.
  ```

- **Probe fails — build.py was not found**: emit:

  ```
  BOOTSTRAP ERROR (AC-5): build.py not found in worktree.
  .pre-commit-config.yaml was not created — package hooks will NOT run.
  Resolution: locate and run the correct build.py for this project layout.
  ```

**Do NOT use `PRE_COMMIT_ALLOW_NO_CONFIG=1` as the default path.** That env-var
silently disables all package hooks and masks the bootstrap failure. It is a
documented last-resort fallback only — use it only when the pre-commit config
cannot be established and the user explicitly accepts that hooks will not run.

### 5. Switch working directory & confirm

```bash
cd "$WORKTREE_PATH"
```

Print:
- Worktree path and branch name
- "Epic worktree ready. Working on ticket `<TICKET_FILE>`."
- Reminder: any future `/feature tickets/.../$EPIC_NAME/...` call will **reuse** this worktree.
- Reminder to run `/ship` when the epic is complete.

### 6. Post-create divergence check (new worktrees only)

**Important:** The epic worktree is always based on `origin/main`, NOT on local `main`. If local `main` is ahead of `origin/main` at the time of creation, the new worktree will NOT contain those local commits.

After step 3 (new worktree creation — skip this check on reuse), check for divergence:

```bash
git rev-list --count origin/main..main   # run in the host repo
```

- If count is 0: no action needed.
- If count > 0: emit a warning (see `worktree-agent.md` Post-create check section for the exact warning format). List the ahead commits so the user knows what is missing. Do NOT abort — this is an informational heads-up.

**What to do if you see this warning:**

1. **Preferred:** Push local `main` to `origin/main` before creating the worktree, then retry. This ensures the worktree starts from the correct base.
2. **Alternative (after creation):** Cherry-pick the missing commit(s) onto the epic branch per the reachability check procedure in `.claude/commands/build-feature.md` Step A step 6 (R-1).

If the epic folder is in the missing commits and you skip this step, `/build-feature` will fail its reachability check and prevent the supervisor from being dispatched until the epic folder is present.

---

## Feature Workflow (free-form or prefixed name)

> **Note:** The bootstrap recipe for free-form feature branches is implemented
> in `scripts/setup_ticket_worktree.py` (subcommand `create-only`). Edit that
> script to change the bootstrap steps — do not update this skill's inline
> commands.
>
> **Post-bootstrap probe:** After `setup_ticket_worktree.py` returns (exit 0 or
> non-zero), verify that `<worktree-root>/.pre-commit-config.yaml` exists and
> resolves. If it is absent or dangling, emit a structured AC-5 error (see Epic
> Workflow "Build outputs (mandatory)" above for the exact error messages) and
> do NOT claim the worktree is ready. `PRE_COMMIT_ALLOW_NO_CONFIG=1` is a
> documented fallback only — do not use it as the default.

1. **Determine Prefix and Sanitize**:
   - Check if the name already starts with a standard branch prefix (e.g., `ticket/`, `feature/`, `bugfix/`, `hotfix/`, `chore/`).
   - If it has a prefix, keep it. If it doesn't, default to `feature/`.
   - Sanitize the rest of the name: lowercase, replace spaces with hyphens, strip special characters.
   - Example: "Add Stop Loss" -> prefix `feature/`, name `add-stop-loss`.
   - Example: "ticket/foo-bar" -> prefix `ticket/`, name `foo-bar`.
   - Note: today `setup_ticket_worktree.py create-only` always emits a `feature/<slug>` branch in its JSON output. It recognises both `feature/` and `ticket/` prefixes for idempotent reuse of an existing worktree, but it does not yet honour `bugfix/`, `hotfix/`, or `chore/` on creation — a follow-up will extend the script to round-trip arbitrary prefixes.

2. **Determine paths**:
   - Main repo: the current working directory (the git root) — save this as `MAIN_REPO`
   - Worktree parent: `<repo-parent>/worktrees/`
   - Worktree path: `<repo-parent>/worktrees/<sanitized-name>/` (do not include the prefix in the folder name)

3–7. **(consolidated): run setup_ticket_worktree.py**

   For a free-form feature name, use the `create-only` subcommand:

   ```bash
   python scripts/setup_ticket_worktree.py create-only "<sanitized-feature-name>"
   ```

   Parse `worktree_path` and `branch` from the JSON output (single line on
   stdout). Report these to the user:

   - Print the worktree path and branch name.
   - Confirm environment is bootstrapped (`.env` copied, dependencies installed).
   - Remind them that the main repo is untouched.
   - Remind them to run `/ship` when they're happy with the result.

---

## Important

- NEVER create the worktree from uncommitted changes - always base on `origin/main`
- If the current directory has uncommitted changes, warn the user but proceed (changes stay in the original directory)
- The worktree is a full working copy with its own `.venv/` - tests, poetry, etc. all work there
- Docker services (database, etc.) are external and work from any directory - no special setup needed
- The `.env` is COPIED (not symlinked) so worktree-specific tweaks are possible without affecting main
- **Epic worktrees are reused across tickets in the same epic** — do not create a per-ticket worktree when an epic worktree exists.
