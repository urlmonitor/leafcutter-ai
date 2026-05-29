---
description: "User-facing entry point to the supervisor system. Resolve an epic name, an epic folder path, or a single standalone-ticket file path under tickets/, then dispatch the right supervisor (epic-supervisor for epics, build-single-ticket sub-skill for standalone tickets) to drive it to completion."
---

> **STOP — PROHIBITION ON INLINE IMPLEMENTATION WORK**
>
> This workflow MUST dispatch ticket-supervisors (for epics) or the
> `build-single-ticket` sub-skill (for standalone tickets). It MUST NOT
> perform any implementation work inline. If you find yourself doing any
> of the following WITHOUT dispatching a `ticket-supervisor`:
>
> - Reading ticket files to plan implementation
> - Writing or editing source code, configuration, or documentation files
> - Running tests or commit commands
> - Searching the codebase for implementation details
>
> **Stop immediately** — you are the coordinator, not an implementer.
>
> The `inline_work_guard.py` PreToolUse hook enforces this mechanically:
> it blocks Edit/Write tool calls while `.build-feature.lock` exists (written
> at the start of this command). The lock is deleted during pre-flight
> (Step B, check 2). Any Edit/Write that fires before deletion means
> orchestration has not begun — **something is wrong**.
>
> **Lock lifecycle:**
> 1. This workflow writes `.build-feature.lock` at argument-resolution start.
> 2. Step B pre-flight check 2 deletes it before spawning any ticket-supervisor.
> 3. `build-single-ticket` Step 1 deletes it before dispatching `ticket-supervisor`.
> 4. On all exit paths (success, error, zero-match, multi-match), this workflow
>    deletes any remaining lock file so it does not persist across invocations.

# /build-feature — Drive an Epic or Single Ticket to Completion

This is **the** user-facing entry point to the supervisor system shipped
by EPIC-AgentSupervisor. It accepts one argument:

- An **epic name** or **epic folder path** → this workflow coordinates the
  epic inline (dependency batching, parallel dispatch of ticket-supervisors,
  post-completion chain).
- A **single standalone ticket file path** (a `.md` under
  `tickets/00_inbox/` or `tickets/01_todo/`, NOT inside an `EPIC-*/`
  folder) → dispatches the `build-single-ticket` sub-skill, which owns
  the inbox → todo → done lifecycle and then spawns `ticket-supervisor`
  to walk the phase agents.

Everything below this workflow — `ticket-supervisor`, phase agents,
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

...and exit non-zero. Do not spawn any supervisor.

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
and error. The pre-flight deletes it when orchestration begins; this cleanup
handles the case where `/build-feature` exits before orchestration starts:

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

...and exit non-zero. Do not proceed to orchestration.

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

Do not proceed to orchestration.

### Exactly one match

Convert the resolved folder to an absolute path; call it `EPIC_FOLDER`. Extract the epic name from its basename — e.g. `EPIC-CMEGapContext`. Call it `EPIC_NAME`.

#### Step A — Ensure the epic worktree exists (mandatory, blocking)

Per the project convention (codified in user-memory `feedback_epic_worktree.md` and the `feature` skill): **all epic work must happen inside the dedicated epic worktree, NEVER on `main`.** This step is unconditional and runs before orchestration begins.

1. Pick the first sub-ticket file under `EPIC_FOLDER` (sorted by `NN_*.md` execution-order prefix). The `feature` skill routes on a ticket path, so we hand it a real ticket:

   ```bash
   FIRST_TICKET=$(ls "$EPIC_FOLDER"/[0-9][0-9]_*.md 2>/dev/null | sort | head -1)
   ```

   If `FIRST_TICKET` is empty, the epic has no executable sub-tickets — abort with a clear error and exit non-zero. Do **not** proceed to orchestration.

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

   The sub-agent (`worktree-agent`) `cd`s in its own session — that does not propagate. This explicit `cd` in the slash-command body is what propagates to ticket-supervisors.

5. If the worktree-agent reports failure (creation error, dirty parent, etc.), abort `/build-feature` with its error verbatim. **Do not fall through to orchestration on `main`** — silent main-branch execution is the exact bug this step exists to prevent.

