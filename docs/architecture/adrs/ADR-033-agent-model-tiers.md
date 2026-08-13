---
title: "ADR-033: Agent Model Tiers and Gatekeeper Escalation"
description: "Decision to pin every agent to one of three model tiers (haiku/sonnet/opus), reach Opus only through a Sonnet gatekeeper, and hold each agent to a tier-floor tool allowlist with all cross-cutting search delegated to a single research-agent."
type: "adr"
status: "active"
created: "2026-08-13"
last_updated: "2026-08-13"
deciders:
  - BrainCandy
components:
  - agent_registry
  - build_pipeline
related_docs:
  - docs/agents/conventions.md
  - docs/agents/README.md
  - docs/architecture/agent_delivery_workflows.md
related_code:
  - config/agent_registry.json
  - scripts/registry_validator.py
---

# ADR-033: Agent Model Tiers and Gatekeeper Escalation

## Status

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-08-13 |
| Deciders | BrainCandy |
| Author | Retroactive record written during the 2026-08-13 ADR numbering repair |
| Context ADRs | ADR-006 (flatten the supervisor chain), ADR-018 (agent isolation topology) |

## 1. Context

Every agent template declares a `model:` tier and a `tools:` allowlist. Those two
fields decide what the agent costs, how much context it consumes, and whether it can
reach the rest of the codebase. Left unconstrained, agent authoring drifts in three
predictable directions: everything gets pinned to the most capable model "to be safe",
every agent gets `Grep` and `Glob` "just in case", and sub-agents nest until the
dispatch chain is impossible to reason about.

The governing policy has been enforced in practice since the package's early history —
it is written up operationally in [`docs/agents/conventions.md`](../../agents/conventions.md),
validated mechanically by `scripts/registry_validator.py`, and encoded in the `model`
field of `config/agent_registry.json`. **The decision record itself was missing from
this repository.** Around 116 citations across 38 files pointed at an
`agent-model-tiers` ADR numbered 006 — a file that did not exist here, since `ADR-006`
in this corpus is the unrelated *Flatten the Supervisor Chain* decision. This ADR is
that missing record, written at a free number, with those citations repointed to it.

`docs/agents/conventions.md` remains the operational how-to. This ADR is the *why*.

## 2. Decision

### 2.1 Three-Tier Model Ladder

Every agent pins `model:` to exactly one of three values. The default is `sonnet`.

| Tier | When to pick it |
|---|---|
| `haiku` | Mechanical, deterministic procedures with no judgement — inputs map to outputs by a fixed recipe. |
| `sonnet` | Standard software-engineering work bounded by clear patterns. The default for nearly every agent. |
| `opus` | Novel synthesis or escalation. Valid **only** as the spawn target of a Sonnet gatekeeper (§2.3), never chosen at an agent's own level outside that role. |

Reaching for a higher tier is a cost and latency decision, not a safety net. An agent
whose work is genuinely mechanical belongs on Haiku even when the surrounding epic is
complex.

### 2.2 Pattern A — Skill Wrapper

A thin agent whose entire job is to load one skill and execute it. Pinned to the lowest
tier the skill's work honestly requires — usually Haiku. It carries the Haiku tool floor
and no more. If a wrapper needs judgement to decide *which* skill to run, it is not a
Skill Wrapper; see §2.4.

### 2.3 Pattern B — Gatekeeper Escalation

The only sanctioned route to Opus. A Sonnet agent does the bounded work and decides,
against a documented rubric, whether the case exceeds what a pattern-following tier can
resolve. Only then does it spawn an Opus sub-agent with a narrowed payload.

This keeps Opus spend proportional to genuine difficulty rather than to the author's
caution, and it forces the escalation criterion to be written down and reviewable. An
Opus agent with no Sonnet gatekeeper in front of it is a review-blocker.

### 2.4 Pattern C — Multi-Skill Dispatcher

An agent that routes between several skills by classifying the request first. It runs
at Sonnet because the routing decision is judgement, even when each downstream skill is
mechanical. Named for a role rather than a single skill.

### 2.5 Visibility Classes

Every agent is exactly one of three classes, and the `description` field must take that
class's shape — the description is what makes auto-trigger fire reliably.

| Class | Meaning |
|---|---|
| User-facing | Invoked directly by the user, typically via a slash command. |
| Confirmation-gated | Performs a destructive or outward-facing action and must obtain explicit approval first. |
| Internal | Only ever spawned by a parent agent; never user-invoked. |

