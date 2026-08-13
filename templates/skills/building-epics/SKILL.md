---
allowed-tools: Read, Edit, Bash(ls *)
description: Operational runbook loaded by `ticket-supervisor` (and historically by
  `epic-supervisor`, now deprecated per ADR-006) as its primary instruction set. Use
  when an agent needs to walk an epic ticket-by-ticket (dependency batching + file-touch
  parallelism gate), drive a single ticket through its phase agents (read `agents` map
  → spawn next `needed` → parse comment status → route ok/handoff/blocker/question),
  adjudicate failures with explicit retry caps, hold the commit-phase serialization
  lock, or escalate blockers to the user via the structured payload. Phase agents
  themselves use the `signoff` skill, not this one.
name: building-epics
---

# building-epics

This skill is the **single runbook** for the supervisory layer. It encodes the control-flow algorithms (epic-level + ticket-level), the file-touch parallelism gate, the failure-adjudication ladder, the retry caps, the commit-phase lock, and the user-escalation payload schema.

It is the operational complement to the [`signoff`](../signoff/SKILL.md) skill. `signoff` defines **what** the on-disk state means and how to mutate it; `building-epics` defines **how** supervisors decide what to do next based on that state. Status-enum semantics, frontmatter ↔ `## Sign-offs` parity, and the comment-heading schema all live in `signoff` and are not duplicated here.

If you change anything in this file, `ticket-supervisor` will see the change at its next invocation — that's the point. Adding a new retry cap or a new escalation tier is an edit to this one file, never an ad-hoc choice in a supervisor prompt.

---

## §1 Epic-level Algorithm (now inlined in `/build-feature`)

> **Note:** `epic-supervisor` is deprecated (ADR-006). `/build-feature` now owns the
> epic-level ticket batching described in this section. `ticket-supervisor` runs at
> depth 0, dispatched directly by `/build-feature` — there is no intermediate
> `epic-supervisor` layer between them.

The six-step loop from the spec (§6.1). This is the outer driver: it walks an epic until every ticket is signed off or the run is halted.

### §1.0 Feedback-Sink Reachability Pre-flight (runs before §1.1 loop)

Before entering the main epic loop (`/build-feature` step 1), verify that the feedback
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

### §1.0.1 Pre-Commit Hook Probe Pre-flight (runs after §1.0)

Before entering the main epic loop (§1.1), verify that the pre-commit hooks
are active and wired up in the epic worktree. This prevents the scenario where
a hook silently skips for the entire drive because the config was lost between
the worktree bootstrap and the drive start.

**Check (POSIX):**

```bash
python3 scripts/commit_guardian/verify_precommit_active.py --json 2>/tmp/probe_pre_drive.txt
```

Parse the JSON stdout: `{"binary": bool, "config": bool, "git_hook": bool, "canary": bool, "incomplete_build": bool, "failing_checks": [...]}`.
(`incomplete_build` is present and `true` only when the guardian scripts are not fully deployed; `failing_checks` will include `"incomplete_build"` in that case.)

**Failure behaviour (surface-and-offer, not hard-halt):**

If `failing_checks` is non-empty OR the script exits non-zero:

1. Emit the structured warning block to the user, listing each failing check:
   ```
   ## Warning: Pre-commit hook probe failed
   Worktree: <worktree_root>
   Failing checks: <list>
   Pre-commit hooks may silently skip during this drive.
   ```
2. Offer the user **three options**:
   a. **Fix and retry** — resolve the config/hooks issue (the probe describes what to fix), then re-invoke `/build-feature`. Typical fix: `build.py` wasn't run, or `.pre-commit-config.yaml` is absent.
   b. **Investigate** — inspect `probe_pre_drive.txt` and the worktree hook installation manually before deciding.
   c. **Override** — proceed despite the failing probe, accepting the risk that hooks may silently skip. This requires an explicit confirmation: "I understand hooks may skip — proceed".
3. On option (a) or (b): halt with `{status: "blocked", blocker_summary: "pre-commit hook probe failed — user must fix or override"}`.
4. On option (c) only: log `[probe-override] User accepted hook-skip risk for this drive` and continue to §1.1.

Do NOT silently continue when `failing_checks` is non-empty — the warning must be surfaced.

If `verify_precommit_active.py` is absent (graceful_skip_if_incomplete pattern), emit:
```
INFO: verify_precommit_active.py not found — probe skipped (incomplete guardian install).
```
and continue to §1.1 without blocking.

**Why this gate exists:** A worktree bootstrap can succeed (config file copied/symlinked)
but the hooks can still fail to fire if the binary is missing, the hook is not installed,
or the config is malformed. This probe checks all four conditions simultaneously.
(Source: EPIC-WorktreeQualityGateGuard, BO-1700d-2)

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

3a. VERIFY disjoint file sets: before dispatching, assert that no two tickets
    in `batch` share an entry in their `files_touched` frontmatter. If overlap
    is detected, remove the overlapping tickets from `batch` and serialize them
    in subsequent passes (treat the overlap as a physical edge, re-run step 3).

4.  DISPATCH one ticket-supervisor per ticket in `batch`, in parallel.
    Each child receives its `ticket_path` as input.

    > **[DISPATCH PROHIBITION]** NEVER render an `Agent` tool-call input as
    > user-facing prose and then stop. If the next intended action is an `Agent`
    > tool call, the supervisor MUST invoke the tool. Describing the call and
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

Both conditions must hold. The file-touch set is authoritative — it is populated by `business-analyst` / `refinement` and validated by the frontmatter guard. If a ticket's `files_touched` is missing or empty, `/build-feature` MUST treat that ticket as conflicting with every other ticket and run it serially (default-conservative).

### §1.3 Halt conditions (epic-level)

`/build-feature` halts the entire run only when:

