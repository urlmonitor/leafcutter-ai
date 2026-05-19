---
title: "Implement self-hosting: separate config targets for leafcutter development"
status: todo
components:
  - build_system
  - onboard
created: 2026-05-19
depends_on: []
priority: high
requires_diagram: false
requires_adr: true
requires_documentation:
  - adr
files_touched:
  - leafcutter/scripts/build.py
  - leafcutter-ai/config/paths.json
  - leafcutter-ai/config/skills_config.default.json
  - .gitignore
  - CLAUDE.md
  - build-self.sh
  - docs/architecture/adrs/ADR-NNN-self-hosting-boundary.md
agents:
  architect-review: needed
  adr-author: needed
  python-coder: needed
  documentation-expert: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  test-writer: not_needed
  sql-coder: not_needed
  architecture-diagram-author: not_needed
  user-surface-smoker: not_needed
---

# Implement self-hosting: separate config targets for leafcutter development

## Actor / Goal

In order to eliminate the confusion between "leafcutter source" and "leafcutter build output",
we need to implement Option C from the self-hosting brainstorm — making `leafcutter-ai/` the
canonical home for leafcutter's own development artifacts, with root-level directories serving
only as compiled demo/test output.

## Context

Currently the root directory is simultaneously:
- The leafcutter package's home repository
- A "target project" that build.py writes into
- The development environment for working on leafcutter itself

This means `docs/vision.md` at root is a template placeholder, `tickets/` holds scaffold
output, and `.claude/agents/` contains agents that are also the dev tools. A newcomer
cannot tell what is source vs output.

See: `docs/brainstorm-self-hosting.md` for the full analysis and recommendation. Option C
was selected: single repo, separate config targets. `leafcutter-ai/` already contains its
own `docs/`, `tickets/`, and `CLAUDE.md` — the remaining work is teaching `build.py` to
target `leafcutter-ai/` for self-hosting and marking root-level artifacts as generated output.

## Architecture Plan

### ADRs

- `Self-hosting boundary convention: leafcutter-ai/ as canonical dev target vs root-level build output` — new ADR to be authored before coding begins.

### Documentation

- `adr` doc at `docs/architecture/adrs/ADR-NNN-<slug>.md` — Architecture Decision Record capturing the self-hosting decision, the Option C rationale, and the boundary convention (what lives in `leafcutter-ai/` vs root).

## Acceptance Criteria

```gherkin
Given a fresh clone of the repository
When a contributor runs `build.py --self`
Then leafcutter's own agents, skills, and commands are installed into leafcutter-ai/.claude/
And leafcutter-ai/docs/ contains the real project vision, roadmap, glossary
And leafcutter-ai/tickets/ contains active development tickets

Given root-level docs/, tickets/, .claude/ directories exist
When a contributor checks git status
Then those directories are gitignored (marked as generated build output)

Given a consumer wants to adopt leafcutter
When they run build.py (without --self) targeting their project root
Then the standard installation flow works unchanged (backward compatible)
```

## Sign-offs

- [ ] architect-review
- [ ] adr-author
- [ ] python-coder
- [ ] documentation-expert
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

- [ ] Write ADR documenting the self-hosting decision, Option C rationale, and boundary conventions (must precede coding)
- [ ] Add `--self` flag to `build.py` that sets `target_root` to `leafcutter-ai/` and loads its config
- [ ] Ensure `paths.json` resolution works when `target_root` is the package directory itself (offset logic or override)
- [ ] Move leafcutter development tickets from root `tickets/` to `leafcutter-ai/tickets/`
- [ ] Verify `leafcutter-ai/docs/` has real content (vision, roadmap, glossary) — not placeholders
- [ ] Update root `.gitignore` to mark root `docs/`, `tickets/`, `.claude/agents/`, `.claude/skills/` as generated output
- [ ] Add `GENERATED.md` header marker to root-level generated directories (docs/, tickets/, .claude/)
- [ ] Update root `CLAUDE.md` to direct contributors to `leafcutter-ai/CLAUDE.md` for package development
- [ ] Create `build-self.sh` (or Makefile target) one-liner for `python leafcutter/scripts/build.py --self`
- [ ] Update CI to run both modes: default consumer test and `--self` dev tooling build

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? Fully reversible — root-level outputs can be regenerated at any time by re-running `build.py`. Ticket/doc moves are git-trackable and revertible. `.gitignore` additions are additive-only.

## Open Questions

- Should `leafcutter-ai/.claude/` also be gitignored (compiled from its own templates), or checked in so that fresh clones have agents available without running build? The ADR should resolve this.
- Should the EPIC-OnboardCompleteness tickets move to `leafcutter-ai/tickets/` as part of this work, or remain at root until this migration is complete?
