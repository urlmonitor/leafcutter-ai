---
allowed-tools: Read, Edit, Bash(ls *)
description: Operational runbook loaded by the `build-feature` workflow (main context)
  and `ticket-supervisor` as their primary instruction set. Use when the workflow needs
  to walk an epic ticket-by-ticket (dependency batching + file-touch parallelism gate),
  or when ticket-supervisor needs to drive a single ticket through its phase agents
  (read `agents` map → read next phase agent template → execute inline → parse comment
  status → route ok/handoff/blocker/question), adjudicate failures with explicit retry
  caps, hold the commit-phase serialization lock, or escalate blockers to the user via
  the structured payload. Loaded by the main context and by ticket-supervisor; phase
  agents themselves use the `signoff` skill, not this one.
name: building-epics
---

# building-epics

This skill is the **single runbook** for the supervisory layer. It encodes the control-flow algorithms (epic-level + ticket-level), the file-touch parallelism gate, the failure-adjudication ladder, the retry caps, the commit-phase lock, and the user-escalation payload schema.

**Architecture note (flat supervisor model):** The supervisor chain has been flattened to respect Claude Code's depth-1 nesting limit:
- The **build-feature workflow** (depth 0, main context) performs epic-level orchestration inline (previously delegated to a separate `epic-supervisor` agent).
- **ticket-supervisor** (depth 1, dispatched via Agent tool from the main context) drives individual tickets. It does NOT have access to the Agent tool — it reads phase agent templates and executes their instructions inline using Read/Edit/Write/Bash.
- Brainstorm escalation returns to the main context (depth 0) rather than spawning from ticket-supervisor.

It is the operational complement to the [`signoff`](../signoff/SKILL.md) skill. `signoff` defines **what** the on-disk state means and how to mutate it; `building-epics` defines **how** the workflow and ticket-supervisor decide what to do next based on that state. Status-enum semantics, frontmatter ↔ `## Sign-offs` parity, and the comment-heading schema all live in `signoff` and are not duplicated here.

If you change anything in this file, both the build-feature workflow and ticket-supervisor will see the change at their next invocation — that's the point. Adding a new retry cap or a new escalation tier is an edit to this one file, never an ad-hoc choice in a supervisor prompt.

---

## §1 Epic-level Algorithm (build-feature workflow, main context)

The six-step loop from the spec (§6.1). This is the outer driver: the build-feature workflow (running at depth 0 in the main context) walks an epic until every ticket is signed off or the run is halted. Previously this was delegated to a separate `epic-supervisor` agent; it is now executed inline by the build-feature workflow.

### §1.0 Feedback-Sink Reachability Pre-flight (runs before §1.1 loop)

Before entering the main epic loop (step 1), verify that the feedback
sink is reachable and writable. This prevents silent telemetry loss for the entire drive.

**Check (POSIX):**

```bash
SINK_PATH="debugging/logs/agent_telemetry.jsonl"
mkdir -p "$(dirname "$SINK_PATH")"
if echo '{"probe":"pre-drive-reachability-check"}' >> "$SINK_PATH" 2>/dev/null; then
  echo "Feedback sink OK: $SINK_PATH"
  SINK_OK=1
else
  echo "## Warning: Feedback sink unreachable"
  echo "Path: $SINK_PATH"
  echo "Telemetry events will not be recorded for this drive."
  SINK_OK=0
fi
```

**Failure behaviour (warn, not hard-halt):**

If the write fails (`SINK_OK=0`):

1. Emit the structured warning block to the user:
   ```
   ## Warning: Feedback sink unreachable
   Path: debugging/logs/agent_telemetry.jsonl
   All telemetry for this drive will be lost (submit-failed events will not be recorded).
   Fix the sink path or confirm before proceeding.
   ```
2. Ask the user: **"Proceed without telemetry? (yes / no)"**
3. On `yes`: set `SINK_OK=1` and continue (user acknowledged the risk).
4. On `no`: halt with `{status: "blocked", blocker_summary: "feedback sink unreachable — user declined to proceed"}`.

Do NOT silently continue with `SINK_OK=0` — the warning must be surfaced to the user.

If the write succeeds (`SINK_OK=1`), proceed to §1.1 without any user-facing message.

**Root cause context:** During EPIC-FeedbackSinkPreDriveCheck (2026-05-27), 23 `submit-failed`
events occurred over an entire drive without detection, yielding zero telemetry for the
retrospective. This pre-flight step closes that gap.

---

### §1.1 Pseudocode

