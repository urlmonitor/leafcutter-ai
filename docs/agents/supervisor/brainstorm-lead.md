---
title: 'Agent Reference: brainstorm-lead (and brainstorm-worker)'
type: reference
status: active
created: 2026-05-08
last_updated: 2026-05-08
components:
- infrastructure
related_docs:
- docs/agents/conventions.md
- docs/agents/coding/epic-supervisor.md
- docs/architecture/adrs/ADR-033-agent-model-tiers.md
- docs/superpowers/specs/2026-05-08-agent-supervisor-design.md
- tickets/09_done/EPIC-AgentSupervisor/Master_Plan.md
related_code:
- .claude/agents/brainstorm-lead.md
- .claude/agents/brainstorm-worker.md
- .claude/agents/ticket-supervisor.md
- .claude/skills/building-epics/SKILL.md
- .claude/commands/build-feature.md
description: 'Overview of Agent Reference: brainstorm-lead (and brainstorm-worker).'
---
# Agent Reference: `brainstorm-lead` (and `brainstorm-worker`)

Implementing agents:
- `brainstorm-lead` (Opus, internal-only).
- `brainstorm-worker` (Sonnet, internal-only) — only spawned by `brainstorm-lead`.

Family: `coding/`.

The brainstorm tier is the third escalation level in the failure
adjudication ladder defined by [`building-epics` §3]. When
`ticket-supervisor` encounters an open-ended design question that
mechanical adjudication cannot resolve, it spawns `brainstorm-lead`,
which runs 2-3 single-perspective `brainstorm-worker`s in parallel and
synthesises a single recommendation.

This doc covers the pair as a unit because they only make sense
together.

---

## 1. When `brainstorm-lead` is spawned

`brainstorm-lead` is spawned **only** by `ticket-supervisor`, only via
[`building-epics` §3.3], and only **after** the supervisor has already
ruled out the cheaper adjudication tiers:

| Tier | Pattern | Why brainstorm is wrong here |
|---|---|---|
| §3.1 — Trivial mechanical | Single file/line/concrete fix | Mechanical retry is faster and cheaper. |
| §3.2 — Cross-agent rework | Reviewer names a sibling whose work needs revision | The work is well-defined; just respawn the sibling. |
| **§3.3 — Open-ended design choice** | Architectural ambiguity, multiple plausible approaches, weighing trade-offs | **This is the brainstorm tier.** |
| §3.4 — Otherwise / cap exhausted | Infrastructure failure, secret missing, user-only decision, retry cap exceeded | The user is the only one who can decide. |

Examples of questions that legitimately reach §3.3:

- "Should this be a JSONB column or a separate normalised table?"
- "Should we cache here or push the cache into the consumer?"
- "Synchronous publish-and-wait, or async fire-and-forget?"
- "One row per symbol-day or one row per symbol with a JSONB array?"

The retry cap is **1 invocation per ticket** ([`building-epics` §4]).
A second design-class blocker on the same ticket falls through to
§3.4 — the supervisor halts and surfaces to the user. This is a hard
cost ceiling, deliberately tight: brainstorm is meant to handle
genuinely-open questions, not to substitute for design work that
should have happened in `refinement` or `architect-review`.

### Threshold note (cost discipline)

`brainstorm-lead` runs on Opus and spawns up to 3 Sonnet workers in
parallel. A single invocation costs roughly 4× a default Sonnet call.
Routing a §3.1- or §3.2-class blocker into the brainstorm tier wastes
tokens AND consumes the per-ticket cap, so a subsequent legitimate
design question on the same ticket is forced through §3.4 to the user
without brainstorm benefit. Both `ticket-supervisor`'s prompt and
`brainstorm-lead`'s own prompt encode this discipline.

---

## 2. Perspective strategy

The lead picks 2-3 perspectives suited to the question.

### Default trio

`simplicity`, `robustness`, `reversibility` — chosen because they cover
the most common axes on which design choices in this codebase are
weighed:

- **simplicity** — surface area, moving parts, concept count.
- **robustness** — degrades-gracefully under partial failure / load.
- **reversibility** — cheapest to undo if proven wrong (one-way doors).

### Substitution rules

The lead substitutes one default with a different lens when the
question is dominated by another concern:

| Question characteristic | Substitute with |
|---|---|
| Hot-path / latency / data-volume question | `performance` |
| Public API / human-caller / discoverability | `usability` |
| Long-lived schema / ageing module / churn-prone area | `maintainability` |

### Number of workers

| Workers | When |
|---|---|
| **2** | Genuinely binary question (e.g. "sync or async") |
| **3** (default) | Multi-axis trade-off |
| **4+** | NEVER. Lead returns `outcome: reject` with reason `question-too-broad` and asks the supervisor to split. |

### Parallel dispatch (load-bearing)

The lead MUST spawn the workers in parallel — multiple `Agent` tool
calls in a single message. Serial dispatch multiplies wall-clock cost
without changing the answer. This is the single project convention for
parallel sub-agent fan-out and is non-negotiable for this agent.

---

## 3. Synthesis algorithm

The synthesis strategy is **structured recommendation merge** with
consensus-or-present-all. This was chosen over alternatives (vote
tallying, weighted voting, perspective-priority ranking) because:

- It is the simplest algorithm that does not silently suppress minority
  opinions.
- It produces a single actionable recommendation when workers agree
  AND a faithful all-views envelope when they do not — both of which
  the supervisor can route mechanically.
- It does not require the lead to weight perspectives (which would
  add a hidden hyperparameter).

