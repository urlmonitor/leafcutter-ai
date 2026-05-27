---
description: "User-facing entry point to the supervisor system. Resolve an epic name, an epic folder path, or a single standalone-ticket file path under tickets/, then dispatch the right supervisor (epic-supervisor for epics, build-single-ticket sub-skill for standalone tickets) to drive it to completion."
---

> **STOP — PROHIBITION ON INLINE IMPLEMENTATION WORK**
>
> This command MUST dispatch a supervisor agent. It MUST NOT perform any
> implementation work inline. If you find yourself doing any of the following
> WITHOUT first dispatching `epic-supervisor` or the `build-single-ticket`
> sub-skill, **stop immediately** and dispatch the correct supervisor first:
>
> - Reading ticket files to plan implementation
> - Writing or editing source code, configuration, or documentation files
> - Running tests or commit commands
> - Searching the codebase for implementation details
>
> The `inline_work_guard.py` PreToolUse hook enforces this mechanically:
> it blocks Edit/Write tool calls while `.build-feature.lock` exists (written
> at the start of this command). The lock is deleted by the supervisor on
> startup. Any Edit/Write that fires before deletion means a supervisor was
> not dispatched — **dispatch the supervisor now**.
>
> **Lock lifecycle:**
> 1. This command writes `.build-feature.lock` at argument-resolution start.
> 2. `epic-supervisor` Pre-Flight step 4 deletes it before spawning any ticket-supervisor.
> 3. `build-single-ticket` Step 1 deletes it before dispatching `ticket-supervisor`.
> 4. On all exit paths (success, error, zero-match, multi-match), this command
>    deletes any remaining lock file so it does not persist across invocations.

# /build-feature — Drive an Epic or Single Ticket to Completion

This is **the** user-facing entry point to the supervisor system shipped
by EPIC-AgentSupervisor. It accepts one argument:

- An **epic name** or **epic folder path** → dispatches `epic-supervisor`
  to drive the epic ticket-by-ticket.
- A **single standalone ticket file path** (a `.md` under
  `tickets/00_inbox/` or `tickets/01_todo/`, NOT inside an `EPIC-*/`
  folder) → dispatches the `build-single-ticket` sub-skill, which owns
  the inbox → todo → done lifecycle and then spawns `ticket-supervisor`
  to walk the phase agents.

Everything below the supervisors — `ticket-supervisor`, phase agents,
the brainstorm tier — is internal; the user reaches all of it through
this single command.

## Argument

Exactly one argument is expected in `$ARGUMENTS`:

- **An epic name** (e.g. `EPIC-AgentSupervisor`) — resolved by searching
  the standard `tickets/` subtrees.
- **An epic folder path** — absolute, repo-relative, or starting with
  `./` — passed through after existence verification; must contain a
  `Master_Plan.md`.
- **A single ticket file path** — a `.md` file directly under
  `tickets/00_inbox/` or `tickets/01_todo/`, NOT inside any `EPIC-*/`
  subfolder.

If `$ARGUMENTS` is empty, print:

```
Usage: /build-feature <epic-name-or-path-or-ticket-path>

Examples:
  /build-feature EPIC-AgentSupervisor
  /build-feature tickets/01_todo/EPIC-Foo
  /build-feature ./tickets/00_inbox/epics/EPIC-Bar
  /build-feature tickets/00_inbox/TICKET-20260511-Some_Title.md
```

…and exit non-zero. Do not spawn any supervisor.

## Lock File Protocol

**Write the lock file first, before any argument resolution.** This is the
sentinel that `inline_work_guard.py` checks to block inline Edit/Write calls:

```bash
# Detect repo root (walk up from $PWD until .git is found)
REPO_ROOT="$PWD"
while [ ! -d "$REPO_ROOT/.git" ] && [ "$REPO_ROOT" != "/" ]; do
  REPO_ROOT="$(dirname "$REPO_ROOT")"
done
LOCK_FILE="$REPO_ROOT/.build-feature.lock"

# Write the lock (overwrite any stale lock from a crashed prior run)
printf '%s %s\n' "$(date -Iseconds)" "$$" > "$LOCK_FILE"
```