```
1.  READ Master_Plan.md and every ticket file in the epic folder
    (sub-tickets at root, plus the done/ subfolder for completed work).

2.  BUILD dependency graph G:
      nodes = { ticket_path for each non-done ticket }
      logical_edges    = { (a, b) | b in a.depends_on (transitively closed) }
      physical_edges   = { (a, b) | a.files_touched ∩ b.files_touched ≠ ∅ }
      G = nodes ∪ logical_edges ∪ physical_edges
    (Both edge sets are undirected for the purpose of the parallelism
    gate; depends_on is also retained as a directed edge for ordering.)

3.  COMPUTE next_ready_batch:
      ready    = { t ∈ G | every t' in t.depends_on has status done }
      batch    = a maximal antichain of `ready` such that
                   ∀ a, b ∈ batch:  a.files_touched ∩ b.files_touched = ∅
                                AND neither a depends_on b nor b depends_on a
                                    (transitive closure).
    Pick batch by ascending NN execution-order prefix when ties exist.

4.  DISPATCH one ticket-supervisor per ticket in `batch` via the Agent tool.
    Each child receives its `ticket_path` as input.
    Ticket-supervisors run at depth 1 (the build-feature workflow is at depth 0).

    > **[DISPATCH PROHIBITION]** NEVER render an `Agent` tool-call input as
    > user-facing prose and then stop. If the next intended action is an `Agent`
    > tool call, the workflow MUST invoke the tool. Describing the call and
    > stopping is always an error — it leaves on-disk state unchanged and
    > appears as a successful run to the user.

    > **[DISPATCH VERIFICATION — mandatory after every fanout]** After issuing
    > all N `Agent` tool calls, confirm N tool-call result blocks appear in
    > context before proceeding to step 5. If fewer results appear than calls
    > issued, halt and report the missing dispatches to the user. Do NOT assume
    > the missing dispatches completed silently.

    **Before dispatching each ticket-supervisor**, emit `supervisor_dispatch`
    (non-blocking) per ticket in the batch:
    ```bash
    python .claude/skills/agent-telemetry/scripts/emit_event.py \
      --agent "build-feature" --event supervisor_dispatch \
      --ticket "<ticket_path>" \
      --log debugging/logs/agent_telemetry.jsonl || true
    ```

5.  WAIT for the entire batch to complete (barrier).
    Each child returns either:
      - { status: "done" }                          → ticket fully signed off
      - { status: "blocked", payload: <§6 schema> } → user input required
      - { status: "failed",  payload: <§6 schema> } → halt-class failure

6.  HALT-or-LOOP:
      IF any child returned "blocked" with a structural blocker
          (i.e. suggested_remediation requires user decision before
           any further ticket in the epic can proceed):
        → halt the epic, surface every pending payload to the user.
        Emit `epic_halted` (non-blocking):
        ```bash
        python .claude/skills/agent-telemetry/scripts/emit_event.py \
          --agent "build-feature" --event epic_halted \
          --outcome blocked \
          --log debugging/logs/agent_telemetry.jsonl || true
        ```
      ELSE-IF any child returned "blocked" but the blocker is local
              to that ticket (other tickets remain independent):
        → mark that ticket blocked, KEEP the epic running, GOTO 3
          (the blocked ticket will be excluded from `ready` until
           the user resolves it).
      ELSE-IF every ticket in the epic is now `done`:
        → emit "epic complete", proceed to PR open (one PR per epic).
        Emit `epic_complete` (non-blocking):
        ```bash
        python .claude/skills/agent-telemetry/scripts/emit_event.py \
          --agent "build-feature" --event epic_complete \
          --outcome ok \
          --log debugging/logs/agent_telemetry.jsonl || true
        ```
      ELSE:
        → GOTO 3.
```

### §1.1.1 Mid-drive ticket pickup (documented contract)

Step 1 of the loop (`READ Master_Plan.md and every ticket file in the epic folder`) is evaluated **fresh on every pass** through the loop — it is not a one-time snapshot taken at epic start. This means:

- If a parallel branch adds a sub-ticket to `Master_Plan.md` and the file lands in the worktree via a mid-drive `merge origin/main`, the new `NN_*.md` file will be present in the epic folder the next time the supervisor re-enters step 1.
- The supervisor will include that ticket in the dependency graph and compute its `next_ready_batch` position exactly as if the ticket had been there from the beginning.
- **This is a guaranteed contract, not accidental behaviour.** It was validated during EPIC-PortableWorkflowHardening: ticket `04_audit_tickets_28_to_35_retroactively.md` was added via a mid-drive merge and picked up cleanly on the subsequent pass. See `docs/retrospectives/EPIC-PortableWorkflowHardening.md` §What Went Well (conflict-resolver item) and §Friction Points (item 2) for the concrete example.

No additional enforcement is required: the per-pass scan is inherent to the loop structure. Operators should be aware of this behaviour — it is a feature, not a side-effect.

### §1.2 File-touch gate (definition)

> Two tickets `a` and `b` are **parallel-safe** iff:
>
> 1. `a.files_touched ∩ b.files_touched = ∅`  *(disjoint physical footprint)*, AND
> 2. neither `a depends_on b` nor `b depends_on a` under the **transitive closure** of `depends_on` *(no logical dependency chain)*.

Both conditions must hold. The file-touch set is authoritative — it is populated by `business-analyst` / `refinement` and validated by the frontmatter guard. If a ticket's `files_touched` is missing or empty, the build-feature workflow MUST treat that ticket as conflicting with every other ticket and run it serially (default-conservative).

### §1.3 Halt conditions (epic-level)

The build-feature workflow halts the entire run only when:

- A child returns `{status: "blocked"}` and the blocker is **structural** — i.e. the suggested remediation requires resolving an ambiguity (`question`-class) that affects multiple tickets, OR a phase agent that is on the critical path of every remaining ticket has returned `failed`.
- The dependency graph contains a cycle that survives `files_touched` projection (this should never occur — refinement prevents it — but treat it as a halt-class invariant violation).
- The commit-phase lock (§5) cannot be released after a child crash (lock-recovery requires user intervention).

In all other blocker scenarios, the epic continues with the remaining independent tickets while the blocked ticket awaits user input. See §6.
### §1.4 Worktree lifecycle — close-worktree prohibition

The build-feature workflow **MUST NOT** invoke `close-worktree`, `git worktree remove`, or
`git branch -D` until **every sub-ticket in the epic is in `done/` status**.

Premature invocation of `close-worktree` destroys the branch ref while in-progress commits
survive as unreachable orphan objects in the object database. This failure mode was observed
in EPIC-AgentRegistryAsSourceOfTruth (2026-05-14) and required full manual git plumbing to
recover (see below).

**Safe stop protocol — when the workflow must pause mid-epic:**

1. Commit any in-progress staged implementation.
2. Update the ticket file to reflect which agents have signed off so far.
3. Return control to the user with a clear status summary. **Do NOT call `close-worktree`.**

#### §1.4.1 All-Tickets-Done Gate (mandatory counting gate before close-worktree)

When the build-feature workflow reaches the post-completion chain Step 5 (Worktree Cleanup),
it MUST run this counting gate before invoking worktree cleanup:

```python
# Pseudocode — implement in whatever language the supervisor runs in
open_tickets = [
    f.name for f in Path(epic_folder).glob("*.md")
    if f.name != "Master_Plan.md"
    and parse_frontmatter_status(f) != "done"
]

if open_tickets:
    abort(
        f"Worktree cleanup blocked: {len(open_tickets)} sub-ticket(s) "
        f"not done: {open_tickets}. Complete or defer them first."
    )
    # Do NOT proceed with worktree cleanup.
    # Do NOT call close-worktree.
else:
    ALL_TICKETS_DONE = True
    log("All-Tickets-Done gate passed: ALL_TICKETS_DONE=true")
    # Proceed to worktree cleanup.
```