6. **Reachability check.** After `worktree-agent` returns (step 2-3 above), verify that the epic folder is present in the new worktree:

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
   d. If still absent after all cherry-picks, **abort** with a clear error message — do NOT proceed to orchestration on an empty epic:
      ```
      Error: epic folder not reachable in worktree after cherry-pick recovery.
      Epic folder: <EPIC_FOLDER_REPO_RELATIVE>
      Worktree: <WORKTREE_PATH>
      Action: push local main to origin/main, then re-run /build-feature.
      ```

   See `.claude/skills/build-feature-ops-notes/SKILL.md` KI-1 for the root-cause explanation and background.

#### Step B — Epic Coordination (inline)

This workflow runs at **depth 0**. It dispatches `ticket-supervisor` agents at **depth 1** via the Agent tool. ticket-supervisors are self-contained (they do all phase work inline, no further Agent tool calls). This architecture satisfies the hard depth-1 nesting limit.

---

##### Pre-Flight Checks (all 7 required before any ticket dispatch)

**Check 1 — Worktree preflight (mandatory, blocking).**

Verify this workflow is running inside the dedicated epic worktree:

```bash
CWD=$(git rev-parse --show-toplevel)
BRANCH=$(git branch --show-current)
EPIC_NAME_CHECK=$(basename "<EPIC_FOLDER>")   # e.g. EPIC-CMEGapContext
```

**Block conditions (any of these → halt without dispatching):**

a. `BRANCH` is `main` or `master`. Epic work on a trunk branch is always a bug — abort.
b. `BRANCH != EPIC_NAME` (the branch must match the epic folder basename).
c. The absolute, resolved form of `WORKTREE_PATH` (from Step A) does not equal `CWD`.

On any block condition, emit a halt payload with reason `worktree preflight failed`, include the detected `CWD`, `BRANCH`, and `expected branch`, and instruct the user to re-invoke via `/build-feature <epic-name>` from the main repo. **Do not auto-spawn `worktree-agent` to recover** — silent recovery would mask invocation bugs. Exit.

**Check 2 — Delete `.build-feature.lock` (inline-work-guard handoff).**

After all block conditions pass, remove the sentinel lock written at the start of this command so subsequent ticket-supervisor spawns and phase agents are not blocked by `inline_work_guard.py`:

```bash
rm -f "$(git rev-parse --show-toplevel)/.build-feature.lock"
```

If the lock file does not exist, the `rm -f` is a no-op. This deletion signals that orchestration has taken ownership.

**Check 3 — Master_Plan completeness check (two-level gating).**

Read `Master_Plan.md` and apply these two gates before dispatching any ticket.

*Level 1 — Epic-wide gate (hard halt for ALL tickets):*
Scan `Master_Plan.md` for a `##`-level heading containing "Design Decision" or "Key Decision" (case-insensitive). If no such heading is found, halt the entire epic without dispatching any ticket and emit:

> `Master_Plan.md has no "Key Design Decisions" section — add one and resolve all open architectural questions before invoking /build-feature.`

Do not dispatch any ticket when this gate fires. Exit.

*Level 2 — Per-ticket selective gate:*
For each sub-ticket in scope, scan its `## Architecture` and `## Context` sections for lines containing any of these markers: `TODO`, `TBD`, `open question` (case-insensitive), or a heading (`###`-level or above) whose text ends with `?`.

- A ticket with such markers is **gated**: do not dispatch it. Surface its unresolved items in the consolidated payload below.
- A ticket without such markers is dispatched normally — even when sibling tickets are gated.
- Additionally gate any ticket whose `depends_on` list includes a gated ticket (transitive gating via dependency order).

After evaluating all tickets, emit **one consolidated payload** that lists every gated ticket and its unresolved items. This gives the user a single-pass view of all architectural questions to resolve before re-invoking `/build-feature`. If ALL tickets are gated, halt entirely. If some tickets remain ungated, proceed with those.

**Check 4 — Per-ticket selective gate (TBD/TODO detection).**