- A child returns `{status: "blocked"}` and the blocker is **structural** — i.e. the suggested remediation requires resolving an ambiguity (`question`-class) that affects multiple tickets, OR a phase agent that is on the critical path of every remaining ticket has returned `failed`.
- The dependency graph contains a cycle that survives `files_touched` projection (this should never occur — refinement prevents it — but treat it as a halt-class invariant violation).
- The commit-phase lock (§5) cannot be released after a child crash (lock-recovery requires user intervention).

In all other blocker scenarios, the epic continues with the remaining independent tickets while the blocked ticket awaits user input. See §6.
### §1.4 Worktree lifecycle — close-worktree prohibition

`/build-feature` **MUST NOT** invoke `close-worktree`, `git worktree remove`, or
`git branch -D` until **every sub-ticket in the epic is in `done/` status**.

Premature invocation of `close-worktree` destroys the branch ref while in-progress commits
survive as unreachable orphan objects in the object database. This failure mode was observed
in EPIC-AgentRegistryAsSourceOfTruth (2026-05-14) and required full manual git plumbing to
recover (see below).

**Safe stop protocol — when the supervisor must pause mid-epic:**

1. Commit any in-progress staged implementation.
2. Update the ticket file to reflect which agents have signed off so far.
3. Return control to the user with a clear status summary. **Do NOT call `close-worktree`.**

#### §1.4.1 All-Tickets-Done Gate (mandatory counting gate before close-worktree)

When `/build-feature` reaches the post-completion chain Step 5 (Worktree Cleanup),
it MUST run this counting gate before spawning `worktree-agent`:

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
    # Do NOT spawn worktree-agent.
    # Do NOT call close-worktree.
else:
    ALL_TICKETS_DONE = True
    log("All-Tickets-Done gate passed: ALL_TICKETS_DONE=true")
    # Proceed to spawn worktree-agent.
