---
title: "Kernel decision store: approved decisions filed as reviewable YAML records, reused as precedent"
status: in_progress
components:
  - decision_kernel
created: 2026-10-01
depends_on: []
priority: high
roadmap_phase: phase_kernel_1_founding
requires_diagram: false
requires_adr: true
change_target: code
risk_surface: privacy
tags:
  - decision-kernel
  - decision
  - colony-memory
last_updated: 2026-10-01
agents:
  commit: needed
---

# Kernel decision store: approved decisions filed as reviewable YAML records, reused as precedent

## Actor / Goal
In order to stop re-deciding the same design questions, we need the kernel to file every
human-approved decision as a reviewable YAML record in the repository and to offer those
records as precedent when a later run asks a matching question.

## Context
- The record format was decided by the kernel itself: decision `dec-ef8ddcb79d668a67`
  (option "Kernel-contract YAML per decision"), resolved and approved by the user on
  2026-10-01 in run `run-2fbb4ef43b1345f6` (Langfuse trace `c93592ca1a813365b7d48d5a8363c66d`).
- Stage 0 delta design (the review of the user's colony memory concept):
  [part 1](../../docs/analysis/2026-10-01-colony-memory-stage0-delta.md) to
  [part 4, decisions needed](../../docs/analysis/2026-10-01-colony-memory-stage0-delta-4-decisions-needed.md).
- The kernel trace review of the run that asked this question:
  [kernel trace review](../../docs/analysis/2026-10-01-kernel-trace-review-decision-records-run.md).

## Binding user decisions
- No Neo4j yet. Decisions are files in `docs/decisions/` behind a `ColonyMemory` interface so a
  graph backend can replace the store later without kernel changes. This departs deliberately
  from concept section 7 and the (uncommitted, other-worktree) ADR-057.
- Precedent from day one: past decisions are pulled into a new decision and Jev judges whether
  each applies. Automatic influence on routing scores or thresholds stays gated (calibration).
- Only human-approved decisions become records. Nothing derives authority from a model-written
  record. Records cannot self-authorize.
- The kernel stays read-only during a run. A run stages an approved record in its run
  artifacts; the explicit CLI command `python -m kernel decisions publish --run-id R` writes it
  into `docs/decisions/` after validation, for normal git review. The `/leafcutter` skill may
  announce a staged record but never runs publish.

## Scope (no acceptance criteria by user decision)
Part 1, the store: ADR-059, ADR-060, ADR-061; `config/decision_record.schema.json`; the
`kernel/memory/` package (port, null and file backends, record models, builder, validation,
generated index); the `decisions validate|index|publish` CLI; the first record; docs, "As
built" notes and a changelog entry. The knowledge map reads the records through the existing
`docs` surface; the dedicated `decisions` surface in `config/paths.json` is deferred (see
Comments): a new registry entry needs an acceptance criterion with `package_surface: true`.
Validation at commit rides the normal test suite (no new pre-commit hook: that is package
surface and needs ACs).

Part 2, the learning loop: staging an approved record from a resolved decision, precedent
lookup and judgement inside the assess batch, the confirm question (`reuse` or `decide_anew`),
and the round-8 defects (a) human-added option without cited evidence, (b) null `trace_refs`
in the decision report, (c) no decision section in report.md, (d) duplicated retrieval-cut
limitations, (e) every criterion citing all evidence, (f) a named contract or class not
fetched by symbol.

Part 3, proof: an offline three-run end-to-end test through the real service and graph, and a
live check of the decision-records goal against this worktree.

## Files
Authoritative list is the commit; see `git log` for `#KernelDecisionStore`.

## Comments

### 2026-10-01 16:40 — python-coder (status: ok)
feedback-id: fb_2026-10-01_b8d1b96d

Built in two commits. Part 1 (the store): ADR-059, ADR-060, ADR-061, the record schema, the
`kernel/memory/` package, the `decisions validate|index|publish` CLI, record
`dec-ef8ddcb79d668a67` (staged through the real builder and published through the real CLI, then
validated) and the how-to. Part 2 and 3 (the learning loop and the proof): staging, precedent,
the confirm question, the six round-8 fixes, the offline three-run test and the live check.

Deviations from the brief, both deliberate:
- **No `decisions` surface in `config/paths.json`.** The commit-msg hook
  `check-package-surface-declaration` refuses a new `config/paths.json` entry unless a cited
  acceptance criterion carries `package_surface: true`, and this ticket has no ACs by user
  decision. The knowledge map already reads `docs/decisions/*.yaml` through the existing `docs`
  surface (id, title, component edges; a test asserts it). The dedicated surface would add the
  `supersedes`, `superseded_by` and `related` edges. To add it later, author the AC, then add to
  `surfaces` in `config/paths.json`: `"decisions": {"path": "docs/decisions/", "edge_fields":
  ["components", "supersedes", "superseded_by", "related"], "_optional": true}`.
- **Retrieval benchmark re-baselined for three cases.** The benchmark measures the lexical stage
  over the real checkout, and the checkout now holds the decision store (ADR-059..061, the
  how-to, `kernel/memory/`), which answers exactly what those goals ask. No ranking code changed;
  the fixture notes say which results moved and why.

Open: the `decision` capability's `side_effect_class` is now `run_artifacts` (it stages a record
in the run root). `docs/decisions` is not a retrieval source: precedent comes through the memory
port, so ordinary research does not see records as `prior_decisions` evidence.