(This is the enforcement mechanism of Level 2 above — included as a distinct numbered check for auditability. The scan in Check 3 Level 2 produces the gated-ticket list; this check enforces it by excluding gated tickets from the dependency graph before entering the epic loop.)

**Check 5 — Orphan-process sweep (advisory, non-blocking).**

Check for stale pytest / SQL-test worker processes left over from previous worktree sessions:

- POSIX:
  ```bash
  ps -eo pid,command | grep -E 'pytest.*sql_func|sql_functions' | grep -v grep
  ```
- Windows / PowerShell:
  ```powershell
  Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*sql_func*' } | Select ProcessId, CommandLine
  ```

If any processes are returned, surface them to the user in a single advisory line (PIDs and commands) and ask whether to kill them before dispatching the first ticket-supervisor. **Do not auto-kill** — the user may have another active session. This is advisory: if the user declines or no processes are returned, proceed normally.

**Check 6 — Feedback-sink reachability check (warn-not-halt).**

Verify that the telemetry sink is writable:

```bash
SINK_PATH="debugging/logs/agent_telemetry.jsonl"
mkdir -p "$(dirname "$SINK_PATH")"
echo '{"probe":"pre-drive-reachability-check"}' >> "$SINK_PATH" 2>/dev/null \
  && SINK_OK=1 || SINK_OK=0
```

- **If `SINK_OK=1`** (write succeeded): proceed silently.
- **If `SINK_OK=0`** (write failed): emit the structured warning block and ask the user **"Proceed without telemetry? (yes / no)"**. On `yes`, continue. On `no`, halt. Do NOT silently proceed with an unreachable sink.

**Check 7 — Load operational runbooks.**

Load these skill files for reference during the epic loop:
- `.claude/skills/building-epics/SKILL.md` — operational runbook (single source of truth for algorithms).
- `.claude/skills/signoff/SKILL.md` — needed to read ticket-state surfaces produced by phase agents.

---

Do not proceed until all seven checks succeed (checks 1-4 are blocking; check 5 is advisory; check 6 is warn-not-halt requiring user acknowledgement if sink is unreachable; check 7 is informational).

---

##### The Epic Loop (six-step cycle)

After pre-flight passes, execute this loop until every ticket is done or the epic is halted:

**Step 1 — Read epic state (fresh on every pass).**

Read `Master_Plan.md` and every ticket file in the epic folder (sub-tickets at root plus the `done/` subfolder for completed work). This is evaluated fresh on every loop iteration — not a one-time snapshot. Mid-drive ticket additions (e.g. from a `merge origin/main`) are picked up automatically on the next pass.

**Step 2 — Build dependency graph.**

```
nodes = { ticket_path for each non-done ticket }
logical_edges    = { (a, b) | b in a.depends_on (transitively closed) }
physical_edges   = { (a, b) | a.files_touched ∩ b.files_touched != empty }
G = nodes + logical_edges + physical_edges
```

Both edge sets are undirected for the parallelism gate; `depends_on` is also retained as a directed edge for ordering. Exclude any tickets that were gated by Check 3/4 above.

**Step 3 — Compute next ready batch (maximal antichain).**

```
ready = { t in G | every t' in t.depends_on has status done }
batch = a maximal antichain of `ready` such that:
          for all a, b in batch:
            a.files_touched intersect b.files_touched = empty
            AND neither a depends_on b nor b depends_on a (transitive closure)
```

Tie-break by ascending NN execution-order prefix.

**File-touch parallelism gate definition:** Two tickets `a` and `b` are parallel-safe iff (1) `a.files_touched intersect b.files_touched = empty` AND (2) neither depends on the other under the transitive closure of `depends_on`. Both conditions must hold. If a ticket's `files_touched` is missing or empty, treat it as conflicting with every other ticket and run it serially (default-conservative).

**Step 4 — Dispatch ticket-supervisors in parallel.**