```

**ALL_TICKETS_DONE confirmation token**: the supervisor MUST log the string
`ALL_TICKETS_DONE=true` (visible in the transcript) after the gate passes.
The worktree-agent MUST NOT be spawned unless this token has been set in
the current supervisor invocation. This makes the gate outcome auditable.

**Master_Plan status promotion (mandatory once the gate passes):** the epic-level
`status:` field in `Master_Plan.md` is NOT promoted automatically when its children
complete — it must be set explicitly. Immediately after `ALL_TICKETS_DONE=true`, and
before dispatching `/finalize-feature`:

```
Read Master_Plan.md → confirm status is currently todo/in_progress
→ Edit frontmatter status: <current> → done
```

If skipped, `/finalize-feature` archives a `status: todo` master plan into `99_done/`,
which is misleading to retrospective tooling and the archive-check gate.
(Source: EPIC-AcPipelineDeployGaps retrospective, 2026-06-17, Finding #7)

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
(Note: this doc predates ADR-006; the recovery steps remain valid — substitute `/build-feature` for `epic-supervisor` throughout.)

### §1.5 Ticket close-out — two-pass pattern (implementation + status-checker)

When running individual ticket-supervisors (not a full `/build-feature` epic drive), the supervisor
naturally stops after the commit phase **without** moving the ticket file to `done/` or
flipping `pull-request: needed → signed_off`. This is correct for parallel safety but
leaves the ticket visible to the ticket-prioritizer as "ready" — causing it to appear as
unimplemented even after its commit has landed.

**Standard two-pass close-out:**

1. Run the implementation supervisor to completion (through the commit phase).
2. Dispatch a `status-checker` agent on the same ticket.
3. The status-checker verifies all frontmatter agents are in `{signed_off, not_needed}`,
   invokes `set_ticket_status.py --status done` to mark the ticket complete (BO-400c-4),
   and flips `pull-request: needed → signed_off` (per epic convention: one PR per epic,
   not per ticket).

This "implementation supervisor → status-checker close-out" pattern is the expected idiom
for individual ticket runs within a multi-ticket epic. Validate: after the status-checker
runs, the ticket file's frontmatter shows `status: done`. The ticket file MUST remain at
its original path — do NOT move it to a `done/` subfolder (BO-400c-1).



---

## §2 Ticket-level Algorithm (ticket-supervisor)

The five-step loop from the spec (§6.2). One `ticket-supervisor` instance drives one ticket from its current `needed` agents to fully signed off.

### §2.0 Pre-flight — working-tree hygiene

Before spawning the first agent for a ticket, the ticket-supervisor MUST run `git status`
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
   the user or the epic-supervisor with a description of the suspicious files and their apparent
   origin).
2. Await explicit user authorization before removing or staging the files.
3. Once authorized, commit a chore commit removing the foreign files with a message like:
   `chore: remove cross-branch orphan files from <other-epic>` — separate from any
   implementation commit.

This was observed in EPIC-AgentRegistryAsSourceOfTruth (2026-05-15) where ~835 lines of
scripts from a different epic leaked into the worktree as untracked files and confused
every ticket-supervisor that ran until a cleanup commit removed them.

### §2.0.5 Drive-Start Status Transition (BO-400a-1)

Before spawning the first phase agent for a ticket, the ticket-supervisor MUST
invoke `set_ticket_status.py` to mark the ticket as in-progress:

```bash
python scripts/set_ticket_status.py --ticket <absolute_ticket_path> --status in_progress
```

**Idempotent re-drive (BO-400a-1-i):** If the ticket is already `in_progress`
(prior run was interrupted), the script exits 0 and prints `status: in_progress -> in_progress (no change)`.
Proceed without warning.

**Non-zero exit** from `set_ticket_status.py` is a blocker — surface to the user
and halt the ticket run. Do NOT spawn any phase agent if the status transition fails.

### §2.1 Pseudocode

> **§2.1-R1 — Synchronous phase dispatch (MANDATORY).** Every `Agent(...)` call
> that spawns a phase agent is BLOCKING: the ticket-supervisor MUST wait for the
> call to return and parse its result before doing anything else. The
> supervisor's turn MUST NOT end while a phase agent is still running. Dispatching
> a phase agent "in the background" and returning — or describing a dispatch and
> stopping — leaves the ticket half-driven and forces a re-drive.
> (Source: EPIC-WorktreeQualityGateGuard retrospective KI-1, 2026-07-06 — ticket 07's
> first supervisor ended its turn with test-writer still running.)
>
> **§2.1-R2 — Commit phase required for code-producing tickets (MANDATORY).** Any
> ticket whose `files_touched` includes source files (`.py`, `.sql`, `.js`, `.ts`,
> config, etc.) MUST list `commit: needed` in its `agents` map so the commit phase
> runs inside the drive — where the pre-commit hooks fire and the staged set is
> validated. When `commit` is absent from the map, changes are left staged and the
> caller must commit them out-of-band, bypassing the hook path. Docs-only /
> AC-only tickets may omit `commit`.
> (Source: EPIC-WorktreeQualityGateGuard retrospective KI-2, 2026-07-06 — 6 of 8
> tickets lacked `commit:` in their map, forcing per-ticket main-loop commits.)

```
1.  READ ticket frontmatter `agents` map.
    LET pending = [ name for name, status in agents
                          if status == "needed" ]
    IF pending is empty:
      → mark ticket done via set_ticket_status.py --status done (BO-400a-2),
        return {status: "done"}.
        NOTE: Do NOT use git mv to move the file to a done/ subfolder (BO-400c-1).
    LET next_agent = first(pending) in natural order
                     (declaration order in the YAML; ties broken
                      by canonical phase ordering — architect-review,
                      test-writer (priority 5, before coders),
                      python-coder (priority 6), sql-coder (priority 7),
                      test-runner, pr-reviewer (priority 11),
                      ac-validator (priority 11.5, after pr-reviewer and before commit),
                      user-surface-smoker (priority 11.5, concurrent with ac-validator),
                      ac-fulfillment-gate (priority 11.7, after ac-validator and before commit),
                      commit (priority 12), pull-request (priority 13),
                      status-checker, documentation-expert).

    # ac-validator skip rule (for tickets without ## Agent Contracts)
    IF next_agent == "ac-validator":
      READ ticket body. Check for the `## Agent Contracts` section.
      IF `## Agent Contracts` section is absent OR has no `- [ ] AC-N:` lines:
        → SKIP ac-validator: do NOT spawn it.
           Mark agents["ac-validator"] = "signed_off" in frontmatter.
           Append comment to `## Comments`:
             ### <today> <time> — ticket-supervisor (status: ok)
             ac-validator phase skipped — no ## Agent Contracts section or AC lines in ticket
           GOTO top of loop (pick next pending agent from updated map).
    # If ## Agent Contracts is present with at least one AC line, dispatch normally.

    # ac_coverage done-gate (AC-7)
    IF pending is empty AND frontmatter has `ac_coverage:`:
      LET coverage = parse frontmatter["ac_coverage"]   # format: "N/M"
      IF coverage != "M/M" (i.e. N < M):
        → BLOCK done transition:
           do NOT move ticket to done/ folder.
           do NOT flip status: done.
           Return {status: "blocked", payload: {
             ticket_path: <path>,
             phase: "ticket-supervisor",
             blocker_summary: "ac_coverage is <N/M> — not all ACs validated before done",
             suggested_remediation: "Respawn ac-validator to complete coverage, or manually mark remaining ACs covered if evidence exists outside the diff."
           }}
      # When coverage == "M/M": proceed with normal done-marking recipe.

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
      IF the `## Test Requirements` block is absent entirely:
        → SKIP test-writer: do NOT spawn it.
           Mark agents["test-writer"] = "signed_off" in frontmatter.
           Append comment to `## Comments`:
             ### <today> <time> — ticket-supervisor (status: ok)
             test_requirements empty — test-writer phase skipped (docs-only or config-only ticket)
           GOTO top of loop (pick next pending agent from updated map).
      IF block is PRESENT but tests array is EMPTY (`tests: []`):
        LET has_code_producer = any agent in ticket agents: map whose
            produces trait (from config/agent_registry.json) is "production_code"
        IF NOT has_code_producer:
          → SKIP test-writer (same actions as absent block above).
          GOTO top of loop.
        # If has_code_producer is true: do NOT skip — block is present and
        # test-writer is expected to fill in the tests array as its deliverable.
      # For computed-map tickets generated by generate_ticket_from_ac.py:
      # the ## Test Requirements block will always be present for production_code
      # agent tickets (even if tests: [] initially). The empty array is the expected
      # initial state; dispatching test-writer normally lets it populate the specs.
    # If tests array has entries, dispatch test-writer normally.
    # If block is present with empty tests but a code producer exists, dispatch normally.

2.  SPAWN next_agent with input { ticket_path: <absolute path> }.
    The agent invokes the `signoff` skill as its final action;
    on return, the ticket file has a new `## Comments` heading
    and updated `agents:` + `## Sign-offs` rows.

    **Before spawning**, emit `agent_start` (non-blocking):
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
    (done | halted-for-user | escalated-to-brainstorm-lead-and-waiting).