**ALL_TICKETS_DONE confirmation token**: the workflow MUST log the string
`ALL_TICKETS_DONE=true` (visible in the transcript) after the gate passes.
Worktree cleanup MUST NOT proceed unless this token has been set in
the current workflow invocation. This makes the gate outcome auditable.

**Worktree recovery procedure (branch ref destroyed, commits survive as orphans):**

```bash
# 1. Find orphan commit SHAs
git fsck --unreachable | grep commit

# 2. Identify the correct HEAD from commit messages
git show --oneline <sha>   # repeat for each candidate

# 3. Recreate the worktree registration files
# Path: <main-repo>/.git/worktrees/<wt-name>/
echo "ref: refs/heads/<branch>" > .git/worktrees/<wt-name>/HEAD
echo "<absolute-path-to-wt>/.git" > .git/worktrees/<wt-name>/gitdir
echo "../.." > .git/worktrees/<wt-name>/commondir

# 4. Recreate the worktree's .git pointer (inside the worktree folder)
echo "gitdir: <main-repo>/.git/worktrees/<wt-name>" > <wt>/.git

# 5. Restore the branch ref
git -C <wt> update-ref refs/heads/<branch> <sha>

# 6. Recover working-tree files
git -C <wt> restore .
```

See `docs/how-to/epic-supervisor-recovery.md` for the full step-by-step recovery guide.

### §1.5 Ticket close-out — two-pass pattern (implementation + status-checker)

When running individual ticket-supervisors (not a full epic run), the supervisor
naturally stops after the commit phase **without** moving the ticket file to `done/` or
flipping `pull-request: needed → signed_off`. This is correct for parallel safety but
leaves the ticket visible to the ticket-prioritizer as "ready" — causing it to appear as
unimplemented even after its commit has landed.

**Standard two-pass close-out:**

1. Run the implementation supervisor to completion (through the commit phase).
2. Dispatch a `status-checker` agent on the same ticket.
3. The status-checker verifies all frontmatter agents are in `{signed_off, not_needed}`,
   moves the ticket to `done/`, and flips `pull-request: needed → signed_off` (per
   epic convention: one PR per epic, not per ticket).

This "implementation supervisor → status-checker close-out" pattern is the expected idiom
for individual ticket runs within a multi-ticket epic. Validate: after the status-checker
runs, `git status` on the ticket path should show the file in the `done/` subfolder.



---

## §2 Ticket-level Algorithm (ticket-supervisor)

The five-step loop from the spec (§6.2). One `ticket-supervisor` instance (running at depth 1) drives one ticket from its current `needed` agents to fully signed off. The ticket-supervisor does NOT have access to the Agent tool (depth-1 constraint); instead it reads phase agent templates and executes their instructions inline.

### §2.0 Pre-flight — working-tree hygiene

Before executing the first phase agent for a ticket, the ticket-supervisor MUST run `git status`
and inspect the output for **untracked files that belong to a different epic**.

Cross-branch contamination is possible when a sub-agent from a different worktree context
writes files using a path that resolves into the current working tree. The contaminating
files appear as untracked and carry names or content that reference a different epic (e.g.,
paths containing `EPIC-Foo` while the current epic is `EPIC-Bar`).

**Contamination detection heuristic:**

- Filename contains an epic name other than the current epic.
- File content (first 5 lines) references modules, tickets, or ADRs not in the current epic scope.
- File was not listed in the current ticket's `files_touched` and has no obvious relationship
  to the current ticket's goal.

**What to do if contamination is detected:**

1. **Do not auto-stage, do not auto-delete.** Surface the finding to the parent (escalate to
   the user or the build-feature workflow with a description of the suspicious files and their apparent
   origin).
2. Await explicit user authorization before removing or staging the files.
3. Once authorized, commit a chore commit removing the foreign files with a message like:
   `chore: remove cross-branch orphan files from <other-epic>` — separate from any
   implementation commit.

This was observed in EPIC-AgentRegistryAsSourceOfTruth (2026-05-15) where ~835 lines of
scripts from a different epic leaked into the worktree as untracked files and confused
every ticket-supervisor that ran until a cleanup commit removed them.

### §2.1 Pseudocode

```
1.  READ ticket frontmatter `agents` map.
    LET pending = [ name for name, status in agents
                          if status == "needed" ]
    IF pending is empty:
      → mark ticket done (move file to done/, flip status: done),
        return {status: "done"}.
    LET next_agent = first(pending) in natural order
                     (declaration order in the YAML; ties broken
                      by canonical phase ordering — architect-review,
                      test-writer (priority 5, before coders),
                      python-coder (priority 6), sql-coder (priority 7),
                      test-runner, pr-reviewer, commit, pull-request,
                      status-checker, documentation-expert).

    # requires_adr pre-flight override
    IF frontmatter.requires_adr == true
       AND agents["adr-author"] == "needed"
       AND "adr-author" NOT IN { name for name, status in agents
                                       if status == "signed_off" }:
      → OVERRIDE next_agent = "adr-author"
        (dispatches ADR authoring BEFORE any coder or documentation agent,
         regardless of declaration order in the YAML).
    # Once adr-author is signed_off, the override no longer fires and
    # natural order resumes.

    # docs-only / config-only test-writer skip rule
    IF next_agent == "test-writer":
      READ ticket body. Locate the `## Test Requirements` block (if present).
      Parse the `tests:` YAML array inside that block.
      IF tests array is EMPTY (`tests: []`) OR the `## Test Requirements`
         block is absent entirely:
        → SKIP test-writer: do NOT execute it.
           Mark agents["test-writer"] = "signed_off" in frontmatter.
           Append comment to `## Comments`:
             ### <today> <time> — ticket-supervisor (status: ok)
             test_requirements empty — test-writer phase skipped (docs-only or config-only ticket)
           GOTO top of loop (pick next pending agent from updated map).
    # If tests: [] or block absent, proceed directly to next needed agent.
    # Otherwise (tests array has entries), dispatch test-writer normally.

