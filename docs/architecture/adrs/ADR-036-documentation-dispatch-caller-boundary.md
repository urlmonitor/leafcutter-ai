---
title: "ADR-036: Documentation Dispatch Is Caller-Dependent — documentation-expert Is a Human Entry Point, Never an AC's assigned_agent"
description: "Records that both routes into documentation work are legitimate and serve different callers: documentation-expert remains a supported convenience router for a person working in the main session, while an acceptance criterion's assigned_agent MUST name the leaf author directly. Generalises to the rule that an AC may not assign work to any agent whose own role is to dispatch other agents, because a subagent cannot await what it spawns."
type: "adr"
status: "active"
created: "2026-08-26"
last_updated: "2026-08-26"
deciders:
  - BrainCandy
components:
  - documentation_system
  - supervisor_system
  - agent_registry
  - ac_store
related_docs:
  - docs/known-issues/supervisor-system.md
  - docs/architecture/adrs/ADR-006-flatten-supervisor-chain.md
  - docs/architecture/adrs/ADR-019-build-feature-inline-phase-dispatch.md
  - docs/architecture/agent_delivery_workflows.md
  - docs/architecture/components/supervisor-spawn-topology.md
related_code:
  - templates/agents/documentation-expert.md
  - config/agent_registry.json
  - scripts/registry_validator.py
---

# ADR-036: Documentation Dispatch Is Caller-Dependent — `documentation-expert` Is a Human Entry Point, Never an AC's `assigned_agent`

## Status

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-08-26 |
| Deciders | BrainCandy |
| Author | Written from BrainCandy's explicit statement of the distinction on 2026-08-25/26, during the `BO-3100` / `BO-3200` enrichment pass |
| Supersedes | None |
| Context ADRs | ADR-006 (flatten supervisor chain), ADR-019 (inline phase dispatch) — both cited here **with a correction**, see §5 |

> **Component note.** `ac_store` is listed in `components:` because the field this
> decision constrains — `assigned_agent` — is an AC-store field, even though the
> rule is about agent topology. `documentation_system`, `supervisor_system` and
> `agent_registry` are the surfaces that must change to honour it.

## 1. Context

Two routes reach the same documentation specialists, and until now the project had
no recorded answer to which one is correct. The absence produced pressure in both
directions: one reading says `documentation-expert` is redundant and should be
deleted; the other says it is the front door and everything should go through it.
Both are half right, and the half each gets wrong is the same half — **neither
reading asks who is calling.**

### Route 1 — a person, from the main conversation

`documentation-expert` is a Diataxis-intent router. A person says "document this",
and it classifies the request by intent (do / decide-record / design / look up /
understand) and dispatches the matching leaf author: `how-to-author`, `adr-author`,
`architecture-diagram-author`, `reference-author`, `explanation-author`.

Its value is stated most precisely by the person it was built for:

> "my idea was just that I would always call the documentation expert so I don't
> have to remember all the other agents."
> — BrainCandy, 2026-08-25

That is a real requirement about a real user, and it is met. A single memorable
entry point that absorbs the taxonomy is exactly what a convenience router is for.

### Route 2 — the build pipeline, from an AC's `assigned_agent`

The same agent can also be named in an acceptance criterion's `assigned_agent`
field. When it is, it is not invoked by a person from the main session — it is
**dispatched as a subagent** by the build pipeline. It must then spawn a leaf
author as a grandchild and report on what that grandchild produced.

That second case is broken, and the reason is structural.

### Why route 2 cannot work — the mechanism

`docs/known-issues/supervisor-system.md` → **KI-SS-001** (severity: blocker; open;
mechanism corrected 2026-08-25) records the finding:

> **A subagent has no idle state.** In the main session, emitting text with no tool
> call ends the *turn*, and the session survives to be notified later. In a
> subagent, emitting text with no tool call ends the *agent* — that text **is** the
> result returned to the parent.

So a subagent that dispatches a child and then says "I'll wait for it" is not
failing an await. It is typing its own exit. Nor is there a wait primitive it could
reach for instead: the harness strips `TaskOutput`, `ScheduleWakeup`, `Workflow` and
`AskUserQuestion` from every subagent, and nothing else blocks until a background
task completes. Subagents are designed not to park.