The choice is **fixed by ticket 09 of EPIC-AgentSupervisor** ("Design
Decisions" section). Future revisions to the synthesis strategy require
a new ticket, not an ad-hoc change in the agent prompt.

### Algorithm

```
1.  Receive { question, ticket_path }.
2.  Choose perspectives (§2 above).
3.  Spawn 2-3 brainstorm-workers IN PARALLEL.
4.  Wait for all worker outputs (barrier).
5.  Each worker returns:
        perspective: <name>
        recommendation: <one line>
        rationale: <2-4 sentences>
        risks: <1-3 bullets>
6.  Normalise each recommendation (whitespace, case-folding) — but
    DO NOT paraphrase. Equivalence is judged on substantive choice.
7.  IF 2+ workers' recommendations describe the same substantive choice:
        → outcome: consensus
        → recommendation: <the agreed-on choice>
        → rationale: <synthesised — names which perspectives concurred,
                      surfaces the strongest single risk seen across them>
    ELSE (every worker disagrees):
        → outcome: tie
        → alternatives: <full envelope of every worker's
                         {perspective, recommendation, rationale, risks}>
8.  Return to ticket-supervisor.
```

### What the supervisor does with each outcome

| Outcome | Supervisor action |
|---|---|
| `consensus` | Append a `(status: question)` comment containing the recommendation + synthesised rationale. Surface the [`building-epics` §6] payload to the user with `phase: brainstorm-lead`. The user can accept the recommendation by simply replying "go", or override by appending an answering comment. |
| `tie` | Append a `(status: question)` comment containing the full present-all envelope. Surface the §6 payload. The user picks an option. |
| `reject` | Fall through to [`building-epics` §3.4] — halt and surface as a §6 payload with a reason that names the rejection cause. |

---

## 4. Escalation to user

The brainstorm tier does NOT escalate to the user directly. It returns
its structured output to `ticket-supervisor`. The supervisor then:

1. Appends a `## Comments` entry with `(status: question)` containing
   the recommendation (consensus) or the present-all envelope (tie).
   Heading format follows [`signoff` §3].
2. Builds the [`building-epics` §6] payload with `phase: brainstorm-lead`
   and a `blocker_summary` distilled from the recommendation /
   alternatives.
3. Returns `{status: "blocked", payload: ...}` to `epic-supervisor`,
   which relays to the user.
4. The epic continues with independent siblings unless the structural
   halt conditions in [`building-epics` §1.3] are met.

When the user replies (typically by editing the ticket file directly —
e.g. flipping the `failed` row back to `needed` and appending an
answering comment with the chosen approach), they re-invoke
`/build-feature <epic>` and the epic-supervisor re-enters its main
loop with the resolved ticket once again `ready`.

---

## 5. `brainstorm-worker` constraints (single-perspective analyst)

The worker is deliberately minimal:

| Constraint | Why |
|---|---|
| **Tools: `Read, Bash` only.** No `Edit`, `Write`, or `Agent`. | Single-shot analyst; no side-effects, no sub-agents. |
| **Single perspective.** | The lead is composing a multi-perspective view by spawning multiple workers; each worker advocates ONE lens. |
| **Strict output schema.** | The lead parses on the keys `perspective`, `recommendation`, `rationale`, `risks`. Deviations break synthesis. |
| **Structured rejection on malformed input.** | Even on the failure path, the worker returns the same shape (with `recommendation: REJECT — ...`) so the lead can include it in synthesis. |
| **No sign-off, no ticket mutation.** | Workers are not phase agents. They do not invoke the `signoff` skill. |

The worker file is `.claude/agents/brainstorm-worker.md`. There is no
separate reference doc for the worker — it exists only as the lead's
sub-agent and is documented in this same file (§5 above).

---

## 6. Edge cases

| Case | Behaviour |
|---|---|
| Worker returns malformed-input rejection | Treat as `recommendation: REJECT`, include in synthesis. Do NOT respawn or substitute a new worker — the cap and parallel-dispatch contract preclude it. |
| All workers return `REJECT` | Lead returns `outcome: reject` with reason `all-workers-rejected`. Supervisor falls through to §3.4. |
| Question is genuinely binary | Spawn 2 workers (not 3). The two perspectives chosen should be the most relevant — the default trio's `simplicity` + `robustness` is a reasonable fallback. |
| Lead would need 4+ perspectives | Return `outcome: reject` with reason `question-too-broad`. Ask the supervisor to split. |
| Lead is invoked without a `ticket_path` | Return `outcome: reject` with reason `missing-input`. |
| Lead is invoked but `building-epics` §3.1 / §3.2 clearly applies | Return `outcome: reject` with reason `should-have-been-mechanical`. The supervisor's prompt is the first line of defence; this is a backstop. |

---

## 7. Cross-Links

- [`.claude/agents/brainstorm-lead.md`](../../../.claude/agents/brainstorm-lead.md) —
  the agent file (frontmatter + system prompt).
- [`.claude/agents/brainstorm-worker.md`](../../../.claude/agents/brainstorm-worker.md) —
  the single-perspective sub-agent.
- [`.claude/agents/ticket-supervisor.md`](../../../.claude/agents/ticket-supervisor.md) —
  the only legitimate caller of `brainstorm-lead`. See its "Failure
  adjudication" section for case 3.
- [`.claude/agents/epic-supervisor.md`](../../../.claude/agents/epic-supervisor.md) —
  the outer driver above the supervisor.
- [`.claude/skills/building-epics/SKILL.md`](../../../.claude/skills/building-epics/SKILL.md) —
  §3.3 (when invoked), §4 (1-per-ticket cap), §6 (escalation payload
  schema).
- [`.claude/skills/signoff/SKILL.md`](../../../.claude/skills/signoff/SKILL.md) —
  comment heading schema (§3); the supervisor uses this to write the
  `(status: question)` comment that carries the brainstorm output.
- [`.claude/commands/build-feature.md`](../../../.claude/commands/build-feature.md) —
  user-facing entry point that ultimately leads here through the
  failure-adjudication ladder.
- [`docs/agents/coding/epic-supervisor.md`](epic-supervisor.md) —
  outer-driver reference doc.
- [Spec §5.1, §6.3, §12](../../../docs/superpowers/specs/2026-05-08-agent-supervisor-design.md) —
  agent definitions, escalation flow, and the deferred-item record
  that ticket 09 closed by picking the synthesis strategy.
- [Ticket 09](../../../tickets/09_done/EPIC-AgentSupervisor/done/09_brainstorm_agents.md) —
  the ticket that shipped this pair.

[`building-epics` §3]: ../../../.claude/skills/building-epics/SKILL.md
[`building-epics` §3.3]: ../../../.claude/skills/building-epics/SKILL.md
[`building-epics` §3.4]: ../../../.claude/skills/building-epics/SKILL.md
[`building-epics` §4]: ../../../.claude/skills/building-epics/SKILL.md
[`building-epics` §6]: ../../../.claude/skills/building-epics/SKILL.md
[`building-epics` §1.3]: ../../../.claude/skills/building-epics/SKILL.md
[`signoff` §3]: ../../../.claude/skills/signoff/SKILL.md