2.  READ next_agent's template via the inline execution protocol (§9):
      a. Look up next_agent in `agent_registry.json` → get `template_path`.
      b. Read the template file via the Read tool.
      c. EXECUTE the template's instructions inline using Read/Edit/Write/Bash
         (the ticket-supervisor does NOT use the Agent tool — depth-1 constraint).
      d. The template's signoff instructions are followed inline;
         on completion, the ticket file has a new `## Comments` heading
         and updated `agents:` + `## Sign-offs` rows.

    **Before executing**, emit `agent_start` (non-blocking):
    ```bash
    python .claude/skills/agent-telemetry/scripts/emit_event.py \
      --agent "ticket-supervisor" --event agent_start \
      --ticket "<ticket_path>" --phase "<next_agent>" \
      --log debugging/logs/agent_telemetry.jsonl || true
    ```

    # post-coder contract-shrinking check (supervisor-side warn, not block)
    IF next_agent IN {"python-coder", "sql-coder"}:
      RUN: git diff --name-only HEAD~1..HEAD -- "*.py" | grep -E "test_|_test\.py$"
      LET deleted_tests = files listed by `git diff --name-only --diff-filter=D HEAD~1..HEAD -- "test_*.py" "*_test.py"`
      LET diff_lines = output of `git diff HEAD~1..HEAD`
      LET weakening_found = (
            any(deleted_tests)
            OR diff_lines contains r"^\+.*pytest\.skip"
            OR diff_lines contains r"^\+.*pytest\.mark\.xfail"
            OR diff_lines contains r"^\+.*@unittest\.skip"
            OR diff_lines contains r"^\+.*@unittest\.expectedFailure"
      )
      IF weakening_found:
        → append warning comment to `## Comments` (do NOT block, do NOT change agent status):
          ### <today> <time> — ticket-supervisor (status: ok)
          contract-shrinking-warning: coder phase completed but potential test weakening detected.
          Details: <specific files and patterns found, e.g. "test_foo.py deleted; pytest.mark.xfail added in test_bar.py">
          Pre-commit hook will block if this reaches commit phase.
    # This is the diagnostic/audit layer. The pre-commit hook (check_contract_shrinking.py)
    # is the blocking layer. This warn does NOT halt the pipeline or change the sign-off.

3.  RE-READ the ticket. Locate the LAST `## Comments` heading
    (parser-strict regex from signoff §5.4):
      ### YYYY-MM-DD HH:MM — <agent> (status: ok|handoff|blocker|question)

4.  ROUTE on the status tag using the table below (§2.2).

    When the status is `ok`, emit `agent_signoff` (non-blocking):
    ```bash
    python .claude/skills/agent-telemetry/scripts/emit_event.py \
      --agent "ticket-supervisor" --event agent_signoff \
      --ticket "<ticket_path>" --phase "<next_agent>" \
      --outcome ok \
      --log debugging/logs/agent_telemetry.jsonl || true
    ```

5.  After routing, GOTO 1 unless routing produced a terminal outcome
    (done | halted-for-user | blocked-for-brainstorm-escalation).
```

### §2.2 Routing table

| Comment status | Action | Loop control |
|---|---|---|
| `ok` | No-op (the agent has already self-marked `signed_off`). | Continue: GOTO 1. |
| `handoff` | Read the prose body to identify the named recipient sibling. Set that sibling's status to `needed` if not already, and override "natural order" — make it the next pick. | Continue: GOTO 1. |
| `blocker` | Run **failure adjudication** (§3). May retry inline, may re-execute a sibling template, may return blocked for brainstorm escalation, may halt. | Loop control depends on adjudication branch. |
| `question` | HALT the ticket. Build the user-escalation payload (§6) and return `{status: "blocked", payload: ...}` to the build-feature workflow (main context). | Terminal for this `ticket-supervisor` until user replies. |

### §2.3 Sign-off invariants (delegate to `signoff` skill)

After every inline phase execution completes, the ticket file MUST satisfy the validator rules in [`signoff` §5](../signoff/SKILL.md). If a parity violation is detected (frontmatter `agents` ≠ `## Sign-offs`), the ticket-supervisor halts immediately with a `failed` payload — it does not attempt to repair the ticket.

---

## §3 Failure Adjudication

When the latest comment status is `blocker`, the ticket-supervisor walks this four-case ladder. The cases are ordered by escalation severity; pick the **first** matching case.

### §3.1 Case 1 — Trivial mechanical failure

**Pattern**: the blocker comment names a single file + line + concrete fix (test failure pointing to one assertion, lint error, hook failure with autofix-class diagnostic, single missing import).

**Action**: retry inline — re-read the **same** phase agent's template and re-execute its instructions with the blocker comment body as additional context. **Cap**: 1 retry per phase per ticket (§4).

Emit `agent_retry` before the retry (non-blocking):
```bash
python .claude/skills/agent-telemetry/scripts/emit_event.py \
  --agent "ticket-supervisor" --event agent_retry \
  --ticket "<ticket_path>" --phase "<failing_agent>" \
  --retry-count 1 \
  --log debugging/logs/agent_telemetry.jsonl || true
```

### §3.2 Case 2 — Cross-agent rework

**Pattern**: the blocker comment is from a **review-class** phase (`pr-reviewer`, `architect-review`, `status-checker`) and explicitly names a sibling whose work needs revision (e.g. "re-execute sql-coder with this finding").