The failure is silent and **shaped exactly like success**. The agent exits cleanly,
so a caller reading only its status concludes the phase completed. This is the
phantom-done shape this repository exists to prevent, relocated from the artifact
layer to the orchestration layer — and it is invisible to every gate, because no
gate runs.

`documentation-expert` is precisely an agent whose job is to dispatch another agent.
There is a recorded observation of it doing exactly this: dispatching a specialist
and returning immediately, such that an early "nothing changed" check on disk is
**not** proof the grandchild died. The stall and the success are indistinguishable
from the outside, in both directions.

The distinction that resolves everything is therefore **not** "is this agent good or
bad". It is **who is calling**:

| Caller | Position | Can consume a completion notification? | Verdict |
|---|---|---|---|
| A person, from the main conversation | Session, depth 0 | Yes — the session survives the turn | **Supported.** Keep it. |
| The build pipeline, via an AC's `assigned_agent` | Subagent | No — emitting text ends the agent | **Forbidden.** |

### What the registry says today

`config/agent_registry.json` currently records `documentation-expert` with
`spawned_by: ["ticket-supervisor"]` and a seven-entry `spawn_allowlist` covering the
five leaf authors plus `research-agent` and `glossary-triage`. That pair of
declarations asserts, as the shipped topology, exactly the arrangement this decision
forbids for pipeline dispatch: a subagent that spawns. Reconciling it is follow-on
work (see §4), not something this record performs.

## 2. Decision

**Both routes are legitimate. They serve different callers, and the rule is
caller-dependent.**

1. **`documentation-expert` remains a supported human entry point and MUST NOT be
   removed.** It is a convenience router for a person working in the main
   conversation, where the session can receive a child's completion. Its value —
   one name to remember instead of five — is the requirement it was built to meet,
   and that requirement stands. Anyone proposing to delete it MUST be pointed at
   this ADR.

2. **An acceptance criterion's `assigned_agent` MUST name the leaf author
   directly.** For documentation work that means `how-to-author`, `adr-author`,
   `architecture-diagram-author`, `reference-author` or `explanation-author`.
   An AC's `assigned_agent` MUST NOT be `documentation-expert`.

3. **The general form, stated so it is mechanically checkable.** An AC's
   `assigned_agent` MUST NOT name any agent whose own role is to dispatch other
   agents. Operationally: an agent is disqualified from appearing in
   `assigned_agent` when it holds the means to spawn (the `Agent` tool in its
   template `tools:`) **and** a non-empty `spawn_allowlist` in
   `config/agent_registry.json`. Both declarations are already recorded per agent,
   so the rule reads from data that exists rather than from prose.

4. **The invariant this instantiates, from KI-SS-001, is binding beyond
   documentation:**

   > **A subagent must never depend on the result of anything it spawns.** If it
   > needs the result, it must not delegate — it must do the work itself, or not be
   > the one orchestrating.

   That statement references no depth limit, no notification route and no fork-mode
   setting, so it survives changes to all three. It applies to **any** router-shaped
   agent, not only to `documentation-expert`, and it is the reason clause 3 is
   phrased as a property of the agent rather than as a name on a list.

### What this decision does NOT claim

**No enforcement of clause 2 or 3 exists today.** `scripts/registry_validator.py`
validates `spawn_allowlist` / `spawned_by` bidirectional consistency, unknown-agent
references, self-loops, and the `Edit`/`Write` → `requires_verification` pairing. It
has **no** rule about `assigned_agent`, and no AC-store validator has one either —
`scripts/ac_store/validate_ac.py` reads `assigned_agent` only to recognise the
deprecated `python-coder` legacy proxy. A future build-time rule in
`registry_validator.py` is the natural home for clause 3, and `AR-200` /
`INF-600` (agent-card and registry coherence) and the in-flight `BO-3100a` (spawn
authority as a declared, validated property) are the nearby criteria. **None of them
enforces this rule as of 2026-08-26.** Until one does, this is a convention held by
the authoring agents, and a violation will ship silently.

## 3. First application

The IT PO applied this rule while enriching the `BO-3100` and `BO-3200` trees on
2026-08-26. All **14** documentation ACs across the two trees name a leaf author,
and none names `documentation-expert`:

| `assigned_agent` | Count |
|---|---|
| `architecture-diagram-author` | 8 |
| `reference-author` | 4 |
| `adr-author` | 1 |
| `how-to-author` | 1 |
| `documentation-expert` | **0** |

