---
title: "Wire supervisor feedback emission system — implement emit_event.py and imperative emit calls"
status: todo
components:
  - build_pipeline
created: 2026-05-28
depends_on: []
priority: medium
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - leafcutter-ai/templates/skills/agent-telemetry/scripts/emit_event.py
  - leafcutter-ai/templates/agents/epic-supervisor.md
  - leafcutter-ai/templates/agents/ticket-supervisor.md
  - leafcutter-ai/templates/skills/building-epics/SKILL.md
agents:
  architect-review: not_needed
  test-writer: needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
ac_traceability:
  L0: INF-400
  L1: INF-400g
  l2:
    - INF-400g-1
    - INF-400g-2
    - INF-400g-3
    - INF-400g-4
    - INF-400g-5
    - INF-400g-6
    - INF-400g-7
    - INF-400g-8
    - INF-400g-9
  l3:
    - INF-400g-2-i
    - INF-400g-2-ii
  ac_path: docs/acceptance-criteria/infrastructure/INF-400-agent-learning/INF-400g.yaml
  routing: direct_to_ba
---

# Wire supervisor feedback emission system — implement emit_event.py and imperative emit calls

## Actor / Goal

In order to have observable drive telemetry that feeds the retrospective-agent's
`subagent-quality` analysis, we need to create `emit_event.py` and convert the
feedback emission blocks in the supervisor templates from example code (documentation)
to imperative Bash instructions so that agents execute them.

## Context

The supervisor feedback system is architecturally complete: the `subagent-quality`
category exists in `config/feedback_categories.yaml`, the retrospective-agent reads
it via `aggregate.py --category subagent-quality`, and the `building-epics/SKILL.md`
runbook already contains `emit_event.py` call sites at nine locations (§1.1
`supervisor_dispatch`, `epic_halted`, `epic_complete`; §2.1 `agent_start`,
`agent_signoff`; §3.1 `agent_retry`; §3.2 `agent_respawn`; §3.4 `agent_failure`).

Two gaps prevent the system from functioning:

1. **`emit_event.py` does not exist.** The SKILL.md calls
   `python .claude/skills/agent-telemetry/scripts/emit_event.py` but the script has
   never been created. Every `|| true` suffix means failures are silently swallowed,
   making it undetectable during drives today.

2. **The supervisor agent templates treat emission as example code, not instructions.**
   The feedback emission blocks in `epic-supervisor.md` (CFCS algorithm between steps
   5-6) and `ticket-supervisor.md` (all four adjudication emit points: §3.1, §3.2,
   §3.3, §3.4) are written as Python code blocks with inline comments — they look like
   documentation of what an agent might do, not imperative Bash commands an agent MUST
   run. As a result, agents reading the templates skip the emission entirely.

### Deployment path note

The build system (`build_phases.py` `build_skills()`) deploys
`templates/skills/<skill-name>/*` verbatim to `.claude/skills/<skill-name>/`. Therefore
the correct source location for `emit_event.py` is:

```
leafcutter-ai/templates/skills/agent-telemetry/scripts/emit_event.py
```

This deploys to the path already referenced throughout `building-epics/SKILL.md`:

```
.claude/skills/agent-telemetry/scripts/emit_event.py
```

No changes to `building-epics/SKILL.md` §1.1 or §2.1 call sites are required —
the script path is already correct in the SKILL.md. The task is to CREATE the script
at the right source location so the build can deploy it.

### Why not `scripts/telemetry/`?

The `scripts/` directory in the source repo is for Python scripts deployed to
`<target>/scripts/` (commit guardian, doc compliance, feedback). The `emit_event.py`
script is a skill auxiliary, not a standalone project script — it belongs in the
`agent-telemetry` skill folder where the build system will co-locate it with any
future `SKILL.md` for that skill.

### Relationship to `submit_feedback.py`

`emit_event.py` writes raw telemetry events to `debugging/logs/agent_telemetry.jsonl`
(structured event records for operational observability). `submit_feedback.py` writes
feedback entries to `debugging/logs/feedback.jsonl` (categorized, validated
CFCS feedback). These are two separate sinks:

- **`agent_telemetry.jsonl`** — low-level event log (every agent start/stop/retry);
  consumed by the retrospective-agent to compute timing and failure rates.