{% if platform == 'claude' %}
Spawn one `ticket-supervisor` per ticket in the batch via the `Agent` tool — **all in a single message** with multiple `Agent` tool calls (the project convention for parallel sub-agent fan-out). Each child receives `{ticket_path: <absolute path>}`.
{% elif platform == 'antigravity' %}
Spawn one `ticket-supervisor` per ticket in the batch via parallel terminal calls:
```bash
python .agents/agents/ticket-supervisor/scripts/run.py --ticket_path="<absolute path>"
```
Run all batch members in parallel.
{% endif %}

> **NEVER render an `Agent` tool-call input as user-facing prose and then stop.**
> If your next intended action is an `Agent` tool call, you MUST invoke the
> tool — describing the call and stopping is always an error.

> **Dispatch Verification (mandatory after every fanout).** After issuing all N
> `Agent` tool calls, confirm that N tool-call result blocks appear in your
> context before proceeding. If fewer results appear than calls issued, halt and
> report the missing dispatches to the user rather than continuing to step 5.
> Do NOT proceed to the next phase assuming the missing dispatches completed.

**Before dispatching each ticket-supervisor**, emit `supervisor_dispatch` telemetry (non-blocking):
```bash
python .claude/skills/agent-telemetry/scripts/emit_event.py \
  --agent "build-feature" --event supervisor_dispatch \
  --ticket "<ticket_path>" \
  --log debugging/logs/agent_telemetry.jsonl || true
```

**Step 5 — Wait barrier and collect results.**

Wait for the entire batch to complete. Each child returns one of:
- `{status: "done"}` — ticket fully signed off
- `{status: "blocked", payload: ...}` — user input required
- `{status: "blocked", escalation_type: "brainstorm", design_question: "..."}` — brainstorm escalation (see handler below)
- `{status: "failed", payload: ...}` — halt-class failure

##### Cross-ticket pattern detection (CFCS emit, between steps 5 and 6)

After collecting all blocked/failed payloads from a parallel ticket batch and before applying halt-or-loop logic, scan the payloads for repeated cross-ticket failure patterns and emit one aggregating CFCS entry per detected pattern.

**Algorithm:**

```python
# Group blocked payloads by (phase, blocker_summary prefix)
from collections import defaultdict
groups = defaultdict(list)
for payload in blocked_payloads:
    key = (payload["phase"], payload["blocker_summary"][:60])
    groups[key].append(payload)

# Emit one aggregating entry per group with >= 2 members
for (phase, summary_prefix), affected in groups.items():
    if len(affected) >= 2:
        count = len(affected)
        # Shell equivalent:
        # python scripts/feedback/submit_feedback.py \
        #   --ticket "<any_affected_ticket_path>" --phase build-feature \
        #   --category subagent-quality \
        #   --tags "agent-<phase>,cross-ticket-pattern,n-<count>" \
        #   --note "Cross-ticket pattern: <phase> failed with '<summary_prefix>' on <count> tickets." \
        #   --jsonl debugging/logs/feedback.jsonl 2>/dev/null
```

**Non-blocking contract:** A failed `submit_feedback.py` call during pattern detection MUST NOT alter the blocked payload surfaced to the user. The aggregating emit is a side-effect only.

**Threshold:** N >= 2 tickets with the same (phase, blocker_summary[:60]) to trigger.

**Exactly one aggregating entry per detected pattern per drive.**

##### Brainstorm escalation handler (between steps 5 and 6)

When a ticket-supervisor returns `{status: "blocked", escalation_type: "brainstorm", design_question: "..."}`:

{% if platform == 'claude' %}
1. Dispatch `brainstorm-lead` at depth 1 via the `Agent` tool with the design question as input.
{% elif platform == 'antigravity' %}
1. Dispatch `brainstorm-lead` via terminal:
   ```bash
   python .agents/agents/brainstorm-lead/scripts/run.py --design_question="<the design question>"
   ```
{% endif %}
2. Collect the recommendation from `brainstorm-lead`.
3. Re-invoke `ticket-supervisor` for that ticket with the brainstorm result:
   ```
   {ticket_path: "<absolute path>", brainstorm_recommendation: "<recommendation text>"}
   ```
4. **Cap: 1 brainstorm escalation per ticket per drive.** If the same ticket requests a second brainstorm escalation, treat it as a structural blocker and surface to the user.