`BO-3100d-2` states the reasoning inline as an `it_requirement`: *"AGENT CHOICE IS
DELIBERATE: adr-author, the leaf author of decision records, not
documentation-expert. A documentation-expert dispatch that then dispatches a leaf
author is the defect BO-3100c removes."* That is this decision, applied before it
was recorded; this ADR is the record it was applied against.

## 4. Consequences

### Positive

- **The user keeps the single entry point they asked for, and loses nothing.** The
  one name they wanted to remember still works, for exactly the calling position
  they use it from. The restriction lands entirely on a machine-authored field the
  user does not type.
- **The delete-it pressure is answered once.** `documentation-expert` now has a
  written justification, so its usefulness does not have to be re-argued each time
  someone notices that ACs bypass it.
- **The rule is stated as a checkable property, not a blocklist.** Clause 3 reads
  from two declarations that already exist per agent, so a future validator needs no
  new metadata and no hand-maintained list of forbidden names.
- **It generalises.** Any future router-shaped agent is covered on the day it is
  written, without amending this record.

### Negative

- **Whoever authors an AC must now know which leaf author fits the intent** — the
  Diataxis classification that `documentation-expert` performs for a human is work
  the IT PO absorbs for an AC. That cost is real and is accepted: it is paid once,
  by an agent with the architecture docs in front of it, rather than at dispatch
  time by an agent that cannot report failure.
