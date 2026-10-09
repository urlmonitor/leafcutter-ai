---
title: "KI-AR-004 — architect-review's and conflict-resolver's Opus escalations were registered but never built, so large-impact reviews and structural conflicts have never escalated"
description: "KI-AR-004 — architect-review-deep and conflict-resolver-deep were registered but never built, so neither escalation ever ran; both are now retired and this entry holds the follow-up to build real ones"
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

# KI-AR-004 — architect-review's and conflict-resolver's Opus escalations were registered but never built, so large-impact reviews and structural conflicts have never escalated

> Index: [agent-registry.md](../agent-registry.md).

- **Severity:** medium
- **Status:** open — no AC (follow-up requested by BrainCandy, 2026-10-09; widened the same day to cover both escalations)
- **Occurrences:** 2
- **First seen:** 2026-10-09 · **Last seen:** 2026-10-09
- **Where:** `config/agent_registry.json` entries `architect-review-deep` and `conflict-resolver-deep` (both `template_path: null`, `model: opus`) — now removed; `templates/agents/architect-review.md` and `templates/agents/conflict-resolver.md` (the escalation instructions and their behavioural-pattern entries) — now rewritten

**What was found.** Two gatekeeper agents were told to escalate their hardest cases to an Opus-tier
sub-agent that does not exist:

- `architect-review` classifies a change as small or large and, for large-impact changes, was told to
  "Spawn `architect-review-deep` via the `Agent` tool".
- `conflict-resolver` classifies each conflicted file as line-by-line or structural and, for structural
  files, was told to "Spawn `conflict-resolver-deep` (Opus) via the Agent tool".

The registry listed both targets as Opus-tier agents — but each had `template_path: null` and no
`templates/agents/<id>.md` exists, so the build never deployed either. The escalations have therefore
never run: every large-impact review and every structural conflict has been handled at the base tier,
or failed to dispatch, with nothing reporting it.

**How it surfaced.** Measured while authoring the spawn-allowlist delivery criteria (AR-300c-5
family, 2026-10-09). `architect-review`'s hand-written "Available Sub-Agents" table omitted the
deep agent while the registry listed it — the only one of five hand-written tables that dropped a
registry permission — which is what led to checking whether the target exists. The same check then
found `conflict-resolver-deep` with the identical shape.

**What was done now.** Once spawn delivery lands, a declared sub-agent with no deployable
definition stops the build (AR-300c-5-iii, mirroring AR-300c-3-i). BrainCandy chose to **remove**
both dead escalations rather than build them inside that PR (decisions 10 and 13): each deep id is
removed from the gatekeeper's spawn permission, the escalation instruction and its
behavioural-pattern entry are deleted from the gatekeeper's body (the gatekeeper now handles large and
structural cases itself; `conflict-resolver` is left with no sub-agent permission at all), and the
registry entry, the `package_boundary.json` item, the schema descriptions and the agent docs and cards
no longer name either id. This loses nothing that worked, since neither escalation ever ran.

**The follow-up this entry holds.** If a deeper, Opus-tier architectural review or structural-conflict
resolution is wanted, each needs to be specified properly — acceptance criteria for what the deep
agent does beyond the base one, a real template, a test that the escalation dispatches and returns,
and a registry entry that resolves to a deployable definition. An alternative worth weighing first:
the `Agent` tool accepts a model override, so each gatekeeper could re-dispatch its own work on a
stronger model without a separate agent at all. The payloads keep their `escalation` and
`escalation_reason` fields (always `none` today) so a real escalation can be added without changing
their shape.

**Pattern:** a capability declared in the registry with no deployable definition behind it — the
same "described but not delivered" shape the AR-300 tree exists to remove, here for a whole agent
rather than a section of one, and it occurred twice.