```

### §2.1.1a Produces-Trait Guardrail Rules

At dispatch time, the ticket-supervisor reads the `produces` field from the
dispatched agent's registry entry and applies the guardrail rules below. This
read happens once per agent dispatch, before the agent is spawned.

**Guardrail mapping:**

| `produces` value | TDD guardrails apply? | Behaviour |
|---|---|---|
| `production_code` | YES | Ensure `test-writer` runs before this agent (priority 5) and `test-runner` runs after (priority 9). If either is already `not_needed` or `signed_off` in the ticket's `agents:` map, the explicit ticket setting wins — do NOT re-inject. |
| `documentation` | NO | Neither `test-writer` nor `test-runner` are required. Skip both silently. |
| `prompt` | NO (TDD) | TDD guardrails do NOT apply. Prompt-quality guardrails apply instead (defined in the `llm-expert` template). The existing test-writer skip rule handles this via the `## Test Requirements` absence check. |
| `test_artifact` | NO | Wrapping a test-producing agent in test-writer/test-runner would be circular. |
| `review_verdict` | NO | Review agents produce verdicts, not executable code. |
| `analysis` | NO | Analysis agents produce reports/recommendations, not executable logic. |
| `orchestration` | NO | Orchestrators drive other agents; TDD guardrails do not apply. |
| `configuration` | CONDITIONAL | Apply TDD guardrails only if the configuration change is consumed by tested code (supervisor judgment). Default: NO. |
| `null` | WARN + NO | Log a warning that the agent has an ambiguous or missing produces trait, then treat as `documentation` (no TDD guardrails). Do NOT block the dispatch. |

**Priority of rules (ticket-level overrides agent-level):**

1. **Ticket-level explicit `not_needed`**: If `agents.test-writer: not_needed` is set in the
   ticket's frontmatter, test-writer is NEVER spawned, regardless of the produces trait.
2. **Ticket-level `## Test Requirements` block**: If the block is absent or `tests: []`, the
   docs-only skip rule fires and test-writer is skipped (marked `signed_off`) regardless of
   produces value.
3. **Registry produces trait**: If neither ticket-level rule fires, the produces trait determines
   whether TDD guardrails apply.

**Warning format for null produces:**

```
### YYYY-MM-DD HH:MM — ticket-supervisor (status: ok)
produces-trait-warning: agent '<agent-name>' has produces: null in registry.
TDD guardrails skipped (default: documentation behaviour). Resolve the ambiguity
in config/agent_registry.json before the next epic drive.
```

### §2.1.1 Canonical Phase Ordering Table

The priority column is the authoritative ordering for dispatch ties. Lower numbers run first.

| Priority | Agent | Notes |
|---|---|---|
| 1 | `status-checker` | Runs first; verifies system state |
| 2 | `adr-author` | ADR before coders |
| 3 | `architecture-diagram-author` | Diagram before coders |
| 3.5 | `it-po` | Per-agent contracts before architect-review |
| 4 | `architect-review` | Shapes design before implementation |
| 5 | `test-writer` | Writes failing tests before coders |
| 6 | `python-coder` | Primary implementation |
| 6 | `llm-expert` | Authoring phase agent |
| 7 | `sql-coder` | Database implementation |
| 7 | `sql-query` | Ad-hoc query authoring |
| 8 | `frontend-coder` | Frontend implementation |
| 9 | `test-runner` | Validates test suite |
| 10 | `change-scope-reviewer` | Verifies change set scope |
| 10 | `documentation-expert` | Documents changes |
| 10 | `explanation-author` | Documentation specialist |
| 10 | `how-to-author` | Documentation specialist |
| 10 | `reference-author` | Documentation specialist |
| 11 | `pr-reviewer` | Final quality gate |
| 11.5 | `ac-validator` | AC coverage gate; runs after pr-reviewer (11) and before commit (12) |
| 11.5 | `user-surface-smoker` | Surface end-to-end smoker; concurrent with ac-validator |
| 11.7 | `ac-fulfillment-gate` | AC store fulfillment gate; runs after ac-validator (11.5) and before commit (12) |
| 11.9 | `documentation-verifier` | Documentation coverage gate; runs after documentation-expert (10) and before commit (12) |
| 12 | `commit` | Atomic commit phase |
| 13 | `pull-request` | Pushes branch and opens PR |

**Flow-change pair ordering note:** For tickets generated from (change_target,
risk_surface) pairs listed in `config/guardrail_gates.yaml` `flow_change_gates:`
(e.g. `code/production`, `code/all`, `schema/production`, `schema/all`),
the computed agents map will include both `architect-review` (priority 4) and
`documentation-expert` (priority 10). This table's ordering guarantees that
architect-review (4) and documentation-expert (10) are dispatched before
python-coder (6) and sql-coder (7) — satisfying the flow-change requirement
that design review and doc planning precede implementation. No special
supervisor logic is needed beyond this priority ordering.

### §2.2 Routing table

| Comment status | Action | Loop control |
|---|---|---|
| `ok` | No-op (the agent has already self-marked `signed_off`). | Continue: GOTO 1. |
| `handoff` | Read the prose body to identify the named recipient sibling. Set that sibling's status to `needed` if not already, and override "natural order" — make it the next pick. | Continue: GOTO 1. |
| `blocker` | Run **failure adjudication** (§3). May respawn a sibling, may escalate to `brainstorm-lead`, may halt. | Loop control depends on adjudication branch. |
| `question` | HALT the ticket. Build the user-escalation payload (§6) and return `{status: "blocked", payload: ...}` to the parent epic-supervisor. | Terminal for this `ticket-supervisor` until user replies. |

### §2.3 Completion Manifest Validation (post-comment-parse step)

After parsing the latest comment status tag (step 3 of the §2.1 pseudocode) and **before** routing on it (step 4), the ticket-supervisor MUST read the `completion_manifest:` YAML block in that comment body. The manifest format is defined in [`signoff` §2b](../signoff/SKILL.md) — this section describes only the **supervisory actions** taken based on its contents.

#### Supervisor routing table for manifest state

