---
title: "KI-AR-004 — architect-review's and conflict-resolver's Opus escalations were registered but never built, so large-impact reviews and structural conflicts have never escalated"
description: "KI-AR-004 — architect-review-deep and conflict-resolver-deep were registered but never built, so neither escalation ever ran; both are now retired and this entry holds the follow-up to build real ones"
type: reference
category: reference
status: active
created: '2026-10-09'
last_updated: '2026-10-12'
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
resolution is wanted, it needs to be specified properly: acceptance criteria for what the escalated
work does beyond the base pass, a test that the escalation actually dispatches and returns, and a
definition that really deploys. The payloads keep their `escalation` and `escalation_reason` fields
(always `none` today), so whichever option below is chosen can record an escalation without
changing their shape. Three options, collected 2026-10-12 so the decision can be made later with
them side by side (not yet decided):

**Option 1 — Two real deep agents** (`architect-review-deep`, `conflict-resolver-deep`): templates,
registry entries, spawn permissions, tests.

- Pro: fits today's agent world with no new infrastructure; buildable now through `/plan-feature`.
- Pro: each deep agent gets its own focused instructions for the hard case, and its own card,
  evals and feedback stream.
- Pro: AR-300c-5-iii and the delivery gates already guarantee a declared sub-agent resolves and is
  delivered, so it cannot silently not exist again.
- Con: two more prompts to keep consistent with their base agents (rubric, payload, constraints);
  that duplication is what drifted before.
- Con: the large/structural decision stays with the base agent's own judgement, an LLM reading a
  prose rubric, with no confidence and no exact pre-check.
- Con: runs against ADR-052 (capabilities replace agents), so it is likely to be rebuilt later.

**Option 2 — Re-dispatch on a stronger model.** The gatekeeper, having classified a case as large
or structural, re-dispatches its own work through the `Agent` tool with a model override (Opus).

- Pro: smallest change; no new agent and no second prompt, so nothing can drift apart.
- Pro: buildable now; the existing `escalation: opus` value records it.
- Con: the escalation decision is still the base model's prose judgement, as in Option 1.
- Con: the stronger run re-reads the same general instructions; it gets no instructions written
  for the hard case.
- Con: depends on the platform's model override (Claude Code's `Agent` tool); a platform without
  it (Gemini, ADR-002) cannot escalate, and the override is a harder seam to test than a named
  agent.

**Option 3 — A small Decision Kernel flow** (LangGraph, per ADR-052 and ADR-053). Deterministic
pre-checks first: much of the rubric is countable (files touched, components crossed, new
dependencies, contract or schema changes; for conflicts, a signature changed on both sides, a
rename collision, both sides editing the same block). Then Jev judges what remains against the
rubric's known criteria. A low-confidence answer escalates rather than passing, defaulting to
"structural". Only then does a `reasoning` step (Opus) do the deep review or merge, with its own
pre-checks and post-checks.

- Pro: the cheapest mechanism that can answer runs first (ADR-053 §3): code for countable facts,
  Jev for the bounded "is this large under these criteria?" call, Opus only when warranted.
- Pro: the escalation decision becomes measurable: typed answers with confidence, traced, and
  calibratable per decision type (ADR-056), instead of a prose judgement nobody can audit.
- Pro: matches the target architecture, so it is built once.
- Con: depends on the kernel hosting engineering capabilities; the capability registry
  deliberately starts empty (ADR-055), so this cannot ship before that work.
- Con: the most authoring per check: an executor for every check, Jev criteria and boundary
  cases, and an `on_uncertain` route.
- Con: Jev must only decide whether to escalate, never whether the work is right (ADR-053 §4). A
  confident wrong "small" answer is invisible at run time (§6), so the deterministic pre-checks
  and the default-to-structural rule carry real weight.

The base agents handle these cases themselves until one is chosen. Options 1 and 2 could serve as
a bridge to Option 3, but each would then be built twice.

**Pattern:** a capability declared in the registry with no deployable definition behind it — the
same "described but not delivered" shape the AR-300 tree exists to remove, here for a whole agent
rather than a section of one, and it occurred twice.