Hybrids are forbidden. In particular, a confirmation-gated agent must never be *spawned*
to serve an interactive action — relayed approval is not approval.

### 2.6 Tool Allowlist & Strict Research Delegation

Each agent's `tools:` is the **minimum** needed for its job, with per-tier floors:

| Tier | Minimum `tools:` | Add-on |
|---|---|---|
| Haiku | `Bash, Read` | — |
| Sonnet | `Bash, Read, Write, Edit` | `+ Agent` if it spawns sub-agents |
| Opus | `Bash, Read, Write, Edit` (as a gatekeeper's spawn target) | `+ Agent` if it spawns further sub-agents |

An empty `tools:` value means *no tools*, not "all default tools". `*` is never allowed
without an inline comment citing this section.

**Strict research delegation.** `Grep`, `Glob`, and all `mcp__jcodemunch__*`,
`mcp__plugin_serena_serena__*` and `mcp__plugin_context7_context7__*` tools are removed
from every non-research agent. All cross-cutting search goes through a single
`research-agent`, which keeps the full toolkit and returns curated findings.

The reason is context economy: a spawned agent holding `Grep` and `Glob` reproduces the
parent's entire research surface inside its own context and balloons its return payload,
which defeats the cost rationale for spawning it at all.

Two carve-outs, and only two: the **user-facing interactive session** (not a spawned
agent — the user steers it directly) and **`research-agent` itself** (the rule would be
self-defeating).

Narrowing below a tier floor is always allowed and encouraged. **Widening** above it
requires a comment block in the agent file justifying the exception.

### 2.7 Nesting Depth — Soft Cap of 3

Agent spawn chains were capped at a depth of 3 to keep dispatch logs readable and stop
an epic drive from fanning out unboundedly.

> **Superseded in practice.** The runtime now enforces a **hard limit of depth 1** —
> sub-agents cannot spawn further sub-agents. [ADR-006 — Flatten the Supervisor
> Chain](ADR-006-flatten-supervisor-chain.md) restructured the supervisor topology
> around that limit. The soft cap is recorded here as the original reasoning; the
> depth-1 hard limit is what binds today.

### 2.8 Clarifications on Edge Cases

- An agent that only *reads* still declares a tier; read-only does not imply Haiku.
- Slash-command names and agent names share a namespace — a collision must be resolved
  by renaming, not by relying on dispatch order.
- Dropping `Write`/`Edit` from a Sonnet agent that is genuinely read-only needs no
  justification. Adding a tool above the tier floor always does.

## 3. Alternatives Considered

| Option | Verdict | Reason |
|---|---|---|
| Single model for all agents | Rejected | Either overpays for mechanical work or underpowers synthesis. |
| Per-agent free choice, no tiers | Rejected | Drifts to "highest tier, all tools" with no reviewable criterion. |
| Opus reachable directly | Rejected | Removes the forcing function that makes the escalation rubric explicit. |
| Every agent keeps the search toolkit | Rejected | Duplicates the research surface per agent and inflates payloads. |

## 4. Consequences

### Positive

- Model spend tracks genuine difficulty, because escalation must be argued for.
- Spawned-agent contexts stay small, so return payloads stay reviewable.
- `model:` and `tools:` become mechanically checkable — `registry_validator.py` enforces them.

### Negative

- Authors must route search through `research-agent` rather than grepping inline, which
  costs a round trip.
- The tier-floor exception comment is friction on legitimately unusual agents.

### Neutral

- The three-tier vocabulary is fixed; adding a tier is an ADR-level change.

## 5. References

- [`docs/agents/conventions.md`](../../agents/conventions.md) — the operational how-to that implements this policy
- [`docs/agents/README.md`](../../agents/README.md) — the tier table across the live agent set
- [ADR-006 — Flatten the Supervisor Chain](ADR-006-flatten-supervisor-chain.md) — the depth-1 topology that supersedes §2.7
- [ADR-018 — Agent Isolation Topology](ADR-018-agent-isolation-topology.md)

## 6. Review Criteria

An agent template passes model-tier review when all of the following hold:

1. `model:` is one of `haiku`, `sonnet`, `opus`, and the choice matches §2.1.
2. If `model: opus`, a named Sonnet gatekeeper spawns it against a documented rubric (§2.3).
3. `tools:` meets its tier floor (§2.6) and is non-empty.
4. No `Grep`, `Glob`, or MCP search tool appears unless the agent is `research-agent`.
5. Any tool above the tier floor carries the justification comment block.
6. The `description` matches the agent's visibility class shape (§2.5), with concrete
   "Use when:" triggers.
