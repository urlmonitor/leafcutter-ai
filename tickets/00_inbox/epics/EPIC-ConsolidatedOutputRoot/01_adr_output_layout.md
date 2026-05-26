---
title: "Author ADR for consolidated output layout decision"
status: todo
components:
  - build_pipeline
created: 2026-05-26
depends_on: []
priority: high
requires_diagram: false
requires_adr: true
agents:
  architect-review: needed
  adr-author: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  python-coder: not_needed
  test-writer: not_needed
  documentation-expert: not_needed
---

# 01: Author ADR for Consolidated Output Layout

## Goal
In order to formalise the output-layout design, we need a new Architecture
Decision Record that documents why all `build.py` outputs move to a single
`leafcutter-project/` root, what alternatives were considered (symlinks,
physical copies, no-change), and the consequences for tools that read fixed
paths (Claude Code, pre-commit, Gemini/Antigravity).

## Context
This epic changes where `build.py` writes its outputs. That is a binding,
cross-cutting architectural decision: it affects every downstream consumer of
leafcutter, every tool that expects files at specific paths (`.claude/`,
`scripts/`, `.pre-commit-config.yaml`, `.gemini/`, `.antigravity/`), and the
self-hosting boundary described in ADR-001-self-hosting-boundary.md.

An ADR must exist and be accepted before any implementation tickets (02–06) can
be merged. This ticket produces that ADR.

Key questions the ADR must resolve (see also Master_Plan.md Open Questions):
- Does Claude Code follow symlinks for `.claude/agents/` and `.claude/skills/`?
  Answer determines whether a symlink shim layer is viable or whether physical
  copies must remain.
- Output root name (`leafcutter-project/`, `.leafcutter/`, `leafcutter-out/`).
- Commit vs gitignore posture for the output root.

The ADR will reference ADR-001 (self-hosting boundary) and may require updating
its "Consequences" section once the new layout is adopted.

## Architecture Plan

### ADRs

- `leafcutter-ai/docs/architecture/adrs/ADR-NNN-consolidated-output-root.md` —
  new ADR to be authored, covering the output-layout decision, alternatives, and
  consequences. Replaces/supersedes the "Negative" note in ADR-001 about
  `scripts/` being at root.

## Acceptance Criteria

```gherkin
Given ADR-NNN-consolidated-output-root.md is written and accepted
When a developer reads it
Then it documents: (a) chosen output root name, (b) symlink/copy strategy for
  .claude/ and other fixed-path tools, (c) commit-vs-gitignore posture, (d)
  migration impact on existing installs, (e) alternatives considered

Given ADR-001 references the new ADR
When a developer reads ADR-001
Then the "Consequences" section notes the superseded layout or links to ADR-NNN
```

## Sign-offs

- [ ] architect-review
- [ ] adr-author
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

### adr-author
- [ ] Investigate whether Claude Code follows symlinks for `.claude/` discovery
  (can be tested locally — create a symlink `.claude/agents -> leafcutter-project/agents`
  and verify Claude Code loads the agents)
- [ ] Document findings in ADR-NNN-consolidated-output-root.md at
  `leafcutter-ai/docs/architecture/adrs/`
- [ ] Record chosen output root name, symlink strategy, and gitignore posture
- [ ] Amend or update ADR-001 to reference the new ADR

### architect-review
- [ ] Validate that the ADR covers the three hard constraints: Claude Code
  discovery, pre-commit root-path requirement, Gemini/.antigravity fixed paths
- [ ] Confirm the shim/symlink strategy is feasible on Windows (symlinks require
  elevated privileges or Developer Mode — note risk)

## Risk & Safety
- Touches money? No.
- Touches data? No.
- Reversibility? ADR documents a decision; reversing it would require a new ADR.
  Low risk — no code is changed in this ticket.
- Windows symlink concern: symlinks on Windows require Developer Mode or admin
  elevation. If symlinks are not viable on Windows, the shim strategy must use
  file copies with a manifest-tracked dirty flag instead.
