---
title: "KI-AR-004 — architect-review's Opus escalation was registered but never built, so large-impact reviews have never escalated"
description: "KI-AR-004 — architect-review's Opus escalation was registered but never built, so large-impact reviews have never escalated"
type: reference
category: reference
status: active
created: '2026-10-09'
last_updated: '2026-10-09'
components:
  - agent_registry
related_docs:
  - docs/known-issues/agent-registry.md
  - docs/known-issues/README.md
---

# KI-AR-004 — architect-review's Opus escalation was registered but never built, so large-impact reviews have never escalated

> Index: [agent-registry.md](../agent-registry.md).

- **Severity:** medium
- **Status:** open — no AC (follow-up requested by BrainCandy, 2026-10-09)
- **Occurrences:** 1
- **First seen:** 2026-10-09 · **Last seen:** 2026-10-09
- **Where:** `config/agent_registry.json` entry `architect-review-deep` (`template_path: null`, `model: opus`); `templates/agents/architect-review.md` (the escalation instruction and its behavioural-pattern entry)

**What was found.** `architect-review` classifies a change as small or large and, for large-impact
changes, is told to "Spawn `architect-review-deep` via the `Agent` tool". The registry lists
`architect-review-deep` as an Opus-tier review agent — but its `template_path` is `null` and no
`templates/agents/architect-review-deep.md` exists, so the build never deploys it. The escalation
has therefore never run: every large-impact review has been handled at the base tier, or failed to
dispatch, with nothing reporting it.

**How it surfaced.** Measured while authoring the spawn-allowlist delivery criteria (AR-300c-5
family, 2026-10-09). `architect-review`'s hand-written "Available Sub-Agents" table omitted the
deep agent while the registry listed it — the only one of five hand-written tables that dropped a
registry permission — which is what led to checking whether the target exists.

**What was done now.** Once spawn delivery lands, a declared sub-agent with no deployable
definition stops the build (AR-300c-5-iii, mirroring AR-300c-3-i). BrainCandy chose to **remove**
the dead escalation rather than build it inside that PR: `architect-review-deep` is removed from
`architect-review`'s spawn permission, the escalation instruction and its behavioural-pattern entry
are deleted from `architect-review`'s body, and the registry entry is retired. This loses nothing
that worked, since the escalation never ran.

**The follow-up this entry holds.** If a deeper, Opus-tier architectural review is wanted for
large-impact changes, it needs to be specified properly — acceptance criteria for what the deep
review does beyond the base one, a real template, a test that the escalation dispatches and
returns, and a registry entry that resolves to a deployable definition. An alternative worth
weighing first: the `Agent` tool accepts a model override, so `architect-review` could re-dispatch
its own review on a stronger model without a separate agent at all.

**Pattern:** a capability declared in the registry with no deployable definition behind it — the
same "described but not delivered" shape the AR-300 tree exists to remove, here for a whole agent
rather than a section of one.