**Clean up the lock on every exit path** — success, zero-match, multi-match,
and error. The supervisors delete it when they start; this cleanup handles the
case where `/build-feature` exits before a supervisor is dispatched:

```bash
# Run on every exit path (trap or explicit call)
rm -f "$LOCK_FILE"
```

**Stale lock detection.** On startup, if `$LOCK_FILE` already exists, check
its age before overwriting:

```bash
if [ -f "$LOCK_FILE" ]; then
  LOCK_AGE=$(( $(date +%s) - $(stat -c %Y "$LOCK_FILE" 2>/dev/null || echo 0) ))
  if [ "$LOCK_AGE" -lt 300 ]; then
    echo "WARNING: .build-feature.lock is only ${LOCK_AGE}s old — a previous /build-feature may still be running."
    echo "If this is a stale lock, delete it manually: rm '$LOCK_FILE'"
  fi
fi
```

Age check is advisory (warning only). Proceed regardless.

## Resolution rule

Decide between **single-ticket**, **epic-path**, and **epic-name** by
the literal characters of `$ARGUMENTS`:

1. **Single-ticket short-circuit.** If `$ARGUMENTS` ends in `.md`,
   resolve it (absolute, repo-relative, or `./`-prefixed) and confirm
   the file exists. If it does **and** its parent directory is
   `tickets/00_inbox` or `tickets/01_todo` (with no `EPIC-*` segment
   between), this is a standalone ticket: jump to the
   **Single Ticket Workflow** below. Do not search the epic subtrees.

