---
title: "ADR-032: Tiered Parallel Code-Smell Review (Modern-12 Bucket Split + Depth-1 Orchestration)"
description: "Records the decision to replace the single all-12 Opus code-smell reviewer (find-code-smells) with a tiered pipeline: the Modern-12 Fowler smells are partitioned into a structural (mechanical) bucket and a design (judgment) bucket over a shared core method skill; two read-only leaf reviewer agents run the buckets on Sonnet and Opus respectively and RETURN their findings; a top-level code-smell-review skill (and /code-smell-review command) fans out to both leaves in parallel and merges into one severity-ranked report, with merge-time re-verification of high-impact findings. Orchestration is a top-level skill rather than an agent to stay within Claude Code's depth-1 sub-agent limit (ADR-006)."
type: adr
status: active
created: 2026-08-11
last_updated: 2026-08-11
components:
  - review_system
  - skills_system
  - agent_registry
  - supervisor_system
affects_diagrams: []
related_docs:
  - docs/architecture/adrs/ADR-006-flatten-supervisor-chain.md
  - docs/architecture/components/agent-registry.md
  - docs/architecture/components/skill-registry.md
  - docs/architecture/components/supervisor-spawn-topology.md
  - docs/acceptance-criteria/code-review/
related_code:
  - templates/skills/review-for-code-smells/SKILL.md
  - templates/skills/review-for-structural-code-smells/SKILL.md
  - templates/skills/review-for-design-code-smells/SKILL.md
  - templates/skills/code-smell-review/SKILL.md
  - templates/agents/find-structural-smells.md
  - templates/agents/find-design-smells.md
  - templates/commands/code-smell-review.md
  - unit_tests/test_code_smell_review_wiring.py
---

# ADR-032: Tiered Parallel Code-Smell Review (Modern-12 Bucket Split + Depth-1 Orchestration)

## Status

| Field | Value |
|-------|-------|
| Status | Accepted |
| Date | 2026-08-11 |
| Author | adr-author |
| Supersedes | — |

## Context

The package shipped a first code-smell reviewer, `find-code-smells`: a single
Opus agent that loaded one skill covering all of Martin Fowler's "Modern 12"
code smells (*Refactoring*, 2nd ed) and wrote a report. Two problems emerged
in practice:

1. **Diluted attention lowers recall.** One agent juggling all 12 lenses over
   a whole target misses findings. A single-Opus baseline review of PR #398
   missed a Shotgun-Surgery finding that a focused reviewer later caught.
2. **Uniform-tier cost.** All 12 smells ran on Opus even though roughly half
   are near-lint "mechanical" smells that a cheaper tier handles well — the
   review paid Opus rates for lint-grade work.

A further constraint shapes any fan-out design: Claude Code enforces a
**depth-1 sub-agent limit** (see ADR-006, "flatten the supervisor chain"). A
spawned agent cannot itself spawn further agents, so a reviewer-orchestrator
implemented *as an agent* could not spawn the two focused reviewers beneath it.

## Decision

1. **Split the Modern-12 into two difficulty buckets, each its own skill, over
   a shared core.** `review-for-code-smells` is the CORE method skill
   (gather → infer → scan → classify → report; the severity rubric; the
   finding/report format). `review-for-structural-code-smells` covers the 6
   mechanical smells — {Mysterious Name, Duplicated Code, Long Function, Long
   Parameter List, Loops, Repeated Switches}. `review-for-design-code-smells`
   covers the 6 judgment smells — {Global Data, Mutable Data, Feature Envy,
   Data Clumps, Primitive Obsession, Shotgun Surgery}. The two buckets MUST be
   a true partition (union = all 12, intersection = empty), and each bucket
   MUST declare a dependency on the core skill.

2. **Two tiered leaf reviewer agents, read-only.** `find-structural-smells`
   MUST run on Sonnet; `find-design-smells` MUST run on Opus. Both MUST load
   the core skill plus their bucket skill, MUST be read-only (tools:
   Bash/Read/Skill; no Write; `requires_verification: false`), and MUST RETURN
   their findings rather than writing a file.