This handler runs at depth 0 (this workflow), dispatching brainstorm-lead at depth 1. The ticket-supervisor does NOT dispatch brainstorm-lead itself — it returns the escalation payload and this workflow handles routing.

**Step 6 — Halt-or-loop logic.**

Apply these rules in order:

- **IF** any child returned `{status: "blocked"}` with a **structural** blocker (the suggested remediation requires resolving an ambiguity that affects multiple tickets, OR a phase agent on the critical path of every remaining ticket has returned `failed`):
  → Halt the epic. Surface every pending payload to the user. Emit `epic_halted` telemetry:
  ```bash
  python .claude/skills/agent-telemetry/scripts/emit_event.py \
    --agent "build-feature" --event epic_halted \
    --outcome blocked \
    --log debugging/logs/agent_telemetry.jsonl || true
  ```

- **ELSE-IF** any child returned `{status: "blocked"}` but the blocker is **local** to that ticket (other tickets remain independent):
  → Mark that ticket blocked. KEEP the epic running. Exclude it from `ready` until the user resolves it. GOTO Step 1.

- **ELSE-IF** every ticket in the epic is now `done`:
  → Emit "epic complete". Emit `epic_complete` telemetry:
  ```bash
  python .claude/skills/agent-telemetry/scripts/emit_event.py \
    --agent "build-feature" --event epic_complete \
    --outcome ok \
    --log debugging/logs/agent_telemetry.jsonl || true
  ```
  → Proceed to the **Post-Completion Chain** below.

- **ELSE** (some tickets remain, none are structurally blocked):
  → GOTO Step 1.

##### Halt conditions (comprehensive list)

The epic loop halts entirely only when:

- **Worktree preflight failure** (Check 1). Refuse to spawn any ticket-supervisor from `main`, from a mismatched branch, or from a mismatched working tree.
- A child returns `{status: "blocked"}` and the blocker is **structural** — suggested remediation requires resolving an ambiguity that affects multiple tickets, or a phase agent on the critical path of every remaining ticket has returned `failed`.
- The dependency graph contains a **cycle** that survives the `files_touched` projection (refinement should prevent this; treat as an invariant violation).
- The **commit-phase lock** cannot be released after a child crash (lock-recovery requires user intervention; see `building-epics` section 5.4).

In all other blocker scenarios — a single ticket's blocker is local and other tickets remain independent — mark that ticket blocked, exclude it from `ready`, and continue.

---

##### Post-Completion Chain

Execute these steps in order after every ticket is `done`:

**Step 1 — Retro Decision**

Evaluate these heuristics to decide whether to run a retrospective:

*Run retro when ANY of these are true:*
- Epic has >= 5 sub-tickets
- Any ticket was retried (a phase agent signed off as `failed` then re-run)
- Any ticket was blocked and required user escalation
- Epic took more than 1 calendar day (first ticket start vs. last ticket done)
- `agent_telemetry.jsonl` exists and shows >= 3 phase failures across the epic

*Skip retro when ALL of these are true:*
- Epic has < 5 sub-tickets
- All tickets passed first try (no retries, no blocks)
- No user escalations were needed
- Epic completed within a single session

{% if platform == 'claude' %}
If running retro: spawn `retrospective-agent` via the Agent tool. Pass it the epic path. The agent produces `docs/retrospectives/<EPIC-Name>.md`.
{% elif platform == 'antigravity' %}
If running retro: run the retrospective agent script:
```bash
python .agents/agents/retrospective-agent/scripts/run.py --epic_path="<EPIC_FOLDER>"
```
{% endif %}

If skipping: log the reason in the output:
> Retro skipped: <N> tickets, all passed first try, no escalations.

**Step 2 — Changelog Entry (always runs)**

Write a per-file changelog entry via `emit_entry.py`:

1. Read `Master_Plan.md` title (-> `epic` field) and description (-> `description`).
2. List all sub-ticket basenames from the epic folder (-> `tickets` list).
3. Run `git log --oneline --no-pager origin/main...HEAD` and extract short SHAs (-> `commits` list, up to 20).
4. If Step 4 of this chain produced a merged PR, record its number (-> `pr` field); otherwise omit `pr`.
5. Read `docs/components.json` and select the component IDs relevant to the epic. If the file does not exist, use the top-level package names touched in the epic as a fallback.