**Action**: flip the named sibling from `signed_off` back to `needed` (the sibling self-resets via its own next sign-off cycle — supervisor does not directly mutate the sibling's row), then re-read the named sibling's template and re-execute it inline with the reviewer's comment as additional context. **Cap**: 1 re-execution per phase pair per ticket (§4).

Emit `agent_respawn` before the sibling re-execution (non-blocking):
```bash
python .claude/skills/agent-telemetry/scripts/emit_event.py \
  --agent "ticket-supervisor" --event agent_respawn \
  --ticket "<ticket_path>" --phase "<named_sibling>" \
  --retry-count 1 \
  --log debugging/logs/agent_telemetry.jsonl || true
```

### §3.3 Case 3 — Open-ended design choice (brainstorm escalation)

**Pattern**: the blocker comment describes an architectural ambiguity, multiple plausible approaches, or a question whose answer requires weighing trade-offs (e.g. "should this be a JSONB column or a separate table?", "should we cache here or in the consumer?").

**Action**: the ticket-supervisor returns `{status: "blocked", escalation_type: "brainstorm", blocker_comment: <full comment body>, ticket_path: <path>}` to the build-feature workflow (main context). The main context then dispatches `brainstorm-lead` at depth 1 via the Agent tool, passing the blocker comment and relevant ticket sections as input. `brainstorm-lead` runs its analysis and returns a synthesized recommendation to the main context. The main context appends a `(status: question)` comment to the ticket containing the recommendation and surfaces it to the user via the §6 payload. **Cap**: 1 brainstorm-lead invocation per ticket (§4).

**Key constraint**: the ticket-supervisor does NOT spawn brainstorm-lead itself (depth-1 agents cannot use the Agent tool). It returns control to the main context with the structured payload above, and the main context handles the dispatch.

### §3.4 Case 4 — Otherwise (halt)

**Pattern**: any blocker that does not match cases 1–3 — e.g. infrastructure failure, secret missing, user-only decision, or a Case 1/2/3 retry that has already exhausted its cap.

**Action**:

1. Set `agents.<phase>: failed` (the agent already did this via `signoff` §4; supervisor verifies).
2. Emit `agent_failure` (non-blocking) before building the escalation payload:
   ```bash
   python .claude/skills/agent-telemetry/scripts/emit_event.py \
     --agent "ticket-supervisor" --event agent_failure \
     --ticket "<ticket_path>" --phase "<failing_agent>" \
     --outcome failed \
     --log debugging/logs/agent_telemetry.jsonl || true
   ```
3. Build the user-escalation payload (§6).
4. Return `{status: "blocked", payload: ...}` to the build-feature workflow (main context).

The build-feature workflow decides whether to halt the epic or continue with independent tickets (§1.3 + §6).

---

## §4 Retry Caps (numeric)

Every cap below is a hard ceiling enforced per-ticket. When exceeded, the supervisor MUST fall through to §3.4 (halt + escalate).

| Cap | Limit | Scope |
|---|---|---|
| **Inline retry after own failure** (§3.1) | **1 per phase per ticket** | A second consecutive failure of the same phase on the same ticket → fall through to §3.4. |
| **Sibling re-execution from review** (§3.2) | **1 per phase pair per ticket** | A "phase pair" is the (reviewer, coder) tuple, e.g. (pr-reviewer, python-coder). After one round-trip, a second blocker from the same reviewer against the same coder → fall through to §3.4. |
| **brainstorm-lead escalations** (§3.3) | **1 per ticket** | A ticket gets at most one brainstorm. A second design-class blocker on the same ticket → fall through to §3.4 directly (do not escalate to brainstorm-lead again). |
| **Commit hook autofix loop** | inherited from `precommit-autofix` skill (1 retry) | Owned by the commit phase agent itself; supervisor does not retry commits. |
| **Conflict-resolver chain** | inherited from existing chain | Owned by the pull-request phase agent itself; supervisor does not retry. |

The supervisor maintains a small in-memory counter dictionary keyed by `(ticket_path, phase, cap_kind)`. The counter is per-supervisor-invocation; it is NOT persisted to the ticket file. If a supervisor crashes and is re-spawned mid-ticket, the counters reset — that is acceptable because the on-disk `agents` map and comment log already encode the relevant history, and a re-spawned supervisor reading a `failed` row will route to §3.4 on its own.

---

## §5 Commit-phase Serialization Lock

The commit and pull-request phases mutate the git index and `HEAD`; they cannot run concurrently across sibling tickets in the same worktree. We enforce mutual exclusion via a tiny lock file at the worktree root.

### §5.1 Lock file

- **Path**: `<worktree_root>/.epic-commit-lock`
- **Contents**: a single line, `<ticket_path> <pid> <ISO8601-timestamp>`, for human debugging only. The mere existence of the file is the lock.
- **Lifetime**: held only across the commit (or pull-request) phase of one ticket; deleted on success OR failure.

### §5.2 Acquire recipe (atomic-create)

The supervisor MUST use an atomic create-if-not-exists primitive. Two pragmatic equivalents:

**Bash (POSIX, portable)**:
```bash
# Atomic: succeeds iff the file did not exist; never overwrites.
# `set -C` (noclobber) makes `> file` fail if file exists.
( set -C; printf '%s %s %s\n' "$TICKET_PATH" "$$" "$(date -Iseconds)" \
    > "$WORKTREE_ROOT/.epic-commit-lock" ) 2>/dev/null \
  && acquired=1 || acquired=0
```

**Python (when supervisor is implemented in code, not bash)**:
```python
# O_CREAT | O_EXCL is atomic across all POSIX FSes.
fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
os.write(fd, f"{ticket_path} {os.getpid()} {datetime.now().isoformat()}\n".encode())
os.close(fd)
```

If acquisition fails (`acquired=0` / `FileExistsError`), the supervisor MUST sleep briefly (exponential backoff starting at 250ms, capped at 8s) and retry. After 60 seconds total wait, fall through to §3.4 with blocker `commit-lock-stuck`.

### §5.3 Release recipe

Release is unconditional — both on success and on every failure path:

```bash
rm -f "$WORKTREE_ROOT/.epic-commit-lock"
```

Wrap the entire commit-phase invocation in a `trap`-style `finally` so the lock is released even if the supervisor itself crashes. The supervisor's child commit-agent does NOT touch the lock file directly; the supervisor owns the lock for its child's lifetime.

### §5.4 Recovery

If the build-feature workflow is restarted and finds an existing `.epic-commit-lock` whose `<pid>` is not alive, it MUST log a warning and `rm -f` the stale lock before resuming. A live PID inside an unfamiliar lock means another supervisor instance is running — halt and surface to user (§3.4).

### §5.5 Standing kill auth scope (idle-only)

When the orchestrator has been granted standing authorization to kill orphan
pytest/sql-test worker processes (e.g. during the orphan-process sweep at
pre-flight step 6), that authorization applies **only to truly idle processes**.
Killing an active worker would terminate a legitimate test run in a parallel
session and corrupt its result file.

**Both conditions must hold before killing a process:**

1. **Parent PID is dead.** The process whose PID matches the `PPID` of the
   candidate worker no longer exists (i.e. `Get-Process -Id <ppid>` returns
   nothing on Windows, or `kill -0 <ppid>` returns non-zero on POSIX).
2. **CPU usage is near zero.** A 1-2 second CPU sample shows the process
   consuming less than ~2% CPU -- it is not actively running tests.

**If either condition fails**, the orchestrator MUST surface the process to
the user (PID + command line + CPU%) and ask for a manual decision. Do NOT
auto-kill.

**PowerShell idle-check snippet (per PID):**

```powershell
# Check whether PID $pid is idle before killing it
$proc = Get-Process -Id $pid -ErrorAction SilentlyContinue
if (-not $proc) { Write-Host "$pid already gone"; return }

# Sample CPU over 1.5 seconds
$before = $proc.TotalProcessorTime
Start-Sleep -Milliseconds 1500
$proc.Refresh()
$after  = $proc.TotalProcessorTime
$cpuPct = [math]::Round(($after - $before).TotalSeconds / 1.5 * 100, 1)

# Check parent is dead
$parentAlive = (Get-Process -Id $proc.Parent.Id -ErrorAction SilentlyContinue) -ne $null

if (-not $parentAlive -and $cpuPct -lt 2) {
    Stop-Process -Id $pid -Force
    Write-Host "Killed idle orphan PID $pid (CPU $cpuPct%)"
} else {
    Write-Host "Skipped PID $pid -- parent_alive=$parentAlive cpu=$cpuPct% -- surface to user"
}
```

**Cross-reference:** user-memory feedback entry
`~/.claude/projects/<project-slug>/memory/feedback_kill_idle_processes_only.md`
captures the original user correction that prompted this rule
(EPIC-ArchitectureDocsEnforcement, 2026-05-14).

**Exception — commit-phase preamble kill is unconditional.** The idle-only
rule (§5.5) applies to the pre-flight sweep. The commit agent's Step 0
preamble kill (`pkill -f "pytest" || true` / `taskkill ...`) is deliberately
**unconditional** — it terminates all pytest workers regardless of CPU or
parent status. This is safe because by the time commit fires, all test phases
for the current ticket have completed and any remaining workers are stale.
Workers in parallel tickets are isolated by worktree (separate working dirs).

### §5.6 Stage-all-in-scope before `git commit`

Before invoking `git commit`, the commit-phase agent MUST run `git status` and
stage every modified file that belongs to the epic scope — NOT just the files
explicitly listed in the ticket's `files_touched`.

**Why.** Several pre-commit hooks auto-modify files in place during the commit:

- `transform-decision-history` (pre-stage) injects the current `HH:MM` into
  date-only DECISION HISTORY timestamps and appends a `(#TICKETLESS …)` tail-tag
  when none is present, then calls `git add` on the modified file. Write entries
  as `YYYY-MM-DD HH:MM [Author]: … (#EPIC-Name/NN)` to avoid any transformer
  output in the hook log.
- `apply_sql_changes` reformats SQL files reloaded into the local DB.
- `check_doc_frontmatter` may rewrite `last_updated:` fields.

If any of those files are present in the working tree but unstaged when the
hooks run, the hooks' rewrites collide with the unstaged version when git
attempts to stash-pop after the hook. The commit fails with a stash-conflict
error that requires manual recovery.

**Recipe (run before `git commit`):**

```bash
# 1. Inspect every modified path in the worktree.
git status --short

# 2. Stage every path that belongs to the epic (NOT files owned by other
#    in-flight branches or unrelated local work). When in doubt, prefer
#    `git add <explicit-path>` over `git add .` so unrelated files do not
#    get swept into the commit.
git add <every-in-scope-path>

# 3. Verify nothing in-scope is left unstaged before committing.
git status --short
```

**Cross-reference:** EPIC-AgentSupervisorPolish2 retrospective §KI-2 captures
the original stash-conflict incident.

---

## §6 User Escalation Contract

When a ticket halts (Case §3.4 fall-through, or `question`-class comment from §2.2), the ticket-supervisor returns this exact payload to the build-feature workflow (main context), which in turn relays it to the user.

### §6.1 Payload schema

```
{
  "ticket_path": "<absolute path>",
  "phase":       "<phase agent name, e.g. python-coder | pr-reviewer | commit>",
  "blocker_summary":      "<one sentence>",
  "suggested_remediation":"<text — what the user should decide or provide>"
}
```

All four fields are required. The values are:

- `ticket_path` — absolute filesystem path to the ticket markdown file.
- `phase` — the agent name as it appears in the ticket's `agents:` map (lowercase-with-hyphens). For brainstorm-lead-mediated questions, use `brainstorm-lead` here.
- `blocker_summary` — a single sentence (≤ 120 chars) lifted or distilled from the latest `## Comments` body.
- `suggested_remediation` — a plain-English description of what the user must do (e.g. "Choose between approach A (column-per-symbol) and approach B (JSONB blob); see brainstorm-lead recommendation in the latest comment.").

### §6.2 Epic-level continuation rule (explicit)

> **The build-feature workflow MAY continue processing other tickets in the current batch (and subsequent batches) while a blocked ticket waits for user input**, provided the remaining tickets do not depend on the blocked one (transitively, via either `depends_on` or `files_touched`).

Equivalent phrasing: a single ticket's user-escalation does NOT halt the epic by default. The epic only halts when the §1.3 conditions are met (structural blocker, dependency-cycle invariant violation, or unrecoverable lock state).

When the user replies and resolves the blocker, the supervisor flow is:

1. User edits the blocked ticket directly (e.g. flips a `failed` row to `needed`, or appends an answering comment with the chosen approach).
2. User resumes via `/build-feature <epic>` (or however the harness is wired).
3. The build-feature workflow re-reads `Master_Plan.md`, rebuilds the dependency graph, and re-enters its main loop at §1 step 3 — the resolved ticket is once again `ready`.

---

### §6.3 Standing kill auth scope (idle-only)

When the pre-flight orphan-process sweep (Pre-Flight step 6) or any other sweep
grants **standing authorization** to kill matching processes, that authorization
is **scoped to idle orphans only**. An idle orphan satisfies BOTH of the
following conditions simultaneously:

1. **Parent process is dead.** `Get-Process -Id <parent_pid>` (PowerShell) returns
   nothing, or `psutil.pid_exists(ppid)` (Python) returns `False`.
2. **CPU usage is near zero.** A 1-2 second CPU sample shows usage below 2%
   (i.e. `proc.cpu_percent(interval=1.5) < 2` via psutil).

If **either** condition fails — the parent is still alive, OR the CPU sample
is above threshold — the orchestrator MUST surface the process to the user
rather than killing it. An active test run can look identical to an orphan by
name alone; blanket name-pattern kills will terminate in-flight work in parallel
sessions.

**PowerShell idle-check snippet (per-PID):**

```powershell
$pid_to_check = 12345  # PID to check
$proc = Get-Process -Id $pid_to_check -ErrorAction SilentlyContinue
if (-not $proc) {
    Write-Host "PID $pid_to_check not found — already gone"
} else {
    # Sample CPU over 2 seconds
    $cpu1 = $proc.CPU
    Start-Sleep -Seconds 2
    $proc.Refresh()
    $cpu2 = $proc.CPU
    $cpuDelta = $cpu2 - $cpu1
    if ($cpuDelta -lt 0.1) {
        Write-Host "PID $pid_to_check is IDLE (cpu delta=$cpuDelta) — safe to kill"
    } else {
        Write-Host "PID $pid_to_check is ACTIVE (cpu delta=$cpuDelta) — DO NOT kill"
    }
}
```

Cross-reference: `~/.claude/projects/<project-slug>/memory/feedback_kill_idle_processes_only.md`
(user memory feedback entry that captured the original correction during
EPIC-ArchitectureDocsEnforcement, 2026-05-14).

---

## §8 Known Constraint: Write-Tool Scope Is Bounded by the Git Worktree

### §8.1 Statement

Sub-agents (`documentation-expert`, `python-coder`, `sql-coder`, and all other phase agents) running under the harness have their **Write-tool and Bash-write permission scope bounded by the git worktree root**. Attempts to write files outside this boundary — including `~/.claude/projects/<hash>/memory/`, `~/.claude/hooks/`, or `~/.claude/agents/` — will be denied with a permission error.

Both the `Write` tool and Bash-write variants (`cat`-heredoc, `printf` redirect) are subject to this restriction. The harness enforces it at the permission-guard layer before any filesystem operation occurs.

### §8.2 Failure Signature

A sub-agent hitting this constraint will surface one of:

- **Write tool**: `Permission denied — Write tool denied for paths outside repo`
- **Bash redirect** (`cat`/`printf`/`echo >`): non-zero exit code with a permission-denial message from the harness sandbox

The error is deterministic and unretriable by the phase agent alone — no amount of reformulating the write command will succeed while the permission guard is active.

### §8.3 Design Guidance for Tickets with Out-of-Repo Output

When a ticket's deliverable lives outside the worktree, apply the following design patterns at ticket-creation time:

1. **Mark the phase explicitly.** Add a comment to the relevant agent phase in the ticket body: `<!-- out-of-repo write — requires parent-context execution or explicit permission grant -->`. This signals to the ticket-supervisor and operator that the phase cannot be fully automated by the sub-agent harness.

2. **Document intended content in the ticket body.** Rather than having a sub-agent write the file, describe the intended file content (or include it verbatim) in an `## Out-of-Repo Outputs` block (see `ticket-authoring` skill §Body Structure). The parent context or a human operator creates the file manually using the documented content.

3. **Do not include unnecessary commit phases.** If the ticket produces no in-repo artifact — only an out-of-repo file — do NOT mark `pr-reviewer`, `commit`, or `pull-request` as `needed`. There is nothing to merge into the repository, and those phases would fail with an empty diff.

### §8.4 Cross-References

- `docs/retrospectives/EPIC-AgentSupervisorPolish.md` §Friction Points — the KI-2 case study where this constraint first caused a ticket stall (user-memory feedback file write denied).
- `tickets/99_done/EPIC-AgentSupervisorPolish/02_ki2_background_commit_silent_kill.md` §Comments — the concrete failure signature and out-of-band resolution record.
- `ticket-authoring` skill §Body Structure — the optional `Out-of-Repo Outputs` block that makes out-of-worktree intent explicit in ticket design.

---

## §7 Pre-flight & Archival Gates

Two procedural rules that bracket every epic run. §7.1 fires **before** the
workflow's main loop; §7.2 fires **after** the loop reports "epic complete"
and the workflow is about to move the epic folder into `99_done/`. Both
emerged from the EPIC-WorkflowArchitect retrospective.

### §7.1 Master_Plan portability pre-flight

Before declaring a hook, agent, or skill "portable" in a `Master_Plan.md`, the
**epic author** (not the supervisor) MUST verify zero project-domain imports.
For each candidate file, grep its top-level imports and cross-check against the
project-specific module list in `package_boundary.json`:

```bash
grep -E "^from |^import " <candidate_file> | grep -E "alembic|bybit|sql_|database_manager|live_trader|collector"
```

If the grep returns anything, the file is project-specific by ADR-020 and must
not be classified as portable. Discovering a misclassification mid-drive — as
happened with `post_checkout_drift_check.py` during EPIC-WorkflowArchitect —
forces a Master_Plan count correction and wastes coder time. This check is
fast (seconds per file) and catches the failure class at the cheapest point.

The build-feature workflow does NOT re-run this check at dispatch time; it trusts the
Master_Plan. The discipline is upstream of the workflow loop.

### §7.2 Epic archival gate (build-feature workflow)

When the main loop reports "epic complete" and the build-feature workflow is about to move
the epic folder from `tickets/01_todo/EPIC-<Name>/` (or `tickets/00_inbox/epics/EPIC-<Name>/`)
to `tickets/99_done/EPIC-<Name>/`, the workflow MUST iterate over every
sub-ticket file in the epic and verify:

1. Frontmatter `status: done` (not `todo`).
2. Every entry in `agents:` map is `signed_off` or `not_needed` (not `needed` or `failed`).
3. Every line in the `## Sign-offs` checklist is `- [x] ...` (not `- [ ]`).

If any sub-ticket fails one or more of these checks, the workflow MUST:

- **Extract** the failing ticket(s) from the epic folder to
  `tickets/00_inbox/<TICKET-YYYYMMDD-Slug>.md` with the same content (file move
  via `git mv`, optionally renaming to a standalone-ticket convention).
- **Update** `Master_Plan.md` to mark the extracted ticket(s) as
  *"deferred to standalone ticket"* with a link, so the audit trail is intact.
- **Then** archive the remaining (genuinely complete) epic.

Bulk-moving an entire epic folder to `99_done/` without per-ticket validation —
as happened with EPIC-WorkflowArchitect's T11 — hides outstanding scope and
silently breaks `check-ticket-signoff-parity` on every subsequent commit
touching the archived ticket. The cost of the validation is a few file reads;
the cost of missing it is days of confusion later.

**Re-stage moved files before the archival commit.** When `git mv` is used to
move a ticket or epic folder, any subsequent edits to the moved file (final
sign-offs, status flips, comment-append) MUST be followed by an explicit
`git add <new-path>` *before* committing. The `check-ticket-signoff-parity`
guard reads the **staged** content, not the working-tree content; without the
re-stage, the guard sees the pre-edit snapshot captured at `git mv` time and
fires on a file that is already correct on disk. Observed in
EPIC-ProdIndexHygiene (2026-05-14): the archival commit blocked because the
final pull-request sign-off had been written after the `git mv` but never
re-staged. Resolution was a single `git add <ticket-file>`.

---

## §9 Phase Agent Inline Execution Protocol

The ticket-supervisor (depth 1) cannot use the Agent tool to dispatch phase agents as sub-agents. Instead, it reads each phase agent's template at runtime and executes the template's instructions inline. This section defines the protocol.

### §9.1 Template Resolution

When the ticket-supervisor needs to execute a phase agent (e.g. `python-coder`, `commit`, `pr-reviewer`):

1. **Read `agent_registry.json`** (path: `config/agent_registry.json` relative to the repo root).
2. **Look up the agent name** in the registry. Each entry has a `template_path` field pointing to the agent's template file.
3. **Read the template file** via the Read tool at the resolved path.

```
# Pseudocode
registry = READ("config/agent_registry.json")
agent_entry = registry[next_agent]
template = READ(agent_entry.template_path)
# template now contains the full agent instructions
```

If the agent name is not found in the registry, halt with a `failed` payload: `{blocker_summary: "agent '<name>' not found in agent_registry.json"}`.

### §9.2 What "Execute Inline" Means

After reading the template, the ticket-supervisor follows its instructions directly — as if the template's content were inserted into the supervisor's own instruction stream. Concretely:

1. **Read the template's instructions** — understand what the phase agent is supposed to do (e.g. "read the ticket, implement the code changes, run tests, sign off").
2. **Use the supervisor's own tools** — Read, Edit, Write, and Bash — to carry out the instructions. The ticket-supervisor does NOT delegate; it performs the work itself.
3. **Follow the template's skill references** — if the template says "invoke the `signoff` skill", the supervisor reads and follows the signoff skill's instructions inline as well.
4. **Maintain the template's signoff protocol** — when the template's instructions say to sign off (via the `signoff` skill), the supervisor performs the same frontmatter updates, `## Sign-offs` checkbox flips, and `## Comments` appends that a spawned agent would have done.

The net effect is identical to spawning the agent: the ticket file ends up with the same frontmatter state, sign-off entries, and comments. The only difference is execution context — everything runs in the ticket-supervisor's own process.

### §9.3 Signoff When Executing Inline

The signoff protocol is unchanged from the spawned-agent model:

1. After completing the phase work, the ticket-supervisor follows the `signoff` skill's atomic sign-off recipe (§2 of the signoff skill) to update the `agents:` map and `## Sign-offs` checklist.
2. The ticket-supervisor appends a `## Comments` entry using the parser-strict heading format from the signoff skill (§3), with the phase agent's name as the author:
   ```
   ### YYYY-MM-DD HH:MM — <phase-agent-name> (status: ok)
   <body describing what was done>
   ```
3. The comment author is the **phase agent name** (e.g. `python-coder`), not `ticket-supervisor` — this preserves the audit trail and makes comment parsing consistent with the routing table (§2.2).

### §9.4 Code Search and Research (Without research-agent)

Phase agent templates that previously relied on a `research-agent` or code-search sub-agent should use the following alternatives when executing inline:

| Need | Inline alternative |
|---|---|
| Find definitions / usages | `git grep -n '<pattern>'` via Bash |
| Find files by name | `find . -name '<pattern>' -type f` via Bash |
| Recursive text search | `grep -rn '<pattern>' --include='*.py'` via Bash |
| Read multiple files | Sequential Read tool calls |
| Understand module structure | `find . -name '*.py' -path '<module>/*'` via Bash |

These are available to the ticket-supervisor via the Bash tool and provide equivalent functionality to what a research-agent sub-agent would have delivered.

### §9.5 Error Handling During Inline Execution

If a phase agent's instructions fail during inline execution (e.g. a test fails, a file cannot be found, an edit produces a syntax error):

1. The ticket-supervisor writes a `(status: blocker)` comment as the phase agent, describing the failure.
2. The supervisor then routes the blocker through the standard failure adjudication ladder (§3).
3. For retry (§3.1), the supervisor re-reads the same template and re-executes with the blocker context.

This is functionally identical to how a spawned agent would have reported a blocker — the only difference is that the failure is detected in-process rather than via a returned result.

---

## §8 References

- [`signoff` skill](../signoff/SKILL.md) — canonical status enum (`not_needed | needed | signed_off | failed`), atomic sign-off Edit recipe (`§2`), comment-append recipe with parser-strict heading schema (`§3`), failed-path protocol (`§4`), validator rules enforced by the parity guard (`§5`). **All status mutation lives there; this skill never duplicates it.**
- [`ticket-authoring` skill](../ticket-authoring/SKILL.md) — ticket frontmatter schema, body section order, `files_touched` and `agents` field semantics.
- [Spec: Agent Supervisor & Ticket Sign-off Design](../../../docs/superpowers/specs/2026-05-08-agent-supervisor-design.md) — full design rationale; this skill is the operational distillation of §6 (control flow), §7 (parallelism), §8 (failure handling).
