---
title: 'Agent Reference: ticket-supervisor'
type: reference
status: active
created: 2026-05-08
last_updated: 2026-05-08
components:
- infrastructure
related_docs:
- docs/agents/conventions.md
- docs/architecture/adrs/ADR-033-agent-model-tiers.md
- docs/superpowers/specs/2026-05-08-agent-supervisor-design.md
- tickets/09_done/EPIC-AgentSupervisor/Master_Plan.md
related_code:
- .claude/agents/ticket-supervisor.md
- .claude/agents/epic-supervisor.md
- .claude/skills/building-epics/SKILL.md
- .claude/skills/signoff/SKILL.md
description: 'Overview of Agent Reference: ticket-supervisor.'
---
# Agent Reference: `ticket-supervisor`

Implementing agent: `ticket-supervisor` (Sonnet, internal).
Family: `coding/`.

Drives a single ticket from its current `needed` agents to fully signed
off. Reads frontmatter `agents:` map, spawns the next `needed` agent in
natural order, parses the `## Comments` status tag, routes on
ok / handoff / blocker / question, and runs the failure-adjudication
ladder on blockers. Never invoked by the user — `epic-supervisor` is the
only legitimate caller.

---

## 1. Purpose

`ticket-supervisor` is the inner driver of the supervisory layer. Its job
is the five-step loop from [spec §6.2] applied to a single ticket:
read → spawn → parse → route → loop. It implements that loop by
following [`building-epics` §2]; the agent file does not contain the
algorithm, only the orchestration scaffolding around it.

Phase agents (`python-coder`, `pr-reviewer`, `commit`, …) own their own
ticket-state writes via the `signoff` skill. The `ticket-supervisor` only
**reads** that state to decide the next move, plus the terminal
`status: todo` → `status: done` flip and `git mv` to `done/` when every
agent has signed off.

---

## 2. Inputs

```
ticket_path:    <absolute or repo-relative path to the ticket markdown file>
context:        <optional payload from epic-supervisor — e.g. carrying-over
                 retry counters from an earlier interrupted run>
```

Resolve `ticket_path` to absolute before any Read or Edit. Missing path →
return `{status: "failed", payload: {... blocker_summary: "ticket-not-found" ...}}`.

---

## 3. Phase ordering

Per [`building-epics` §2.1] step 1:

1. Compute `pending = [name for name, status in agents if status == "needed"]`.
2. Pick the **first** entry in `pending` by **declaration order in the YAML**.
3. Ties (none expected, since YAML maps preserve insertion order) broken
   by the canonical phase ordering:
   `architect-review → coder → test-runner → pr-reviewer → commit →
    pull-request → status-checker → documentation-expert`.

Two routing overrides apply:

| Override | Effect |
|---|---|
| Comment status `handoff` with named recipient | The named sibling is the next pick, regardless of natural order. |
| Failure adjudication respawn (§3.1, §3.2) | The chosen respawn target is the next pick. |

---

## 4. Behaviour (the five-step loop)

Per [`building-epics` §2.1]:

1. **Read** frontmatter `agents:` map. If `pending` is empty, mark the
   ticket done and return `{status: "done"}`.
2. **Spawn** the chosen agent via the `Agent` tool with input
   `{ticket_path: <absolute path>}`. The agent invokes `signoff` as its
   final action.
3. **Re-read** the ticket. Locate the LAST `## Comments` heading per the
   parser-strict regex in [`signoff` §5.4].
4. **Route** on the comment status tag (table below).
5. **Loop** to step 1 unless routing produced a terminal outcome
   (done | halted-for-user | escalated-to-brainstorm-lead).

### 4.1 Routing table

| Comment status | Action | Loop control |
|---|---|---|
| `ok`       | No-op (the agent already self-marked `signed_off`). | Continue. |
| `handoff`  | Identify named recipient sibling; flip its status to `needed` if not already; override natural order. | Continue. |
| `blocker`  | Run failure adjudication (§5). | Branch-dependent. |
| `question` | HALT; build the §6 escalation payload; return `{status: "blocked", payload: ...}`. | Terminal. |

After every spawn, verify ticket parity per [`signoff` §5]. If parity is
violated, halt immediately with a `failed` payload — do **not** attempt
to repair the ticket.

---

## 5. Failure adjudication

When the latest comment status is `blocker`, walk the four-case ladder
in [`building-epics` §3] in order; pick the FIRST matching case.

| Case | Pattern | Action | Cap (per ticket) |
|---|---|---|---|
| §3.1 Trivial mechanical | Single file/line/concrete fix | Respawn the same agent with the blocker comment as input. | 1 respawn per phase |
| §3.2 Cross-agent rework  | Review-class agent (`pr-reviewer`, `architect-review`, `status-checker`) names a sibling | Flip the named sibling to `needed`; respawn it with the reviewer's comment as input. | 1 respawn per phase pair |
| §3.3 Open-ended design   | Architectural ambiguity, multi-approach question | Spawn `brainstorm-lead` (ticket 09); append `(status: question)` comment with synthesised recommendation; surface via §6 payload. | 1 brainstorm-lead invocation |
| §3.4 Otherwise / cap exhausted | Anything else, or any case 1–3 retry that has run its cap | Verify the failed agent set `agents.<phase>: failed`; build the §6 payload; return `{status: "blocked"}`. | — |

The supervisor maintains an in-memory counter dictionary keyed by
`(ticket_path, phase, cap_kind)`. Counters are per-supervisor-invocation
and NOT persisted to the ticket file. On counter overflow, fall through
to §3.4 directly (do not re-attempt §3.1–§3.3). If the supervisor crashes
and is re-spawned, counters reset — that is acceptable because the
on-disk `agents:` map already encodes the failure history, and a
re-spawned supervisor reading a `failed` row routes to §3.4 on its own.