Build the payload and call `emit_entry.py`:

```bash
python leafcutter/scripts/changelog/emit_entry.py \
  --changelog-dir "changelogs/" \
  --payload '{
    "title": "EPIC-<Name> complete",
    "date": "YYYY-MM-DD",
    "time": "HH:MM",
    "type": "epic_completion",
    "epic": "<Master_Plan.md title>",
    "components": ["<component1>", "..."],
    "summary": "<one sentence in plain business language>",
    "description": "<1-3 line technical summary from Master_Plan description>",
    "tickets": ["<01_ticket.md>", "..."],
    "commits": ["<sha1>", "..."],
    "pr": "<PR-number or omit>",
    "adrs": ["<ADR-NNN — omit field if no ADRs were produced>"],
    "diagrams": ["<docs/architecture/path.md — omit field if no diagrams apply>"]
  }'
```

- `summary` is **required**. Write one sentence in plain business language that describes what the epic delivered to the business (not the technical implementation).
- `pr` is optional. Populate it with the PR number or URL when the epic landed via a single tracked PR. Omit the field entirely if the epic spans multiple PRs or no single PR is canonical.
- `adrs` is optional. Include when the epic produced or amended an ADR. Omit the field entirely when not applicable.
- `diagrams` is optional. Include paths to architecture diagrams only when the epic introduced architectural changes documented in a diagram. Omit the field entirely when not applicable.

Print the path of the written changelog file to the user.

Then commit the new entry file:

```bash
git add "changelogs/"
git commit -m "chore(changelog): add epic-completion entry for EPIC-<Name>"
```

Do NOT write to or modify the legacy `CHANGELOG.md`.

**Step 3 — Epic Folder Move**

Move the epic folder to `tickets/99_done/EPIC-<Name>/`:
1. `git mv <current-epic-path> tickets/99_done/EPIC-<Name>/`
2. Update `status:` field in `Master_Plan.md` frontmatter to `done`
3. Stage the changes

**Step 4 — PR Merge (user approval required)**

1. Find the open PR for the epic branch: `gh pr list --head <branch>`
2. **Mergeability gate (mandatory, blocking).** Before claiming the PR is "ready to merge" or surfacing merge prose to the user, query GitHub for the authoritative merge state:

   ```bash
   gh pr view <PR-number> --json mergeable,mergeStateStatus,statusCheckRollup
   ```

   Interpret the result:

   - `mergeable == "MERGEABLE"` AND `mergeStateStatus == "CLEAN"` -> proceed to step 3.
   - `mergeable == "CONFLICTING"` -> halt the merge step. Surface the conflict to the user with the offending files (from `gh pr view --json files`) and stop. Do NOT call `gh pr merge`.
   - `mergeStateStatus` in (`BLOCKED`, `BEHIND`, `DIRTY`, `UNSTABLE`, `UNKNOWN`) -> halt the merge step. Show the user the exact `mergeStateStatus` value and the failing required checks (from `statusCheckRollup`), and stop. Do NOT call `gh pr merge`.
   - `mergeable == "UNKNOWN"` -> GitHub has not finished computing mergeability. Wait briefly and re-query once; if still `UNKNOWN`, surface that to the user and stop.

   **Never claim a PR is "ready to merge" without this check.** A clean local working tree and a green local test run do not guarantee that GitHub will accept the merge.

3. Show the user: branch name, commit count, files changed, and the confirmed `mergeable` / `mergeStateStatus` values from step 2.
4. Ask: **"Merge epic PR to main? (yes / no)"**
5. On `yes`: `gh pr merge --merge <PR-number>`
6. On `no`: stop here with "PR left open for manual handling." Do NOT proceed to Step 5.

**Never merge without explicit user approval.**

**Step 4.5 — All-Tickets-Done Gate (mandatory, blocking)**