- **Nothing stops a violation today.** An AC naming `documentation-expert` will pass
  every gate and then park silently at build time. Until clause 3 is enforced
  mechanically, this record is prose — and KI-SS-001 documents that two existing
  prompt-level rules against the same failure (`building-epics` §2.1-R1 and
  `ticket-supervisor`'s disk-diff guard) were both in force on 2026-08-18 and neither
  fired. Prompt discipline has already been tried here and rotted.
- **The registry contradicts this record until it is reconciled.**
  `documentation-expert`'s `spawned_by: ["ticket-supervisor"]` declares it a phase
  agent. That entry needs revisiting under `BO-3100a`; leaving it produces a shipped
  declaration that disagrees with an accepted decision.

### Neutral but load-bearing

- This ADR changes no template, no registry entry and no AC. It records the boundary
  so the reconciliation work can be planned against a settled answer.
- The boundary is drawn at **calling position**, which is not a property any current
  artifact records. An agent's template and registry entry describe what it may do,
  never who invoked it. That is why the rule has to be expressed as a constraint on
  `assigned_agent` — the one field that unambiguously means "the pipeline will
  dispatch this as a subagent" — rather than as a capability on the agent itself.

## 5. Relationship to ADR-006 and ADR-019 — both rest on a premise now known false

[ADR-006](ADR-006-flatten-supervisor-chain.md) and
[ADR-019](ADR-019-build-feature-inline-phase-dispatch.md) are the nearest prior
records on dispatch topology, and this decision sits beside them. **Read both with
the following caveat.**

Each argues from a **hard depth-1 Agent-tool nesting limit**, with calls beyond depth 1
"silently blocked" / "silently dropped — no error is raised, the tool call simply does
not execute." ADR-006 states it as a platform constraint with "no workaround within
the Agent tool's invocation model"; ADR-019 restates it in different words.

**That premise is false.** Nesting works. The real constraint is narrower and
different in kind: **a subagent cannot await what it spawns.** A grandchild dispatched
from depth 1 does run — the `research-agent` at the bottom of the chain in the
KI-SS-001 evidence ran fine and returned a thorough result. Only the *waiting* was
broken.

The distinction matters for anyone reasoning from those records, because the two
premises license different fixes. "Deeper calls do not fire" argues for flattening
the chain so no call is ever deep. "A subagent cannot await" argues for moving fan-out
to a layer where `await` is real, and permits nesting wherever the parent does not
need the result. This ADR takes the second position and does not repeat the first.

**A superseding record for ADR-006 and ADR-019 is separately specified as
`BO-3100d-2` and is deliberately out of scope here.** This section does not supersede
them, does not mark them superseded, and sets no supersession fields — doing so
piecemeal would produce exactly the half-completed pointer pair that `BO-3100d-2`
exists to prevent. It records the caveat only, so that a reader arriving at this ADR
does not carry the false depth story forward.

## 6. Alternatives Considered

**Remove `documentation-expert` entirely and let every caller name a leaf author.**
Rejected. It solves the pipeline problem by deleting the human affordance that
motivated the agent in the first place, and the user has stated plainly that the
single entry point is the point. The pipeline problem is fully solved by constraining
one field; removing the agent is strictly more destructive for no additional benefit.

**Route everything through `documentation-expert`, including ACs.** Rejected on the
mechanism. In an AC's `assigned_agent` it is dispatched as a subagent and must spawn a
grandchild it cannot wait for — the KI-SS-001 failure, which is silent and
indistinguishable from success. This is the option that looks most consistent and is
the only one that is structurally guaranteed to break.

**Keep `documentation-expert` in `assigned_agent` but forbid it from spawning — make
it author the doc itself.** Rejected. It collapses a router into a fifth
general-purpose documentation author and discards the Diataxis specialisation that is
the reason the leaf authors exist. It also leaves the human route worse off, since the
routing behaviour a person relies on would have to be duplicated or dropped.

**Leave it to prompt guidance in the agent templates.** Rejected on evidence.
KI-SS-001 records two prompt-level rules against this exact failure —
`building-epics/SKILL.md` §2.1-R1 "Synchronous phase dispatch (MANDATORY)" and
`ticket-supervisor`'s repo-verified disk-diff guard. Both were correct, both were in
force on 2026-08-18, and neither fired; neither could even reach the second-level
stall, because `architect-review` never loads `building-epics`. A written rule with no
mechanical backstop is what this project already has, and it did not hold. Clause 3 is
therefore phrased for a validator, and §2's "what this does not claim" states plainly
that the validator does not exist yet.

**Adopt the general invariant (clause 4) without the specific `assigned_agent` rule
(clauses 2–3).** Rejected as unactionable. "A subagent must never depend on the result
of anything it spawns" is the right invariant and the durable one, but nothing in the
repository can check it directly — it is a statement about runtime intent. Clause 3 is
the projection of that invariant onto a field a build-time rule can read.

## 7. Review Criteria

Revisit this decision if any of the following becomes true:

- Subagents gain a real wait primitive, or completion notifications become consumable
  by a spawning subagent. The mechanism in §1 would no longer hold, and route 2 would
  become safe.
- Fan-out is fully relocated to the depth-0 JS workflow runtime (the `BO-3100c`
  direction), such that no agent-level dispatch of a grandchild remains anywhere in a
  build. Clause 3 would then be enforcing an arrangement that can no longer occur.
- A documentation intent appears that genuinely cannot be classified at AC-authoring
  time and must be resolved at dispatch time. That is the one capability route 2 has
  and route 1 does not, and it is the only argument that would reopen clause 2.

## 8. References

- `docs/known-issues/supervisor-system.md` → **KI-SS-001** — the corrected mechanism
  ("a subagent has no idle state"), the two-level stall evidence from 2026-08-18, the
  rotted prompt-level fix, and the durable invariant quoted in clause 4.
- [ADR-006: Flatten the Supervisor Chain](ADR-006-flatten-supervisor-chain.md) — prior
  dispatch-topology record; **argues from the false depth-1 premise, see §5**.
- [ADR-019: build-feature.js Inlines the Phase-Dispatch Loop](ADR-019-build-feature-inline-phase-dispatch.md)
  — same false premise in different wording; **see §5**.
- [ADR-018: Agent Isolation Topology](ADR-018-agent-isolation-topology.md) — the
  isolation topology any relocated coordination must stay consistent with.
- `docs/architecture/agent_delivery_workflows.md` — supervisor dispatch topology.
- `docs/architecture/components/supervisor-spawn-topology.md` — the component-level
  record of who may spawn whom.
- `AR-200` (agent-registry) and `INF-600` (self-describing agents) — the existing
  agent-card / registry coherence criteria; the nearest homes for a future
  `assigned_agent` rule. Neither enforces one today.
- `BO-3100a` — in-flight: spawn authority as a declared, validated property, reconciled
  between `config/agent_registry.json` and `templates/agents/*.md` at build time.
- `BO-3100c` — in-flight: relocate fan-out to the layer where waiting is a real
  operation.
- `BO-3100d-2` — the separately-specified supersession of ADR-006 / ADR-019. Not
  performed by this record.