2. If `$ARGUMENTS` starts with `/` (absolute on POSIX), starts with
   `./`, or contains a backslash (`\`, Windows-style path), treat it as
   a **path** to an epic folder.

3. Otherwise, treat it as an **epic name** and search, in this order,
   for a directory whose name matches `$ARGUMENTS` exactly:
   - `tickets/00_inbox/epics/`
   - `tickets/01_todo/`
   - `tickets/99_done/`

   (The `99_done/` location is included so a user can re-drive a
   previously-completed epic — for instance after a partial revert.)

4. After resolution, verify the resolved folder contains a
   `Master_Plan.md`. If it does not, the argument resolved to a
   non-epic folder; fall through to the "zero matches" branch below.

### Zero matches

Print:

```
Epic '<arg>' not found under tickets/

Searched:
  tickets/00_inbox/epics/<arg>
  tickets/01_todo/<arg>
  tickets/99_done/<arg>

(Use a full path if the epic lives elsewhere, or run /create-ticket to scaffold a new epic.)
```

…and exit non-zero. Do not spawn `epic-supervisor`.

### Multiple matches

If the same epic name resolves under more than one of the searched
roots (rare — typically only happens during in-flight moves between
inbox and todo), print all matches and exit non-zero:

```
Epic '<arg>' found in multiple locations — be explicit:

  tickets/00_inbox/epics/<arg>/Master_Plan.md
  tickets/01_todo/<arg>/Master_Plan.md

Re-run with the full path, e.g.
  /build-feature tickets/01_todo/<arg>
```

Do not spawn `epic-supervisor`.

### Exactly one match

Convert the resolved folder to an absolute path; call it `EPIC_FOLDER`. Extract the epic name from its basename — e.g. `EPIC-CMEGapContext`. Call it `EPIC_NAME`.

#### Step A — Ensure the epic worktree exists (mandatory, blocking)

Per the project convention (codified in user-memory `feedback_epic_worktree.md` and the `feature` skill): **all epic work must happen inside the dedicated epic worktree, NEVER on `main`.** This step is unconditional and runs before `epic-supervisor` is dispatched.

1. Pick the first sub-ticket file under `EPIC_FOLDER` (sorted by `NN_*.md` execution-order prefix). The `feature` skill routes on a ticket path, so we hand it a real ticket:

   ```bash
   FIRST_TICKET=$(ls "$EPIC_FOLDER"/[0-9][0-9]_*.md 2>/dev/null | sort | head -1)
   ```

   If `FIRST_TICKET` is empty, the epic has no executable sub-tickets — abort with a clear error and exit non-zero. Do **not** spawn `epic-supervisor`.

2. {% if platform == 'claude' %}
   Dispatch the `worktree-agent` via the `Agent` tool with action `create` and the ticket path as the argument. The agent delegates to `.claude/skills/feature/SKILL.md` "Epic Workflow", which:
   {% elif platform == 'antigravity' %}
   Dispatch the `worktree-agent` by running its script via the terminal tool:
   ```bash
   python .agents/agents/worktree-agent/scripts/run.py --action="create" --args="<ticket path>"
   ```
   The agent delegates to `.agents/skills/feature/SKILL.md` "Epic Workflow", which:
   {% endif %}

   - **Reuses** the existing `<REPO_PARENT>/EPIC-<Name>` worktree if one is already checked out on branch `EPIC-<Name>`, or
   - **Creates** a new worktree at `<REPO_PARENT>/EPIC-<Name>` on a fresh `EPIC-<Name>` branch from `origin/main`, then bootstraps (`.env`, `.mcp.json`, `poetry install`).

3. Capture the worktree path reported by the agent. Call it `WORKTREE_PATH`.

4. **`cd` into the worktree in this workflow's own shell** so the subsequent `Agent` dispatch inherits the correct working directory:

   ```bash
   cd "$WORKTREE_PATH"
   ```

   The sub-agent (`worktree-agent`) `cd`s in its own session — that does not propagate. This explicit `cd` in the slash-command body is what propagates to `epic-supervisor`.

5. If the worktree-agent reports failure (creation error, dirty parent, etc.), abort `/build-feature` with its error verbatim. **Do not fall through to dispatching `epic-supervisor` on `main`** — silent main-branch execution is the exact bug this step exists to prevent.

6. **Reachability check.** After `worktree-agent` returns (step 2–3 above), verify that the epic folder is present in the new worktree:

   ```bash
   ls "$WORKTREE_PATH/$EPIC_FOLDER_REPO_RELATIVE/Master_Plan.md"
   ```

   Where `EPIC_FOLDER_REPO_RELATIVE` is the repo-relative path of the epic folder (e.g. `tickets/00_inbox/epics/EPIC-Foo`). If `Master_Plan.md` exists, the check passes — proceed to Step B.

   If `Master_Plan.md` is **absent**, the epic folder was committed to local `main` but not yet pushed to `origin/main`. The worktree (created from `origin/main`) does not contain it. Recover as follows:

   a. Find the missing commit(s) on the host repo:
      ```bash
      git log --oneline origin/main..main
      ```
   b. Cherry-pick each missing commit onto the epic branch (run inside the worktree):
      ```bash
      git -C "$WORKTREE_PATH" cherry-pick <SHA>
      ```
      Apply in chronological order (oldest first) if more than one commit is listed.
   c. Re-run the reachability check. If `Master_Plan.md` is now present, proceed to Step B.
   d. If still absent after all cherry-picks, **abort** with a clear error message — do NOT dispatch `epic-supervisor` on an empty epic:
      ```
      Error: epic folder not reachable in worktree after cherry-pick recovery.
      Epic folder: <EPIC_FOLDER_REPO_RELATIVE>
      Worktree: <WORKTREE_PATH>
      Action: push local main to origin/main, then re-run /build-feature.
      ```

   See `.claude/skills/build-feature-ops-notes/SKILL.md` §KI-1 for the root-cause explanation and background.

#### Step B — Dispatch the epic-supervisor

{% if platform == 'claude' %}
Dispatch the `epic-supervisor` agent via the `Agent` tool with input:

```
{
  "epic_path":     "<EPIC_FOLDER>",
  "worktree_path": "<WORKTREE_PATH>",
  "epic_branch":   "<EPIC_NAME>"
}
```
{% elif platform == 'antigravity' %}
Run the epic-supervisor script via the terminal tool:

```bash
python .agents/agents/epic-supervisor/scripts/run.py --epic_path="<EPIC_FOLDER>" --worktree_path="<WORKTREE_PATH>" --epic_branch="<EPIC_NAME>"
```
{% endif %}

`epic-supervisor` performs its own worktree preflight check (see `.claude/agents/epic-supervisor.md` §Pre-Flight Reads step 4) and will halt without spawning any `ticket-supervisor` if it is not inside `worktree_path` on branch `epic_branch`. That is the safety net behind Step A.

Return `epic-supervisor`'s output verbatim. Do not summarise, do not add a preamble, do not modify formatting — the agent's output is already user-facing per its design (see `docs/agents/coding/epic-supervisor.md`).

## Single Ticket Workflow

When step 1 of the Resolution rule matched — `$ARGUMENTS` ends in `.md`, the
file exists, and its parent is `tickets/00_inbox/` or `tickets/01_todo/`
with no `EPIC-*` segment between — delegate the rest of the flow to the
`build-single-ticket` sub-skill.

{% if platform == 'claude' %}
Invoke it via the `Skill` tool:

```
Skill(skill="build-single-ticket", args="<absolute path to the .md file>")
```
{% elif platform == 'antigravity' %}
Run the skill script via the terminal tool:

```bash
python .agents/skills/build-single-ticket/scripts/run.py --args="<absolute path to the .md file>"
```
{% endif %}

The sub-skill owns the standalone-ticket lifecycle end-to-end:

1. Validates the ticket file (exists, has an `agents:` map, not already
   in `99_done`).
2. Derives a clean branch name from the ticket basename (e.g.
   `TICKET-20260511-Foo_Bar.md` → `ticket/foo-bar`) and dispatches
   `worktree-agent create` to set up an isolated worktree based on
   `origin/main` — same convention as the epic worktree step.
3. Moves the ticket from `tickets/00_inbox/` to `tickets/01_todo/` (via
   `git mv`) if needed.
4. Dispatches `ticket-supervisor` with the worktree-relative ticket
   path, carrying a `via: /build-feature (build-single-ticket)` marker
   so the supervisor accepts the call as sanctioned (not a direct user
   invocation).
5. On `{"status": "done"}`, moves the ticket file to
   `tickets/99_done/<basename>` and commits the bookkeeping move. On
   `blocked` or `failed`, leaves the ticket in `01_todo/` and surfaces
   the supervisor's payload verbatim.

Return the sub-skill's output verbatim. Do not summarise.

If the rejection branch fires inside the sub-skill (ticket missing
`agents:` map, ticket already in `99_done/`, etc.), the sub-skill exits
non-zero with its own error message — surface it verbatim too.

## What this command does NOT do

- **Does not scaffold.** If the epic does not exist, it is the user's
  job to run `/create-ticket` (or `create-epic`) first.
- **Does not commit, push, or open a PR directly.** Those side-effects
  flow through the `commit` and `pull-request` phase agents under
  `ticket-supervisor`s, with the `commit-phase serialization lock` from
  `building-epics` §5 enforcing safety.
- **Does not bypass the user-escalation contract.** When a ticket
  blocks on a genuine `(status: question)`, the supervisor surfaces
  the structured payload back to you per `building-epics` §6 — this
  command is a passthrough, not a wrapper that tries to answer
  questions on the user's behalf.

## References

- `.claude/skills/build-single-ticket/SKILL.md` — the sub-skill
  dispatched for standalone-ticket arguments.
- `.claude/agents/epic-supervisor.md` — the agent dispatched by this
  command for epic arguments.
- `.claude/agents/ticket-supervisor.md` — the inner driver the
  epic-supervisor (or `build-single-ticket`) dispatches per ticket.
- `.claude/agents/brainstorm-lead.md` + `brainstorm-worker.md` — the
  design-escalation tier reached from inside `ticket-supervisor` via
  `building-epics` §3.3.
- `.claude/skills/building-epics/SKILL.md` — operational runbook for
  the entire supervisor stack.
- `docs/agents/coding/epic-supervisor.md` — reference doc for the
  outer driver.
- `docs/agents/coding/brainstorm-lead.md` — reference doc for the
  brainstorm tier.