Before proceeding to Step 5 (Worktree Cleanup), verify that every sub-ticket in the epic is fully signed off. Premature invocation of `close-worktree` destroys the branch ref while in-progress commits survive only as unreachable orphan objects.

**Counting gate algorithm:**

```python
open_tickets = [f for f in epic_folder.glob("*.md")
                if f.name != "Master_Plan.md"
                and parse_frontmatter_status(f) != "done"]

if open_tickets:
    abort("Worktree cleanup blocked: %d sub-ticket(s) not done: %s"
          % (len(open_tickets), [f.name for f in open_tickets]))
    # Do NOT proceed. Do NOT spawn worktree-agent.
else:
    ALL_TICKETS_DONE = true
    log("All-Tickets-Done gate passed: ALL_TICKETS_DONE=true")
    # Proceed to Step 5.
```

**ALL_TICKETS_DONE confirmation token**: this workflow MUST log the string `ALL_TICKETS_DONE=true` (visible in the transcript) after the gate passes. The worktree-agent MUST NOT be spawned unless this token has been set in the current invocation.

**Step 5 — Worktree Cleanup (user approval required)**

{% if platform == 'claude' %}
Spawn `worktree-agent` via the Agent tool with `remove <epic-worktree-path>`.
{% elif platform == 'antigravity' %}
Run the worktree agent:
```bash
python .agents/agents/worktree-agent/scripts/run.py --action="remove" --args="<epic-worktree-path>"
```
{% endif %}

The worktree-agent has its own confirmation gate before any destructive action.

The worktree-cleanup step includes **process sweep and log cleanup** (Phase 3.5 of the close-worktree workflow) before `git worktree remove`. The contract is:

- This workflow calls `worktree-agent` (which invokes close-worktree).
- `close-worktree` owns the sweep — this workflow does NOT call `sweep_processes.py` directly.
- If `worktree-agent` reports `SweepResult.conflict_pids` (protected-path or permission conflicts), the cleanup halts and the user must resolve the conflicts before retrying.

Only run if Step 4 (PR merge) succeeded.

---

##### Epic Output Formats

When the epic completes cleanly (all tickets done, entering post-completion chain):

```
## Epic Complete: EPIC-<Name>

All N tickets are signed off. Entering post-completion chain.

Tickets:
- 01_<slug>.md — done
- 02_<slug>.md — done
...
```

When one or more tickets are blocked but the epic is not halted:

```
## Epic Paused: EPIC-<Name>

M tickets are done; K tickets are blocked awaiting user input. The
remaining independent tickets have been processed up to the next
dependency boundary.

Done:
- 01_<slug>.md
...

Blocked (user input needed):
- 04_<slug>.md — phase: <phase>
  blocker: <blocker_summary>
  suggested: <suggested_remediation>

Skipped (depend on blocked tickets):
- 05_<slug>.md (depends_on 04)
```

When the epic is halted by a structural blocker:

```
## Epic Halted: EPIC-<Name>

A structural blocker prevents further progress on independent tickets.

Halt reason: <one-paragraph explanation>
First blocking ticket: <path>
Suggested remediation: <text>

(other pending payloads listed below)
```

---

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
   `TICKET-20260511-Foo_Bar.md` -> `ticket/foo-bar`) and dispatches
   `worktree-agent create` to set up an isolated worktree based on
   `origin/main` — same convention as the epic worktree step.
3. Moves the ticket from `tickets/00_inbox/` to `tickets/01_todo/` (via
   `git mv`) if needed.
4. Dispatches `ticket-supervisor` with the worktree-relative ticket path.
5. On `{"status": "done"}`, moves the ticket file to
   `tickets/99_done/<basename>` and commits the bookkeeping move. On
   `blocked` or `failed`, leaves the ticket in `01_todo/` and surfaces
   the supervisor's payload verbatim.

**Brainstorm escalation handling for single tickets:** If the ticket-supervisor
returns `{status: "blocked", escalation_type: "brainstorm", design_question: "..."}`,
the `build-single-ticket` sub-skill surfaces it back to this workflow. This workflow
then dispatches `brainstorm-lead` at depth 1, collects the recommendation, and
re-invokes `ticket-supervisor` via the sub-skill with the brainstorm result. Same
cap applies: 1 brainstorm escalation per ticket.

