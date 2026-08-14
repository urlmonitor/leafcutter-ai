---
title: 'Agent Reference: epic-supervisor'
type: reference
status: active
created: 2026-05-08
last_updated: 2026-05-12
components:
- infrastructure
related_docs:
- docs/agents/conventions.md
- docs/architecture/adrs/ADR-033-agent-model-tiers.md
- docs/superpowers/specs/2026-05-08-agent-supervisor-design.md
- tickets/09_done/EPIC-AgentSupervisor/Master_Plan.md
related_code:
- .claude/agents/epic-supervisor.md
- .claude/agents/ticket-supervisor.md
- .claude/skills/building-epics/SKILL.md
- .claude/skills/signoff/SKILL.md
- .claude/commands/epic-supervisor.md
description: 'Overview of Agent Reference: epic-supervisor.'
---
# Agent Reference: `epic-supervisor`

Implementing agent: `epic-supervisor` (Sonnet, user-facing).
Family: `coding/`.

Drives a whole epic to completion ticket-by-ticket, respecting both
logical (`depends_on`) and physical (`files_touched`) dependencies, with
parallel dispatch where safe. Halts only on structural blockers.

User-facing entry today: `.claude/commands/epic-supervisor.md` (internal
slash-command surface). The user-facing `/build-feature` command is built
by ticket 09 of [EPIC-AgentSupervisor].

---

## 1. Purpose

`epic-supervisor` is the outer driver of the supervisory layer. Where a
single `ticket-supervisor` knows how to walk **one ticket** through its
phase agents, `epic-supervisor` knows how to walk **a whole epic**: it
reads `Master_Plan.md`, builds a dependency graph, schedules tickets in
parallel batches, surfaces blockers, and stops only when the epic is
done or a structural blocker forces a halt.

It implements the design in [spec §6.1] by following
[`building-epics` §1] — the agent file does not contain the algorithm,
only the orchestration scaffolding around it.

---

## 2. Inputs

```
epic_path:  <absolute or repo-relative path to the epic folder>
# or, equivalently:
epic_name:  <name of the epic — resolves to tickets/01_todo/EPIC-<Name>/
             or tickets/00_inbox/epics/EPIC-<Name>/, in that order>
```

Resolution rule when only `epic_name` is supplied: search `01_todo/` first
(active work), then `00_inbox/epics/` (proposed). If the resolved folder
is missing or contains no `Master_Plan.md`, surface an error to the user
and exit. The agent does **not** scaffold epics; that is `create-epic`.

---

## 3. Behaviour

The six-step loop (per `building-epics` §1.1):

1. **Read** `Master_Plan.md` and every ticket in the epic folder
   (sub-tickets at root plus the `done/` subfolder).
2. **Build** the dependency graph G:
   - Logical edges from `depends_on` (transitively closed).
   - Physical edges from `files_touched` intersection.
   - Both edge sets are undirected for the parallelism gate;
     `depends_on` is also retained directed for ordering.
3. **Compute** the next ready batch — a maximal antichain of tickets
   with all `depends_on` predecessors `done` AND pairwise-disjoint
   `files_touched` AND no transitive `depends_on` relation. Tie-break by
   ascending NN execution-order prefix.
4. **Dispatch** one `ticket-supervisor` per ticket in the batch — all in
   a single message via parallel `Agent` tool calls. Each child receives
   `{ticket_path: <absolute path>}`.
5. **Wait** for the entire batch to complete (barrier).
6. **Halt-or-loop**: apply the §1.3 halt conditions (see §5 below);
   otherwise GOTO 3.

---

## 4. Outputs

### 4.1 Clean completion

```
## Epic Complete: EPIC-<Name>

All N tickets are signed off. Epic ready to merge.

Tickets:
- 01_<slug>.md — done
- 02_<slug>.md — done
...
```

The supervisor does NOT open the PR itself; the `pull-request` phase of
the final ticket is responsible for that.

### 4.2 Pause with per-ticket blockers

When one or more tickets are blocked but the epic continues with
independent siblings:

```
## Epic Paused: EPIC-<Name>

M tickets done; K blocked awaiting user input.

Done:    [ ... ]
Blocked: [ <ticket — phase — blocker_summary — suggested_remediation> ... ]
Skipped: [ <ticket — depends on blocked sibling> ... ]
```

### 4.3 Structural halt

```
## Epic Halted: EPIC-<Name>

Halt reason: <explanation>
First blocking ticket: <path>
Suggested remediation: <text>
```

---

## 5. Halt conditions

The epic halts the entire run only when (per `building-epics` §1.3):

| Condition | Reason |
|---|---|
| Structural blocker | A child returns `blocked` with a remediation that requires resolving an ambiguity affecting multiple tickets, or a phase agent on the critical path of every remaining ticket has returned `failed`. |
| Cycle in graph | The `depends_on` ∪ `files_touched` graph contains a cycle that survives the parallelism projection (refinement should prevent this; treat as invariant violation). |
| Unrecoverable lock | The commit-phase lock cannot be released after a child crash (see `building-epics` §5.4). |

A single ticket's user-escalation does NOT halt the epic by default. The
epic continues with independent siblings.

---

## 6. Parallelism model

- **Single epic worktree** (existing project convention).
- **File-touch gate** at batch-formation time guarantees parallel-safe
  scheduling under the disjoint-`files_touched` invariant.
- **Commit-phase lock** at `<worktree_root>/.epic-commit-lock` enforces
  mutual exclusion on `commit` and `pull-request` phases across siblings.
  The lock is held by each `ticket-supervisor`; `epic-supervisor` itself
  does NOT acquire or release it. The recipe (atomic `set -C` create,
  unconditional `rm -f` release) lives in [`building-epics` §5] and is
  not duplicated in either agent file.
- **One PR per epic** (existing convention). PR opens after every ticket
  is `done`.
- **Nesting depth**: `epic-supervisor` (1) → `ticket-supervisor` (2) →
  phase-agent (3). The supervisor never spawns below depth 2.

---

## 7. Escalation behaviour

When a `ticket-supervisor` returns `{status: "blocked", payload}`:

| Payload classification | Action |
|---|---|
| Local to one ticket (other tickets remain independent under graph) | Mark ticket blocked; exclude from `ready`; continue with the rest of the epic. |
| Structural (multi-ticket impact) | Halt the epic; surface every pending payload to the user. |

The payload schema (per [`building-epics` §6.1]):

```
{
  "ticket_path":           "<absolute path>",
  "phase":                 "<agent name as in agents: map>",
  "blocker_summary":       "<one sentence ≤120 chars>",
  "suggested_remediation": "<plain-English description>"
}
```

When the user replies and resolves a blocker (typically by editing the
ticket file), the user re-invokes `/build-feature <epic>` and
`epic-supervisor` re-enters at step 3 with the updated graph.

---

## 7b. Pre-Flight Reads — Gotchas

### Grandfathered sign-offs look identical to real sign-offs in the agents: map

`scripts/grandfather_ticket_agents.py` (EPIC-AgentSupervisor ticket 11) bulk-
stamped every legacy ticket's phase agents as `signed_off` before any code
shipped. Tickets 02, 03, and 04 of EPIC-MarketStructure were all marked
`signed_off` before the epic started — the supervisor correctly halted, but
only because the user noticed, not because tooling flagged it.

**After TICKET-20260511:** `grandfather_ticket_agents.py` now emits a
nested-map shape:

```yaml
agents:
  architect-review:
    status: signed_off
    grandfathered: true
```

The parity guard (`check_ticket_signoff_parity.py`) and the frontmatter hook
(`ticket_frontmatter_guard.py`) both accept this shape. When you read a ticket
and see `grandfathered: true`, treat the agent's work as **not yet reviewed by
the supervisor system** — do not assume the phase was actually executed.

---

## 7c. Master_Plan Completeness Checklist