---

## 6. Commit-phase lock

The `commit` and `pull-request` phases mutate the git index and `HEAD`;
they cannot run concurrently across sibling tickets in the same worktree.
The `ticket-supervisor` enforces mutual exclusion via a lock file at
`<worktree_root>/.epic-commit-lock`.

| Step | What |
|---|---|
| Acquire | Atomic create-if-not-exists (POSIX `set -C` / Python `O_CREAT|O_EXCL`). On collision, exponential backoff 250ms→8s, total wait cap 60s. |
| Hold    | For the lifetime of the `commit` or `pull-request` child agent only. |
| Release | Unconditional `rm -f` on every exit path (success AND failure). Wrap in a `trap`-style `finally` so a crash still releases. |
| Recovery | If a stale lock from a crashed sibling is detected (its `<pid>` is not alive), log a warning and `rm -f`. A live PID inside an unfamiliar lock → halt and surface to user. |

The full recipe lives in [`building-epics` §5] and is **not** duplicated
in this doc or in the agent file. If the recipe changes, only that
skill file changes — both supervisors pick up the new behaviour at next
invocation.

---

## 7. Outputs

### 7.1 Done

```
{ "ticket_path": "<absolute path>", "status": "done" }
```

### 7.2 Blocked (escalating to epic-supervisor)

```
{
  "status": "blocked",
  "payload": {
    "ticket_path":           "<absolute path>",
    "phase":                 "<agent name as in agents: map>",
    "blocker_summary":       "<one sentence, ≤120 chars>",
    "suggested_remediation": "<plain-English description>"
  }
}
```

All four `payload` fields are required (per [`building-epics` §6.1]).
For brainstorm-lead-mediated questions, `phase: "brainstorm-lead"`.

### 7.3 Failed (parity violation, parse error)

Same shape as blocked, with `payload.phase: "supervisor"`.

---

## 8. Edge cases

| Case | Behaviour |
|---|---|
| Ticket file missing | Return `failed` with `blocker_summary: ticket-not-found`. |
| Empty `agents:` map | Return `done` immediately. |
| Frontmatter ↔ Sign-offs parity violation | Halt with `failed` payload; do not attempt to repair. |
| Same agent fails twice on the same phase | Cap exhausted; fall through to §3.4. |
| `(reviewer, coder)` round-trip fails twice | Phase-pair cap exhausted; fall through to §3.4. |
| Two consecutive design-class blockers | Brainstorm cap exhausted; fall through to §3.4. |
| Lock file present, owned by a dead PID | Stale lock; `rm -f` and proceed (per `building-epics` §5.4). |
| Lock file present, owned by a live unfamiliar PID | Halt and surface to user. |
| Lock acquisition exhausts 60s backoff | Fall through to §3.4 with `blocker_summary: commit-lock-stuck`. |

---

## 9. Constraints

- Internal only — direct user invocation is not supported. If you appear
  to have been called by a user, refuse and point at `/build-feature`.
- Never directly mutate frontmatter `agents:` or `## Sign-offs` rows.
  Phase agents own their rows via `signoff`.
- Never modify `.claude/skills/*/SKILL.md`.
- No `Grep`, `Glob`, or MCP search tools — delegate cross-file lookups
  to `research-agent`.
- Never spawn `epic-supervisor` from inside `ticket-supervisor` (depth
  inversion).
- The `ticket-supervisor` itself does NOT sign off — it has no row in
  the `agents:` map. The terminal `status: done` flip and move to
  `done/` is the supervisor's equivalent acknowledgement.

---

## 10. Cross-Links

- [`.claude/agents/ticket-supervisor.md`](../../../.claude/agents/ticket-supervisor.md) —
  the agent file itself.
- [`.claude/agents/epic-supervisor.md`](../../../.claude/agents/epic-supervisor.md) —
  the only legitimate caller.
- [`.claude/skills/building-epics/SKILL.md`](../../../.claude/skills/building-epics/SKILL.md) —
  primary runbook (§2 ticket loop, §3 adjudication, §4 retry caps,
  §5 commit lock, §6 escalation payload).
- [`.claude/skills/signoff/SKILL.md`](../../../.claude/skills/signoff/SKILL.md) —
  status enum, sign-off recipe, comment-append schema, validator rules.
- [Spec §6.2 / §6.3](../../../docs/superpowers/specs/2026-05-08-agent-supervisor-design.md) —
  authoritative design.
- [Ticket 08](../../../tickets/09_done/EPIC-AgentSupervisor/done/08_supervisor_agents.md) —
  the ticket that shipped this agent.

[EPIC-AgentSupervisor]: ../../../tickets/09_done/EPIC-AgentSupervisor/Master_Plan.md
[spec §6.2]: ../../../docs/superpowers/specs/2026-05-08-agent-supervisor-design.md
[`building-epics` §2]: ../../../.claude/skills/building-epics/SKILL.md
[`building-epics` §2.1]: ../../../.claude/skills/building-epics/SKILL.md
[`building-epics` §3]: ../../../.claude/skills/building-epics/SKILL.md
[`building-epics` §5]: ../../../.claude/skills/building-epics/SKILL.md
[`building-epics` §6.1]: ../../../.claude/skills/building-epics/SKILL.md
[`signoff` §5]: ../../../.claude/skills/signoff/SKILL.md
[`signoff` §5.4]: ../../../.claude/skills/signoff/SKILL.md