Return the sub-skill's output verbatim. Do not summarise.

If the rejection branch fires inside the sub-skill (ticket missing
`agents:` map, ticket already in `99_done/`, etc.), the sub-skill exits
non-zero with its own error message — surface it verbatim too.

## Parallelism model

- **Single epic worktree** (existing project convention preserved).
  Parallel `ticket-supervisor`s share the filesystem; safety is enforced
  by the `files_touched` disjoint-set invariant at batch-formation time
  AND by the per-`ticket-supervisor` commit-phase lock.
- **Commit phase serialized.** At most one `ticket-supervisor` is in
  the `commit` or `pull-request` phase at a time. This is enforced by
  the `ticket-supervisor`s themselves via the lock at
  `<worktree_root>/.epic-commit-lock` (atomic create via `set -C`,
  deleted on release). The recipe lives in `building-epics` section 5.
- **One PR per epic** (existing convention). The PR opens once every
  ticket in the epic is `done`.
- **Staging discipline (SOP).** When this workflow itself stages and
  commits files (e.g. the changelog entry in the post-completion chain),
  it MUST use `git add <explicit paths>` — never `git add .` or
  `git add -A`. The only exception is `git add "changelogs/"` for the
  changelog entry (a known-safe subtree with no in-flight parallel work).

## Constraints

- Do NOT modify `.claude/skills/*/SKILL.md` files — skills are canonical.
- Do NOT directly mutate ticket-state surfaces. Mutation is the job of
  phase agents (via `signoff`) and the `ticket-supervisor` (move-to-done
  flip when complete). This workflow only reads ticket state.
- Do NOT spawn phase agents directly (`python-coder`, `commit`, etc.).
  Always go through a `ticket-supervisor` so per-ticket retry caps,
  comment parsing, and adjudication ladder are applied uniformly.
- Do NOT scaffold tickets or epics. That is `create-ticket` /
  `create-epic`. If the resolved epic folder is missing or empty,
  surface an error and exit.
- **Nesting depth budget:** This workflow runs at depth 0. It dispatches
  `ticket-supervisor` and `brainstorm-lead` at depth 1. ticket-supervisors
  are self-contained (no Agent tool calls) — they do all phase work inline.
  This satisfies the hard depth-1 nesting limit.
- In the post-completion chain, this workflow dispatches `retrospective-agent`
  and `worktree-agent` at depth 1 — these are utility agents that run
  self-contained.

## What this command does NOT do

- **Does not scaffold.** If the epic does not exist, it is the user's
  job to run `/create-ticket` (or `create-epic`) first.
- **Does not commit, push, or open a PR directly.** Those side-effects
  flow through the `commit` and `pull-request` phase agents under
  `ticket-supervisor`s, with the `commit-phase serialization lock` from
  `building-epics` section 5 enforcing safety.
- **Does not bypass the user-escalation contract.** When a ticket
  blocks on a genuine `(status: question)`, the supervisor surfaces
  the structured payload back to you per `building-epics` section 6 — this
  command is a passthrough, not a wrapper that tries to answer
  questions on the user's behalf.

## References

- `.claude/skills/build-single-ticket/SKILL.md` — the sub-skill
  dispatched for standalone-ticket arguments.
- `.claude/agents/ticket-supervisor.md` — the self-contained agent
  dispatched by this workflow per ticket (depth 1).
- `.claude/agents/brainstorm-lead.md` + `brainstorm-worker.md` — the
  design-escalation tier dispatched by this workflow (depth 1) when a
  ticket-supervisor returns a brainstorm escalation.
- `.claude/skills/building-epics/SKILL.md` — operational runbook for
  the algorithms (single source of truth for dependency graph, file-touch
  gate, halt conditions, commit-phase lock, user-escalation schema).
- `templates/agents/epic-supervisor.md` — **DEPRECATED** audit trail.
  All orchestration logic formerly in that agent is now inline in this
  workflow.
