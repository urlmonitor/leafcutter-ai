---
description: "User-facing entry point to the supervisor system. Resolve an epic name, an epic folder path, or a single standalone-ticket file path under tickets/, then dispatch ticket-supervisor directly per ready ticket (for epics) or the build-single-ticket sub-skill (for standalone tickets) to drive it to completion."
---

> **STOP — PROHIBITION ON INLINE IMPLEMENTATION WORK**
>
> This command MUST dispatch a supervisor agent. It MUST NOT perform any
> implementation work inline. If you find yourself doing any of the following
> WITHOUT first dispatching `ticket-supervisor` (for epic batches) or the
> `build-single-ticket` sub-skill (for standalone tickets), **stop immediately**
> and dispatch the correct supervisor first:
>
> - Reading ticket files to plan implementation
> - Writing or editing source code, configuration, or documentation files
> - Running tests or commit commands
> - Searching the codebase for implementation details
>
> The `inline_work_guard.py` PreToolUse hook enforces this mechanically:
> it blocks Edit/Write tool calls while `.build-feature.lock` exists (written
> at the start of this command). The lock is deleted by the first dispatched
> ticket-supervisor on startup. Any Edit/Write that fires before deletion means
> a supervisor was not dispatched — **dispatch the supervisor now**.
>
> **Lock lifecycle:**
> 1. This command writes `.build-feature.lock` at argument-resolution start.
> 2. The first dispatched `ticket-supervisor` (Step B) deletes it before running any phase agents.
> 3. `build-single-ticket` Step 1 deletes it before dispatching `ticket-supervisor`.
> 4. On all exit paths (success, error, zero-match, multi-match), this command
>    deletes any remaining lock file so it does not persist across invocations.

# /build-feature — Drive an Epic or Single Ticket to Completion

This is **the** user-facing entry point to the supervisor system shipped
by EPIC-AgentSupervisor. It accepts one argument:

- An **epic name** or **epic folder path** → dispatches `ticket-supervisor`
  directly, one per ready ticket, driving each ticket through its phase agents
  at depth 0 without going through `epic-supervisor`.
- A **single standalone ticket file path** (a `.md` under
  `tickets/00_inbox/` or `tickets/01_todo/`, NOT inside an `EPIC-*/`
  folder) → dispatches the `build-single-ticket` sub-skill, which owns
  the inbox → todo → done lifecycle and then spawns `ticket-supervisor`
  to walk the phase agents.

Everything below `ticket-supervisor` — phase agents, the brainstorm tier —
is internal; the user reaches all of it through this single command.

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

…and exit non-zero. Do not dispatch any ticket-supervisor.

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

Do not dispatch any ticket-supervisor.

### Exactly one match

Convert the resolved folder to an absolute path; call it `EPIC_FOLDER`. Extract the epic name from its basename — e.g. `EPIC-CMEGapContext`. Call it `EPIC_NAME`.

#### Step A — Ensure the epic worktree exists (mandatory, blocking)

Per the project convention (codified in user-memory `feedback_epic_worktree.md` and the `feature` skill): **all epic work must happen inside the dedicated epic worktree, NEVER on `main`.** This step is unconditional and runs before ticket-supervisor is dispatched (Step B).

1. Pick the first sub-ticket file under `EPIC_FOLDER` (sorted by `NN_*.md` execution-order prefix). The `feature` skill routes on a ticket path, so we hand it a real ticket:

   ```bash
   FIRST_TICKET=$(ls "$EPIC_FOLDER"/[0-9][0-9]_*.md 2>/dev/null | sort | head -1)
   ```

   If `FIRST_TICKET` is empty, the epic has no executable sub-tickets — abort with a clear error and exit non-zero. Do **not** proceed to Step B.

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

   The sub-agent (`worktree-agent`) `cd`s in its own session — that does not propagate. This explicit `cd` in the slash-command body is what propagates to `ticket-supervisor` (dispatched inline in Step B).

5. If the worktree-agent reports failure (creation error, dirty parent, etc.), abort `/build-feature` with its error verbatim. **Do not fall through to dispatching ticket-supervisors on `main`** — silent main-branch execution is the exact bug this step exists to prevent.

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
   d. If still absent after all cherry-picks, **abort** with a clear error message — do NOT proceed to Step B with an empty epic:
      ```
      Error: epic folder not reachable in worktree after cherry-pick recovery.
      Epic folder: <EPIC_FOLDER_REPO_RELATIVE>
      Worktree: <WORKTREE_PATH>
      Action: push local main to origin/main, then re-run /build-feature.
      ```

   See `.claude/skills/build-feature-ops-notes/SKILL.md` §KI-1 for the root-cause explanation and background.

#### Step B — Invoke build-epic.js (preferred) or fall back to inline batching

> **Rationale:** `build-epic.js` is the deterministic JS workflow script that
> implements the epic batching algorithm (building-epics §1.1) without LLM
> prose ambiguity. It is available on Claude Code installations ≥ v2.1.154.
> On older installs the inline fallback below applies.
>
> See EPIC-FlattenSupervisorChain ticket 03 for the full design rationale.
> ADR: docs/architecture/adrs/ADR-006-flatten-supervisor-chain.md

**Preferred path — invoke build-epic.js:**

Check whether `build-epic.js` is available at
`<WORKTREE_PATH>/templates/workflows-js/build-epic.js`.

If it exists, invoke the `build-epic` workflow:

```
workflow("build-epic", { epic_path: EPIC_FOLDER })
```

This delegates all batching, parallel dispatch, and halt detection to the
JS layer. The workflow returns one of:

- `{ status: "ok", ... }` — all tickets completed.
- `{ status: "blocked", halted_tickets: [...], ... }` — one or more tickets
  failed or blocked. Surface the `halted_tickets` array to the user and halt.
- `{ status: "error", message: "..." }` — unrecoverable error (e.g. planner
  agent returned unparseable output). Surface the message and halt.

On `ok`, print the completion message:

```
Epic <EPIC_NAME> complete.
All sub-tickets signed off. Branch: <EPIC_NAME>.
Next step: run /finalize-feature <EPIC_NAME> to open the PR and close the worktree.
```

On `blocked`, print the blocked summary using `result.halted_tickets`.

**Fallback path — inline batching (build-epic.js absent):**

If `build-epic.js` is not present (e.g. on a sub-v2.1.154 install or on a
worktree that pre-dates ticket 03), use the inline prose implementation below.
This is the ADR-006 §C implementation — it is preserved as a safety net and
will be removed once build-epic.js has been validated across all supported
install versions.

**Inline epic batching loop** — repeat until every ticket in the epic is
`done` or the run is blocked/halted:

1. **Read `Master_Plan.md`** from `EPIC_FOLDER`. Extract the list of all
   sub-ticket filenames in the epic (all `NN_*.md` files under `EPIC_FOLDER`,
   excluding `Master_Plan.md`).

2. **Read every sub-ticket frontmatter** to determine:
   - `status:` (done, todo, or blocked)
   - `depends_on:` list (filenames of prerequisite tickets, relative to epic folder)

3. **Compute `ready_batch`** — the maximal set of tickets that:
   - Have `status:` NOT equal to `done`
   - Have every ticket in their `depends_on` list at `status: done`
   - Have disjoint `files_touched` sets with all other tickets in the batch
     (no physical overlap — use conservative single-ticket batching when in doubt)
   - Are not already in a `blocked` state awaiting user resolution

   If `ready_batch` is empty and there are still non-done tickets: surface every
   blocked payload collected so far and halt with a structured summary. If all
   tickets are `done`, proceed to the completion message below.

   > **Tie-breaking:** when multiple tickets are ready simultaneously, sort by
   > ascending `NN_` numeric prefix (lower number runs first).

4. **Dispatch one `ticket-supervisor` per ticket in `ready_batch`**, in
   parallel. Each dispatch is an `Agent` tool call with input:

   ```
   {
     "ticket_path": "<absolute path to the sub-ticket .md file>",
     "context": {
       "epic_path": "<EPIC_FOLDER>",
       "worktree_path": "<WORKTREE_PATH>",
       "epic_branch": "<EPIC_NAME>"
     }
   }
   ```

   > **[DISPATCH PROHIBITION]** NEVER describe an `Agent` tool-call and then
   > stop. If the next intended action is an `Agent` tool call, invoke the
   > tool immediately. Describing the call and stopping leaves on-disk state
   > unchanged and appears as a successful run to the user.

   > **[DISPATCH VERIFICATION]** After issuing all N `Agent` tool calls,
   > confirm N result blocks appear in context before proceeding to step 5.
   > If fewer results appear than calls issued, halt and report the missing
   > dispatches to the user.

5. **Wait for the entire batch to complete** (barrier). Each `ticket-supervisor`
   returns one of:
   - `{ "status": "done" }` — ticket fully signed off
   - `{ "status": "blocked", "payload": { ... } }` — user input required
   - `{ "status": "failed", "payload": { ... } }` — halt-class failure

6. **Route on batch results:**
   - If any returned `blocked` with a structural blocker (affects multiple
     remaining tickets or is a dependency-cycle): halt, surface all pending
     payloads to the user.
   - If any returned `blocked` but the blocker is local to that ticket:
     record the blocked payload, KEEP the loop running, GOTO step 1
     (the blocked ticket will be excluded from `ready_batch` on next pass).
   - If any returned `failed`: halt immediately, surface the failure payload.
   - If all tickets are `done`: exit loop and proceed to the completion message.
   - Otherwise: GOTO step 1.

**Completion message** (print when all tickets are `done`):

```
Epic <EPIC_NAME> complete.
All sub-tickets signed off. Branch: <EPIC_NAME>.
Next step: run /finalize-feature <EPIC_NAME> to open the PR and close the worktree.
```

**Blocked summary format** (print when halting on blockers):

```
Epic <EPIC_NAME> halted — <N> ticket(s) blocked.

<For each blocked ticket:>
  Ticket: <ticket_path>
  Phase:  <phase>
  Blocker: <blocker_summary>
  Remediation: <suggested_remediation>
```

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
- `.claude/agents/ticket-supervisor.md` — the driver dispatched per
  ready ticket for both epic and standalone paths. For epics, this
  command dispatches it directly at depth 0; for standalone tickets,
  `build-single-ticket` dispatches it.
- `.claude/agents/brainstorm-lead.md` + `brainstorm-worker.md` — the
  design-escalation tier reached from inside `ticket-supervisor` via
  `building-epics` §3.3.
- `.claude/skills/building-epics/SKILL.md` — operational runbook for
  the supervisor stack. §1.1 defines the dependency-graph batching
  algorithm implemented inline in Step B of this command.
- `docs/agents/coding/brainstorm-lead.md` — reference doc for the
  brainstorm tier.