- **`feedback.jsonl`** — high-level categorized observations; consumed by
  `aggregate.py --category subagent-quality` for retrospective summaries.

The supervisor templates call BOTH:
- `emit_event.py` for telemetry (SKILL.md call sites)
- `submit_feedback.py` for CFCS feedback (supervisor template adjudication blocks)

This ticket focuses on `emit_event.py` creation and making the `submit_feedback.py`
calls in the templates imperative.

## Acceptance Criteria

```gherkin
Given the build system has deployed the leafcutter package
When the deploy target is inspected
Then .claude/skills/agent-telemetry/scripts/emit_event.py exists and is executable

Given emit_event.py is invoked with valid arguments
When called as:
  python emit_event.py --agent "ticket-supervisor" --event agent_start
    --ticket "/path/to/01_schema.md" --phase "python-coder"
    --log debugging/logs/agent_telemetry.jsonl
Then it exits 0 and appends exactly one JSON line to the log file containing
  event_type, timestamp, ticket_path, agent_name, and payload fields

Given emit_event.py is invoked with --log pointing to a missing directory
When the directory does not exist
Then emit_event.py creates it (mkdir -p semantics) and exits 0

Given epic-supervisor reaches the end of a batch (between steps 5 and 6)
When the cross-ticket pattern detection algorithm runs
Then the Bash block calling submit_feedback.py is an imperative instruction
  (not a Python/prose example block) and the agent executes it

Given ticket-supervisor adjudicates a mechanical retry (§3.1)
When it classifies the blocker as a single-file concrete fix
Then it executes the submit_feedback.py call with category subagent-quality
  before respawning the failing agent

Given ticket-supervisor adjudicates a cross-agent rework (§3.2)
When a review-class agent names a sibling that needs revision
Then it executes the submit_feedback.py call with category subagent-quality

Given ticket-supervisor adjudicates a brainstorm escalation (§3.3)
When the blocker is an architectural ambiguity
Then it executes the submit_feedback.py call with category subagent-quality

Given ticket-supervisor exhausts the adjudication ladder (§3.4)
When no lower-tier case matches or the retry cap is exhausted
Then it executes the submit_feedback.py call with category subagent-quality
  and includes the resulting feedback_id in the blocked payload

Given an epic drive completes (or is halted)
When aggregate.py is run as: python scripts/feedback/aggregate.py
  --category subagent-quality
Then the output is non-empty (at least one entry exists from the drive)
```

## Sign-offs

- [ ] test-writer
- [ ] python-coder
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

### python-coder — create emit_event.py

- [ ] Create `leafcutter-ai/templates/skills/agent-telemetry/scripts/emit_event.py`
  with the following specification:
  - **CLI interface:**
    ```
    python emit_event.py \
      --agent   <agent-name>          # e.g. "epic-supervisor"
      --event   <event-type>          # e.g. "supervisor_dispatch"
      --ticket  <ticket-path>         # absolute or relative path to ticket file (optional)
      --phase   <phase-agent-name>    # e.g. "python-coder" (optional)
      --outcome <ok|blocked|failed>   # (optional)
      --retry-count <N>               # integer (optional)
      --log     <jsonl-path>          # output path; default: debugging/logs/agent_telemetry.jsonl
    ```
  - **Output format** (one JSON line appended to `--log`):
    ```json
    {
      "event_type": "<event-arg>",
      "timestamp":  "<ISO8601-UTC>",
      "agent_name": "<agent-arg>",
      "ticket_path": "<ticket-arg or null>",
      "payload": {
        "phase":       "<phase-arg or null>",
        "outcome":     "<outcome-arg or null>",
        "retry_count": <N or null>
      }
    }
    ```
  - **Directory creation:** call `log_path.parent.mkdir(parents=True, exist_ok=True)` before opening the file — never fail due to a missing `debugging/logs/` directory.
  - **Exit codes:** 0 on success; 1 on argument parse error. Do NOT raise on file-write failure — print a warning to stderr and exit 0 (the `|| true` callers rely on this being non-fatal).
  - **No external dependencies** beyond the Python stdlib. Do NOT import PyYAML, pyyaml, or any third-party library.
  - **DECISION HISTORY block** at the bottom following the project convention.