| Manifest state | Description | Supervisor action |
|---|---|---|
| **all-true** | Every item in `completion_manifest:` is bare `true`. | Proceed normally — route on the comment status tag as usual (GOTO §2.2). |
| **ok-with-false** | Comment status is `ok` but one or more manifest items have `result: false` with a nested object. | Downgrade-to-blocker: treat the comment as if its status were `blocker` and run failure adjudication (§3). The named remediation inside the false item drives the adjudication case selection. |
| **malformed** | A manifest item has a bare `false` value (not a nested object with `result`, `reason`, and `remediation` sub-keys). See "Bare-False Rule" in `signoff` §2b. | Retry-once: re-invoke the **same** agent with a request to expand the bare `false` into a valid nested object. Cap: **1 retry per manifest, not per item** — if a second malformed manifest is returned by the same agent on the same ticket, fall through to §3.4 (halt). |
| **absent** | The comment body contains no `completion_manifest:` key at all. | Warn+skip: append a structured supervisor comment noting the absence, then proceed as if all-true. Legacy tickets authored before EPIC-CompletionManifestSignoff are expected to be absent; new sign-offs should always include the block. |

#### Malformed-retry cap

The malformed-retry cap is **1 per manifest** (i.e. per agent invocation), not 1 per individual false item within the manifest. If the retry produces a second malformed manifest — even if only one item remains bare-`false` — the cap is exhausted and the supervisor falls through to §3.4 directly. This cap counts against the same per-phase retry budget as the §3.1 trivial-mechanical retry (the two share the cap, not each having their own separate 1-retry allowance).

#### Legacy compatibility

The manifest validation step is a **no-op for absent manifests** — it never blocks progress on legacy tickets. The requirement to include `completion_manifest:` applies only to sign-offs written after the epoch ticket (`01_signoff_skill_manifest_section.md`) is merged. See `signoff` §2b (Legacy Compatibility) for the canonical statement of this rule.

---

### §2.4 Sign-off invariants (delegate to `signoff` skill)

After every spawned agent returns, the ticket file MUST satisfy the validator rules in [`signoff` §5](../signoff/SKILL.md). If a parity violation is detected (frontmatter `agents` ≠ `## Sign-offs`), the ticket-supervisor halts immediately with a `failed` payload — it does not attempt to repair the ticket.

---

## §3 Failure Adjudication

When the latest comment status is `blocker`, the ticket-supervisor walks this four-case ladder. The cases are ordered by escalation severity; pick the **first** matching case.

### §3.1 Case 1 — Trivial mechanical failure

**Pattern**: the blocker comment names a single file + line + concrete fix (test failure pointing to one assertion, lint error, hook failure with autofix-class diagnostic, single missing import).

**Action**: respawn the **same** agent (the one that just produced the blocker) with the blocker comment body as additional input. **Cap**: 1 respawn per phase per ticket (§4).

Emit `agent_retry` before the respawn (non-blocking):
```bash
python .claude/skills/agent-telemetry/scripts/emit_event.py \
  --agent "ticket-supervisor" --event agent_retry \
  --ticket "<ticket_path>" --phase "<failing_agent>" \
  --retry-count 1 \
  --log debugging/logs/agent_telemetry.jsonl || true
```

### §3.2 Case 2 — Cross-agent rework

**Pattern**: the blocker comment is from a **review-class** agent (`pr-reviewer`, `architect-review`, `status-checker`) and explicitly names a sibling whose work needs revision (e.g. "respawn sql-coder with this finding").