3. **Orchestration is a TOP-LEVEL skill, not an agent.** `code-smell-review`
   (and the `/code-smell-review` command) MUST run in the top-level loop, fan
   out to both leaf agents in parallel, then merge their findings into one
   severity-ranked report. It MUST NOT be an agent: because Claude Code
   enforces a depth-1 sub-agent limit (ADR-006), a spawned agent cannot spawn
   the two reviewers. Placing the fan-out in a top-level skill keeps the
   reviewers at depth 1.

4. **Retire the single-agent `find-code-smells`.** Its template, command, and
   registry entry MUST be removed.

5. **Orchestrator merge-time verification.** When merging, the orchestrator
   MUST re-check high-impact findings — for example, re-verifying a
   duplicated-code finding's severity by checking whether the copies have
   already drifted. In practice this caught the Sonnet bucket under-rating the
   duplicated `importlib`-loader finding as MEDIUM when the two copies had
   already diverged (one catches `RuntimeError`, the other does not), promoting
   it back to HIGH.

## Consequences

### Positive

- **Higher recall.** Focused buckets each reason over their own smells rather
  than one agent thinning attention across all 12.
- **Cost tiering.** Sonnet handles the mechanical half; Opus is reserved for
  the judgment half that needs whole-target reasoning about data flow,
  ownership, and change locality.
- **Depth-1 compliance.** The top-level orchestration skill keeps both
  reviewers at depth 1, satisfying ADR-006.
- **Actionable output preserved.** Each finding still names the smell plus the
  Fowler refactoring that resolves it.

### Negative / Trade-offs

- **More artifacts to maintain.** 4 skills + 2 agents + 1 command replace the
  single retired agent, and the bucket partition must be kept exact (no smell
  dropped or duplicated) as the skills evolve.
- **Runtime paths are not unit-testable.** The runtime fan-out, the merge, and
  the depth-1 dispatch cannot be exercised in unit tests. This is a documented
  coverage boundary: the structural test
  (`unit_tests/test_code_smell_review_wiring.py`) asserts the prompt- and
  registry-level guarantees (bucket partition, agent models/tools, retirement
  of `find-code-smells`) instead of the live orchestration.

### Operational

- Reviewers are invoked via `/code-smell-review` (top-level) or the two leaf
  agents standalone; the merged report is severity-ranked with each finding
  tagged by smell + refactoring.
- Adding or moving a smell between buckets requires updating the owning bucket
  skill AND the partition assertion in the wiring test in the same change.

## Alternatives Considered

| Alternative | Rejection Reason |
|-------------|-----------------|
| Single all-12 Opus agent (the retired `find-code-smells` baseline) | Simpler and one artifact, but demonstrably lower recall (missed the PR #398 Shotgun-Surgery finding) and no cost tiering — every smell pays Opus rates including the near-lint mechanical half. |
| Workflow-based fan-out | Heavier machinery that requires explicit opt-in; unnecessary for PR-sized reviews where a top-level skill fanning out to two leaves is sufficient. |
| Size-based router (dispatch single-Opus vs the tiered pipeline by diff size) | Over-engineering — it introduces a tunable threshold to babysit. Adaptivity, if ever genuinely needed, belongs in a few lines at the top of a workflow rather than a standing router. |

## References

- [ADR-006 — Flatten the Supervisor Chain](ADR-006-flatten-supervisor-chain.md) — the depth-1 sub-agent limit that forces the orchestration to be a top-level skill rather than an agent.
- [docs/architecture/components/agent-registry.md](../components/agent-registry.md) — registers the two new leaf agents and records the retirement of `find-code-smells`.
- [docs/architecture/components/skill-registry.md](../components/skill-registry.md) — registers the core skill plus the two bucket skills and the orchestration skill.
- [docs/architecture/components/supervisor-spawn-topology.md](../components/supervisor-spawn-topology.md) — the dispatch-topology context for the depth-1 fan-out constraint.
- [docs/acceptance-criteria/code-review/](../../acceptance-criteria/code-review/) — the CR-100 AC tree; `unit_tests/test_code_smell_review_wiring.py` is the covering test.

## Bidirectional Links

This ADR does not directly govern a specific architecture diagram.