Before invoking `/build-feature`, verify `Master_Plan.md` contains a
`## Key Design Decisions` section (or any `##`-level heading containing
"Design Decision" or "Key Decision"). The epic-supervisor Pre-Flight step 5
will halt if this section is absent.

Use these two templates as a starting point:

### Template A — New-column epics

```markdown
## Key Design Decisions

| Decision | Chosen option | Status |
|---|---|---|
| Storage location (which table / hypertable) | `<table>` | RESOLVED |
| Nullable vs non-null default | `<null / 0.0 / false>` | RESOLVED |
| Indexing strategy (BRIN, B-tree, none) | `<strategy>` | RESOLVED |
| HTF intervals supported | `<e.g. 15m, 1h, 4h, D>` | RESOLVED |
```

### Template B — New-procedure epics

```markdown
## Key Design Decisions

| Decision | Chosen option | Status |
|---|---|---|
| Trigger mechanism (event, schedule, on-demand) | `<choice>` | RESOLVED |
| Idempotency strategy (IF NOT EXISTS, ON CONFLICT, WHERE clause) | `<choice>` | RESOLVED |
| Error handling (RAISE, skip-and-log, abort) | `<choice>` | RESOLVED |
| Rollback approach (transaction, compensating DML) | `<choice>` | RESOLVED |
```

Leave the `Status` column as `OPEN` for any decision not yet made. The
per-ticket gate (Pre-Flight step 5 Level 2) will surface tickets whose
`## Architecture` or `## Context` sections still contain `TODO`, `TBD`,
or headings ending with `?`.

---

## 8. Edge cases

| Case | Behaviour |
|---|---|
| Epic folder does not exist | Error; exit. Do not scaffold. |
| Epic folder has no `Master_Plan.md` | Error; exit. |
| Ticket has empty / missing `files_touched` | Treat as conflicting with every other ticket; run serially (default-conservative). |
| Ticket has empty `agents:` map | `ticket-supervisor` returns `done` immediately; no work. |
| Cycle in `depends_on` ∪ `files_touched` | Halt with invariant-violation message; refinement should have prevented this. |
| Stale lock file from a crashed sibling | `epic-supervisor` may log a warning and `rm -f` the stale lock if its `<pid>` is not alive (see `building-epics` §5.4); a live PID inside an unfamiliar lock means another supervisor is running — halt and surface to user. |

---

## 9. Cross-Links

- [`.claude/agents/epic-supervisor.md`](../../../.claude/agents/epic-supervisor.md) —
  the agent file itself (frontmatter + system prompt).
- [`.claude/agents/ticket-supervisor.md`](../../../.claude/agents/ticket-supervisor.md) —
  the inner driver this agent dispatches.
- [`.claude/skills/building-epics/SKILL.md`](../../../.claude/skills/building-epics/SKILL.md) —
  primary runbook (§1 epic loop, §1.3 halt conditions, §5 commit lock,
  §6 escalation contract).
- [`.claude/skills/signoff/SKILL.md`](../../../.claude/skills/signoff/SKILL.md) —
  status enum and validator rules consumed when reading ticket state.
- [`.claude/commands/epic-supervisor.md`](../../../.claude/commands/epic-supervisor.md) —
  internal slash-command surface (the user-facing `/build-feature`
  arrives in ticket 09).
- [Spec §6 Control Flow](../../../docs/superpowers/specs/2026-05-08-agent-supervisor-design.md) —
  authoritative design.
- [Ticket 08](../../../tickets/09_done/EPIC-AgentSupervisor/done/08_supervisor_agents.md) —
  the ticket that shipped this agent.

[EPIC-AgentSupervisor]: ../../../tickets/09_done/EPIC-AgentSupervisor/Master_Plan.md
[spec §6.1]: ../../../docs/superpowers/specs/2026-05-08-agent-supervisor-design.md
[`building-epics` §1]: ../../../.claude/skills/building-epics/SKILL.md
[`building-epics` §5]: ../../../.claude/skills/building-epics/SKILL.md
[`building-epics` §6.1]: ../../../.claude/skills/building-epics/SKILL.md
