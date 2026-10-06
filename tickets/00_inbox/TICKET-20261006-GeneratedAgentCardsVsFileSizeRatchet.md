---
title: "Generated agent cards and docs/INDEX.md: stale on main, and over the doc-length ratchet"
status: todo
components:
  - build_pipeline
  - commit_guardian
created: 2026-10-06
depends_on: []
priority: medium
requires_diagram: false
requires_adr: false
change_target: code
risk_surface: internal
tags:
  - agent-cards
  - file-size
  - generated
last_updated: 2026-10-06
agents:
  test-writer: needed
  python-coder: needed
  commit: needed
---

# Generated agent cards and docs/INDEX.md: stale on main, and over the doc-length ratchet

## Actor / Goal
In order to start every piece of work from a clean tree, we need the committed generated files
(`docs/agents/cards/*.card.md`, `docs/INDEX.md`) to stay current with main and to be regenerable
without a hook override. Today they go stale with every AC change, and regenerating them
conflicts with the doc-length ratchet (`check-doc-length`, which reuses the GE-127b-1 ratchet
code).

## Context
- The cards are build output (`scripts/generate_agent_cards.py`). Several are far over the doc
  limit; `python-coder.card.md` is about 2500 lines. They grow every time an AC is assigned to
  that agent, because each card lists its ACs.
- The ratchet only lets an over-limit file shrink, and splitting a card by hand does not survive
  the next build. So every regeneration needs `SKIP=check-doc-length`.
- **Hit 2026-10-06** while committing TICKET-20261002-WorktreeBootstrapLeavesTrackedFilesDirty,
  which regenerated 4 stale cards. The user chose a one-off skip: "fine to skip it for now, we'll
  pick it up eventually", then "skip check-doc-length for the ticket-3 commit".

- **Stale on main, seen 2026-10-06 in CI on PR #1021.** A fresh clone plus `build.py` modified
  `docs/INDEX.md` and 6 cards: architecture-diagram-author, documentation-expert, frontend-coder,
  llm-expert, python-coder and test-writer. PRs that change ACs or docs (#1017 and #1020 the same
  day) do not regenerate them, and nothing enforces it. So `_bootstrap` still leaves every new
  worktree dirty, even after the CRLF and link-resolution fixes.
- **Moved here by user decision (2026-10-06).** The clean-checkout assertion was narrowed in
  TICKET-20261002-WorktreeBootstrapLeavesTrackedFilesDirty to "a second build changes nothing".
  The "first build on a clean checkout changes nothing" guarantee belongs to this ticket.

## Scope (options to decide)
1. **Freshness**, choose one:
   - a. Stop tracking generated cards and `docs/INDEX.md`; build them on demand and gitignore them.
     Check what reads them from a checkout without a build first.
   - b. Keep them tracked and enforce freshness: a pre-commit or CI check that regenerates and
     fails on drift, so the PR that changes ACs also commits the regenerated files.
2. **Size**, needed only if they stay tracked:
   - a. Exempt generated cards from the doc-length ratchet, because they are machine output.
   - b. Change the generator so cards stay within limits, for example by summarising or capping AC
     lists, or by linking to the AC store instead of listing every entry.
3. **Restore the guarantee.** Add back a test asserting that the first build on a clean checkout of
   main leaves no tracked file modified.

## Test Requirements

```yaml
tests:
  - name: test_first_build_on_a_clean_checkout_changes_nothing
    location: unit_tests/build_guards/test_build_leaves_tracked_files_clean.py
    type: integration
    covers: TICKET-20261006-GeneratedAgentCardsVsFileSizeRatchet
    description: |
      Clone HEAD into a temp dir and run `python scripts/build.py --target-dir .` once, the way
      _bootstrap does. Then `git status --porcelain --untracked-files=no` is empty; if not, the
      message lists each changed file. It is red today: docs/INDEX.md and 6 agent cards are stale
      on main. Whichever freshness option is chosen must make it green and keep it green.
```

## Out of Scope
- The line-ending and link-resolution fixes, done in TICKET-20261002-WorktreeBootstrapLeavesTrackedFilesDirty.

## Comments