**Action**: flip the named sibling from `signed_off` back to `needed` (the sibling self-resets via its own next sign-off cycle — supervisor does not directly mutate the sibling's row), then respawn the named sibling with the reviewer's comment as input. **Cap**: 1 respawn per phase pair per ticket (§4).

Emit `agent_respawn` before the sibling respawn (non-blocking):
```bash
python .claude/skills/agent-telemetry/scripts/emit_event.py \
  --agent "ticket-supervisor" --event agent_respawn \
  --ticket "<ticket_path>" --phase "<named_sibling>" \
  --retry-count 1 \
  --log debugging/logs/agent_telemetry.jsonl || true
```

### §3.3 Case 3 — Open-ended design choice

**Pattern**: the blocker comment describes an architectural ambiguity, multiple plausible approaches, or a question whose answer requires weighing trade-offs (e.g. "should this be a JSONB column or a separate table?", "should we cache here or in the consumer?").

**Action**: spawn `brainstorm-lead` with the blocker comment + the relevant ticket sections as input. `brainstorm-lead` runs 2–3 `brainstorm-worker`s in parallel and returns a synthesized recommendation. The ticket-supervisor then appends a `(status: question)` comment to the ticket containing the recommendation and surfaces it to the user via the §6 payload. **Cap**: 1 brainstorm-lead invocation per ticket (§4).

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
4. Return `{status: "blocked", payload: ...}` to `epic-supervisor`.

The epic-supervisor decides whether to halt the epic or continue with independent tickets (§1.3 + §6).

### §3.5 Case 5 — Confirmation-gate relay-approval deadlock (recurring)

**Pattern**: a confirmation-gated agent (`commit`, `pull-request`, finalize-feature
merge gate, `worktree-agent remove`) is dispatched, presents its gate, and then
**refuses approval relayed via SendMessage** from the parent — it insists on the user's
own message, which a subagent has no channel to receive. The agent loops at its gate.

This is a **recurring, confirmed pattern** (EPIC-PrecommitSafetyNet and
EPIC-AcPipelineDeployGaps). Re-sending "yes" via SendMessage will not resolve it.

**Interim protocol** (until an authorization-token solution ships):

1. Confirm the user has authorized the action in the parent conversation (e.g. via an
   `AskUserQuestion` answer or a direct message).
2. The parent then performs the gated action **directly** from the main loop — e.g. the
   `commit` agent's job is done by a direct (delegated) commit; the merge gate by
   `gh pr merge`; worktree removal by `git worktree remove`. (Note: a direct `git commit`
   is blocked by `enforce_commit_delegation`; satisfy it by dispatching a FRESH `commit`
   agent with the user's approval stated as a pre-authorization in the initial dispatch
   prompt — gated agents accept their *initial* task, only relayed *follow-ups* deadlock.)
3. Log the bypass in the parent transcript: `Bypassed <agent> gate directly —
   relay-approval deadlock; authorization granted by user in parent conversation.`
4. Do NOT re-attempt SendMessage with the approval — it will not succeed and wastes cycles.

**Permanent fix (pending)**: an authorization token, e.g.
`{ "authorization": { "granted_by": "user", "action": "commit", "ticket": "..." } }`,
that gated agents accept as sanctioned without an interactive user turn. See KI-2 from
the EPIC-PrecommitSafetyNet retrospective and `feedback_no_gated_agent_for_interactive.md`.

---

## §4 Retry Caps (numeric)

Every cap below is a hard ceiling enforced per-ticket. When exceeded, the supervisor MUST fall through to §3.4 (halt + escalate).

| Cap | Limit | Scope |
|---|---|---|
| **Coder respawn after own failure** (§3.1) | **1 per phase per ticket** | A second consecutive failure of the same coder agent on the same phase → fall through to §3.4. |
| **Sibling respawn from review** (§3.2) | **1 per phase pair per ticket** | A "phase pair" is the (reviewer, coder) tuple, e.g. (pr-reviewer, python-coder). After one round-trip, a second blocker from the same reviewer against the same coder → fall through to §3.4. |
| **test-failure rework** (BO-530-3-i) | **2 per ticket (configurable)** | When test-runner returns a blocker, the originating coder is re-dispatched for rework. After 2 rework attempts on the same ticket the loop is exhausted — fall through to §3.4. The default of 2 is configurable per-ticket via `test_failure_rework_cap:` in the ticket frontmatter; if absent, 2 applies. |
| **brainstorm-lead invocations** (§3.3) | **1 per ticket** | A ticket gets at most one brainstorm. A second design-class blocker on the same ticket → fall through to §3.4 directly (do not spawn brainstorm-lead again). |
| **Commit hook autofix loop** | inherited from `precommit-autofix` skill (1 retry) | Owned by the commit phase agent itself; supervisor does not retry commits. |
| **Conflict-resolver chain** | inherited from existing chain | Owned by the pull-request phase agent itself; supervisor does not retry. |

The supervisor maintains a small in-memory counter dictionary keyed by `(ticket_path, phase, cap_kind)`. The counter is per-supervisor-invocation; it is NOT persisted to the ticket file. If a supervisor crashes and is re-spawned mid-ticket, the counters reset — that is acceptable because the on-disk `agents` map and comment log already encode the relevant history, and a re-spawned supervisor reading a `failed` row will route to §3.4 on its own.

---

## §5 Commit-phase Serialization Lock

The commit and pull-request phases mutate the git index and `HEAD`; they cannot run concurrently across sibling tickets in the same worktree. We enforce mutual exclusion via a tiny lock file at the worktree root.

### §5.0 Supervised commit auto-authorization

When `ticket-supervisor` dispatches the `commit` agent with a `ticket_path`
argument, the commit agent's routine confirmation gate (Step 3 in the commit
template) is **auto-authorized** — no interactive "Commit this? (yes / edit /
cancel)" prompt is issued and no `question` status is emitted. Authorization
derives from the `/build-feature` dispatch itself plus the three upstream gates
that have already vetted the diff: pr-reviewer, ac-validator, and
ac-fulfillment-gate. The commit agent records an audit entry in the ticket's
`## Comments` section instead of halting for a reply.

**The `commit` agent MUST NOT emit `question` status for its routine
confirmation gate when invoked with a `ticket_path`.** A `question` status is
terminal-until-user-reply (§2.2 routing table), and no reply channel exists
during a mid-drive supervisor run — the ticket would deadlock permanently.

The interactive `/commit` confirmation gate (no `ticket_path`) is entirely
unaffected by this rule.

### §5.1 Lock file

- **Path**: `<worktree_root>/.epic-commit-lock`
- **Contents**: a single line, `<ticket_path> <pid> <ISO8601-timestamp>`, for human debugging only. The mere existence of the file is the lock.
- **Lifetime**: held only across the commit (or pull-request) phase of one ticket; deleted on success OR failure.

### §5.2 Acquire recipe (atomic-create)

The supervisor MUST use an atomic create-if-not-exists primitive.

**Important — Shell Convention**: Each Bash tool call must be a single simple
command. Do NOT chain with `&&`, `||`, `;`, or use subshells. The lock
acquisition requires a dedicated helper script that encapsulates the atomic
logic in one invocable command.

**Bash — single-command invocation**:
```bash
python3 scripts/epic_lock.py --acquire --ticket "$TICKET_PATH" --worktree "$WORKTREE_ROOT"
```
The script exits 0 and prints `acquired=1` on success, or exits 0 and prints
`acquired=0` if the lock already exists. On error it exits non-zero.

If `epic_lock.py` is not yet available, use this single-command form:
```bash
bash -c 'set -C; printf "%s %s %s\n" "'"$TICKET_PATH"'" "$$" "$(date -Iseconds)" > "'"$WORKTREE_ROOT"'/.epic-commit-lock"'
```
Check the exit code from the Bash tool result: exit 0 = acquired, non-zero = not acquired.

**Python (when supervisor is implemented in code, not bash)**:
```python
# O_CREAT | O_EXCL is atomic across all POSIX FSes.
fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
os.write(fd, f"{ticket_path} {os.getpid()} {datetime.now().isoformat()}\n".encode())
os.close(fd)
```

If acquisition fails, the supervisor MUST sleep briefly (exponential backoff starting at 250ms, capped at 8s) and retry. After 60 seconds total wait, fall through to §3.4 with blocker `commit-lock-stuck`.

### §5.3 Release recipe

Release is unconditional — both on success and on every failure path:

```bash
rm -f "$WORKTREE_ROOT/.epic-commit-lock"
```

Wrap the entire commit-phase invocation in a `trap`-style `finally` so the lock is released even if the supervisor itself crashes. The supervisor's child commit-agent does NOT touch the lock file directly; the supervisor owns the lock for its child's lifetime.