- [ ] Create `leafcutter-ai/templates/skills/agent-telemetry/SKILL.md` as a minimal stub
  so the `build_skills()` function treats `agent-telemetry` as a known skill folder:
  ```yaml
  ---
  name: agent-telemetry
  description: >
    Telemetry emission helpers for the supervisory layer. Contains emit_event.py,
    which writes structured event records to debugging/logs/agent_telemetry.jsonl.
  allowed-tools: Bash
  internal: true
  ---
  # agent-telemetry
  Internal skill — provides emit_event.py for supervisory telemetry emission.
  Loaded implicitly by building-epics via the emit_event.py call sites in §1.1 and §2.1.
  ```

### python-coder — rewrite template emit blocks

- [ ] Edit `leafcutter-ai/templates/agents/epic-supervisor.md` §"Cross-ticket pattern detection":
  - The current Python pseudocode block (starting `# Group blocked payloads by...`) is
    documentation. The Bash call within it (the commented-out `FB_ID=$(python ...`) is
    never executed because it is inside a Python comment.
  - Rewrite the section so the emit instruction is an explicit, uncommented Bash block
    that the agent MUST execute after detecting a pattern (N >= 2), NOT inside a Python
    code fence or a comment. Pattern:
    ```
    After detecting a cross-ticket pattern (N >= 2 tickets with matching key), execute
    the following Bash call (non-blocking — prefix with `FB_ID=$(...)` and handle
    non-zero exit as `(submit-failed)`):

    ```bash
    FB_ID=$(python scripts/feedback/submit_feedback.py \
      --ticket "<any_affected_ticket_path>" --phase epic-supervisor \
      --category subagent-quality \
      --tags "agent-<phase>,cross-ticket-pattern,n-<count>" \
      --note "Cross-ticket pattern: <phase> failed with '<summary_prefix>' on <count> tickets." \
      --jsonl debugging/logs/feedback.jsonl 2>/dev/null) || FB_ID="(submit-failed)"
    ```
    ```
  - Keep the algorithm pseudocode (the `groups = defaultdict(list)` section) as an
    explanatory block but make the Bash emit call a separate, imperative instruction.

- [ ] Edit `leafcutter-ai/templates/agents/ticket-supervisor.md` §"Failure adjudication"
  for all four cases (§3.1, §3.2, §3.3, §3.4):
  - In each case, the `FB_ID=$(python scripts/feedback/submit_feedback.py ...)` block
    is already written as Bash but is inside a description paragraph. Verify that the
    framing prose uses imperative language ("execute", "run", "call") not conditional
    or hypothetical language ("could emit", "you might call", "as an example").
  - For any block that reads as optional/descriptive rather than imperative, rewrite
    the surrounding prose to make it a mandatory execution step: "After determining
    this is a §3.N case, EXECUTE the following Bash call (non-blocking):"
  - The CFCS emit contract paragraph at the end of the adjudication section must
    remain — it clarifies that failures are non-blocking.

### test-writer

- [ ] Write unit tests for `emit_event.py` in
  `leafcutter-ai/unit_tests/test_emit_event.py` covering:
  - Happy path: valid args produce a valid JSON line in the output file.
  - Directory creation: `--log` pointing to a non-existent directory succeeds.
  - Optional args: missing `--ticket`, `--phase`, `--outcome`, `--retry-count`
    produce `null` in the payload, not a crash.
  - Invalid event type: still exits 0 (no validation — telemetry is permissive).
  - File is appended, not overwritten, on a second call.

## Risk & Safety

- Touches money? No.
- Touches data? Only log files (`debugging/logs/agent_telemetry.jsonl`,
  `debugging/logs/feedback.jsonl`). These are append-only observation logs;
  no production data or schema is modified.
- Reversibility? Fully reversible. `emit_event.py` is a new file; the template
  edits are prose rewrites. Dropping the ticket reverts to the current (silent)
  state. No migration needed.
- Shared contract? `building-epics/SKILL.md` is loaded by both `epic-supervisor`
  and `ticket-supervisor` on every invocation. The SKILL.md call sites already
  use `|| true` so a missing `emit_event.py` is non-fatal — the template edits
  are additive and do not break existing flows.
- Build dependency: `leafcutter-ai/templates/skills/agent-telemetry/` is a new
  skill folder. Verify that `build_skills()` in `build_phases.py` picks it up
  without changes (it iterates `skills_template_dir.iterdir()` — any new subfolder
  is automatically included). Run `build-self.sh` locally to confirm.