### §5.4 Recovery

If `/build-feature` is restarted and finds an existing `.epic-commit-lock` whose `<pid>` is not alive, it MUST log a warning and `rm -f` the stale lock before resuming. A live PID inside an unfamiliar lock means another supervisor instance is running — halt and surface to user (§3.4).

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

### §5.7 Interim Protocol: Gated-Agent Confirmation-Gate Deadlock

**Problem.** Gated agents — `commit`, `worktree-agent`, and `finalize-feature` — require direct
user authority to proceed past their confirmation gates (git commit, PR merge, worktree removal).
When any of these agents is dispatched as a subagent by a coordinator or supervisor, no direct
user-turn channel exists. A coordinator relaying "yes" via `SendMessage` is rejected ("coordinator
message carries no user authority"), and the agent dead-ends at its gate permanently. The ticket
is then blocked until a human intervenes.

This was observed during EPIC-PrecommitSafetyNet finalization: every attempt to relay a
confirmation through a coordinator subagent failed, forcing out-of-band resolution.

**Interim protocol (operational now).**

When a supervisor or coordinator dispatches a gated agent and the user has already granted
authority for the destructive action, pass the sanction in the **initial dispatch payload**
rather than relying on a later relayed reply. Use the established sanction markers:

| Gated agent | Sanction marker | Where to set it |
|---|---|---|
| `commit` | `COMMIT_AGENT_MODE=1` | Pass as an environment variable or an explicit field in the Agent-tool input when dispatching from `ticket-supervisor`. The commit auto-authorization (§5.0) already encodes this for ticket-supervisor. |
| Supervised phase agents (`finalize-feature`, `worktree-agent`) | `via: /build-feature` or equivalent authorized-dispatch marker | Pass in the prompt/input block of the Agent-tool call so the agent can confirm the caller chain is authorized. |

If a gated agent still dead-ends at its confirmation gate after the sanction marker is
present from the start, the coordinator has two options — in priority order:

1. **Re-dispatch with the sanction marker present from the first message.** Confirm that the
   marker was included (not added mid-conversation via `SendMessage`) and retry.

2. **Complete the destructive step directly** (raw `git` / `gh` at the coordinator's context)
   AND immediately record the bypass reason in a ticket comment or audit note using the
   standard `## Comments` heading schema from the `signoff` skill.

Never silently bypass a gate without logging why. The audit entry is mandatory.

**Proposed permanent fix direction (not yet implemented — forward-looking design note).**

Introduce a structured authorization token that the dispatcher passes in the dispatch payload,
which gated agents accept as user-sanctioned without requiring an interactive turn. The token
would generalize the existing `COMMIT_AGENT_MODE=1` pattern to all gated agents:

```yaml
authorization:
  granted_by: "/build-feature"   # the slash command or agent that holds user authority
  action: "commit"               # the specific destructive action being sanctioned
  ticket: "<ticket_path>"        # scope of the authorization
```

A gated agent receiving a valid `authorization:` block in its dispatch payload would skip the
interactive confirmation gate and record the token in its sign-off comment instead. Until this
token is implemented in the agent templates for `commit`, `worktree-agent`, and
`finalize-feature`, the interim protocol above applies.

### §5.8 --no-verify Override Policy (BO-1700b-3)

`git commit --no-verify` is a **last-resort emergency override only**. It is NOT a
routine escape hatch for fixing hook failures.

**Trade-off**: `--no-verify` skips ALL pre-commit hooks simultaneously. This disables
the WorktreeQualityGateGuard canary, feedback-id checks, doc compliance hooks, and every
other quality gate in one command. Commits that bypass hooks may contain:
- Missing feedback-id entries (breaking retrospective tooling)
- Un-validated test contracts (allowing regression)
- Security suppressions bypassed

**Recommended resolution path** (in priority order):
1. Fix the hook failure (preferred — hooks exist to catch real problems).
2. Suppress the specific hook for this commit: `SKIP=<hook-id> git commit`.
3. Use `--no-verify` ONLY when: hook infrastructure itself is broken (not the code
   being committed), AND the commit is strictly chore/emergency, AND the bypass is
   documented in the commit message with `[NO-HOOKS-OVERRIDE: <reason>]`.

**The `commit` agent enforces this policy** — it refuses `--no-verify` absent explicit
user authorization in the current conversation (relayed approval does not count).

---

## §6 User Escalation Contract

When a ticket halts (Case §3.4 fall-through, or `question`-class comment from §2.2), the ticket-supervisor returns this exact payload to its caller (`/build-feature`), which in turn relays it to the user.

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

> **`/build-feature` MAY continue processing other tickets in the current batch (and subsequent batches) while a blocked ticket waits for user input**, provided the remaining tickets do not depend on the blocked one (transitively, via either `depends_on` or `files_touched`).

Equivalent phrasing: a single ticket's user-escalation does NOT halt the epic by default. The epic only halts when the §1.3 conditions are met (structural blocker, dependency-cycle invariant violation, or unrecoverable lock state).

When the user replies and resolves the blocker, the supervisor flow is:

1. User edits the blocked ticket directly (e.g. flips a `failed` row to `needed`, or appends an answering comment with the chosen approach).
2. User resumes via `/build-feature <epic>` (or however the harness is wired).
3. `/build-feature` re-reads `Master_Plan.md`, rebuilds the dependency graph, and re-enters its main loop at §1 step 3 — the resolved ticket is once again `ready`.

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
supervisor's main loop; §7.2 fires **after** the loop reports "epic complete"
and the supervisor is about to move the epic folder into `99_done/`. Both
emerged from the EPIC-WorkflowArchitect retrospective.

### §7.1 Master_Plan portability pre-flight

Before declaring a hook, agent, or skill "portable" in a `Master_Plan.md`, the
**epic author** (not the supervisor) MUST verify zero project-domain imports.
For each candidate file, grep its top-level imports and cross-check against the
project-specific module list in `package_boundary.json`:

```bash
grep -E "^from |^import " <candidate_file> | grep -E "alembic|sql_|database_manager|live_trader|collector"
```

If the grep returns anything, the file is project-specific by ADR-020 and must
not be classified as portable. Discovering a misclassification mid-drive — as
happened with `post_checkout_drift_check.py` during EPIC-WorkflowArchitect —
forces a Master_Plan count correction and wastes coder time. This check is
fast (seconds per file) and catches the failure class at the cheapest point.

`/build-feature` does NOT re-run this check at dispatch time; it trusts the
Master_Plan. The discipline is upstream of the dispatch loop.

### §7.2 Epic archival gate (supervisor)

When the main loop reports "epic complete", the supervisor MUST iterate over every
sub-ticket file in the epic (scanning recursively via frontmatter `status:`, not
by checking folder position — BO-400a-3) and verify:

1. Frontmatter `status: done` (not `todo` or `in_progress`).
2. Every entry in `agents:` map is `signed_off` or `not_needed` (not `needed` or `failed`).
3. Every line in the `## Sign-offs` checklist is `- [x] ...` (not `- [ ]`).

The scan MUST cover ALL `.md` files recursively in the epic folder, including any
legacy `done/` subfolder that may exist from prior convention. Use the ticket's
frontmatter `status:` field as the authoritative signal — not the file's folder
position (BO-400c-2).

If any sub-ticket fails one or more of these checks, the supervisor MUST:

- **Defer** the failing ticket(s) by updating its frontmatter `status:` to `blocked`
  via `set_ticket_status.py --status blocked --force`, and noting the deferral in
  a `## Comments` entry. Do NOT move the file via `git mv`.
- **Update** `Master_Plan.md` to mark the deferred ticket(s) as
  *"deferred — status: blocked"* with a link, so the audit trail is intact.
- **Then** proceed with archival of the remaining (genuinely complete) epic.

Bulk-moving an entire epic folder to `99_done/` without per-ticket validation —
as happened with EPIC-WorkflowArchitect's T11 — hides outstanding scope and
silently breaks `check-ticket-signoff-parity` on every subsequent commit
touching the archived ticket. The cost of the validation is a few file reads;
the cost of missing it is days of confusion later.

**Stage all status-transition edits before the archival commit.** After
`set_ticket_status.py` updates a ticket's frontmatter, any subsequent edits
to the file (sign-offs, comment-append) MUST be followed by an explicit
`git add <ticket-path>` before committing. The `check-ticket-signoff-parity`
guard reads the **staged** content, not the working-tree content.

**Note (BO-400c-1):** Ticket files are NEVER moved via `git mv` to a `done/`
subfolder. The `set_ticket_status.py` script updates the frontmatter in place
and the file remains at its original path. The parity guard will block any
`git mv` into a `done/` subfolder (BO-400c-3).

---

## §9 Integration Quality Gates

The following two rules govern quality gates that must be applied at the **epic design phase** — before tickets are authored — and enforced at the final ticket in any multi-ticket chain. Both emerged from EPIC-ComputedQualityGates (PR #201, 2026-07-07), where 41 tests were green and all phases were signed off while the feature was entirely inactive on real inputs.

### Cross-Ticket Integration Gate (anti-phantom-done)

When an epic delivers a feature across multiple tickets each implementing one layer of the same system (function body in ticket A, config data in ticket B, call-site wiring in ticket C), the **final ticket in the chain must include a real-store end-to-end test** that:

1. Exercises the **REAL call path** through the feature (not an isolated unit function call).
2. Reads **REAL data** from the on-disk store (not hard-coded synthetic values).
3. Asserts the **observable OUTPUT** (file written, frontmatter emitted, API response) contains the expected computed result.

This gate is **mandatory** when `files_touched` across two or more tickets in the epic share a Python module. A per-ticket unit test targeting the module's internal function directly does NOT satisfy this requirement.

**Reference failure:** EPIC-ComputedQualityGates (PR #201, 2026-07-01) — 41 tests green, all phases signed off, feature entirely inactive on real inputs; caught only by a post-drive `--dry-run` behavioral spot-check.

### Cross-Component Vocabulary Contract Test

When two or more independently maintained components must share the same enum vocabulary (e.g., a guard hook, a YAML config, and a JSON schema all enumerate the same `change_target` values), author a **vocabulary-contract test** when the **first component is written**. The test must:

1. Assert the key/value sets are **set-equal** (`set(A) == set(B)`, not subset) across all sources.
2. Live in a **permanent CI-run test file** (not a one-off migration script).
3. Be part of the standard test suite and remain green permanently.

Without this test, independent edits to each component will silently diverge to disjoint vocabularies. Pattern: `test_ac3_change_target_enum_identical_across_sources` in `unit_tests/commit_guardian/test_check_ac_schema.py`.

(Source: EPIC-ComputedQualityGates, 2026-07-07.)

---

## §8 References

- [`signoff` skill](../signoff/SKILL.md) — canonical status enum (`not_needed | needed | signed_off | failed`), atomic sign-off Edit recipe (`§2`), comment-append recipe with parser-strict heading schema (`§3`), failed-path protocol (`§4`), validator rules enforced by the parity guard (`§5`). **All status mutation lives there; this skill never duplicates it.**
- [`ticket-authoring` skill](../ticket-authoring/SKILL.md) — ticket frontmatter schema, body section order, `files_touched` and `agents` field semantics.
- [Spec: Agent Supervisor & Ticket Sign-off Design](../../../docs/superpowers/specs/2026-05-08-agent-supervisor-design.md) — full design rationale; this skill is the operational distillation of §6 (control flow), §7 (parallelism), §8 (failure handling).
