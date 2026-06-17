---
epic_name: EPIC-CodeQualityHooks
created: 2026-06-16
status: in_progress
components:
  - guardrail-engine
source_ac: GE-100
---
# EPIC-CodeQualityHooks

## Goal

This epic implements AC GE-100: Pre-commit hooks detect duplicate code and gate test coverage on changed lines. It consists of 17 ticket(s) generated from the leaf ACs beneath GE-100, assembled in topological build order with all inter-ticket dependencies derived from the AC depends_on graph.

## Tickets

| # | File | Title | Source AC | Depends On |
|---|------|-------|-----------|------------|
| 01 | [01_TICKET-20260616-GE-100a.md](./01_TICKET-20260616-GE-100a.md) | jscpd hook exits cleanly when the jscpd binary is not installed | GE-100a | GE-100 |
| 02 | [02_TICKET-20260616-GE-100a-1.md](./02_TICKET-20260616-GE-100a-1.md) | jscpd hook rejects version 4.x with an actionable error and exits fail-open | GE-100a-1 | GE-100a |
| 03 | [03_TICKET-20260616-GE-100a-2.md](./03_TICKET-20260616-GE-100a-2.md) | jscpd hook forces staged-only mode when working tree is under /mnt/c/ (WSL2) | GE-100a-2 | GE-100a |
| 04 | [04_TICKET-20260616-GE-100b.md](./04_TICKET-20260616-GE-100b.md) | jscpd hook reports duplicate code blocks that overlap with staged files | GE-100b | GE-100, GE-100a |
| 05 | [05_TICKET-20260616-GE-100b-1.md](./05_TICKET-20260616-GE-100b-1.md) | jscpd hook filters results to only report clones involving staged files | GE-100b-1 | GE-100b |
| 06 | [06_TICKET-20260616-GE-100c.md](./06_TICKET-20260616-GE-100c.md) | jscpd hook blocks commit when strict mode is enabled and duplicates exceed threshold | GE-100c | GE-100, GE-100b |
| 07 | [07_TICKET-20260616-GE-100c-1.md](./07_TICKET-20260616-GE-100c-1.md) | jscpd hook exits fail-open when the jscpd subprocess exceeds the 30-second timeout | GE-100c-1 | GE-100c |
| 08 | [08_TICKET-20260616-GE-100d.md](./08_TICKET-20260616-GE-100d.md) | diff-cover hook exits cleanly when the diff-cover tool or coverage artifact is absent | GE-100d | GE-100 |
| 09 | [09_TICKET-20260616-GE-100d-1.md](./09_TICKET-20260616-GE-100d-1.md) | diff-cover hook falls back through compare branch chain when origin/main is unavailable | GE-100d-1 | GE-100d |
| 10 | [10_TICKET-20260616-GE-100e.md](./10_TICKET-20260616-GE-100e.md) | diff-cover hook reports uncovered lines in changed files against the configured threshold | GE-100e | GE-100, GE-100d |
| 11 | [11_TICKET-20260616-GE-100e-1.md](./11_TICKET-20260616-GE-100e-1.md) | diff-cover hook blocks commit when strict mode is enabled and coverage is below threshold | GE-100e-1 | GE-100e |
| 12 | [12_TICKET-20260616-GE-100f.md](./12_TICKET-20260616-GE-100f.md) | diff-cover hook warns on stale coverage artifact and degrades gracefully in shallow clones | GE-100f | GE-100, GE-100e |
| 13 | [13_TICKET-20260616-GE-100f-1.md](./13_TICKET-20260616-GE-100f-1.md) | diff-cover hook uses HEAD~1 as fallback when all compare branches are unreachable in a shallow clone | GE-100f-1 | GE-100f |
| 14 | [14_TICKET-20260616-GE-100g.md](./14_TICKET-20260616-GE-100g.md) | Onboarding wizard offers opt-in enablement for jscpd and diff-cover hooks | GE-100g | GE-100, GE-100a |
| 15 | [15_TICKET-20260616-GE-100g-1.md](./15_TICKET-20260616-GE-100g-1.md) | Onboarding wizard offers diff-cover enablement following the same detect-then-prompt pattern | GE-100g-1 | GE-100g |
| 16 | [16_TICKET-20260616-GE-100h.md](./16_TICKET-20260616-GE-100h.md) | Both hooks ship disabled in commit_guardian.json with correct hooks_manifest entries | GE-100h | GE-100 |
| 17 | [17_TICKET-20260616-GE-100h-1.md](./17_TICKET-20260616-GE-100h-1.md) | Both hooks ship disabled by default and are not emitted to .pre-commit-config.yaml until enabled | GE-100h-1 | GE-100h |

## Dependencies

```
GE-100a (no dependencies)
GE-100a-1 -> GE-100a
GE-100a-2 -> GE-100a
GE-100b -> GE-100a
GE-100b-1 -> GE-100b
GE-100c -> GE-100b
GE-100c-1 -> GE-100c
GE-100d (no dependencies)
GE-100d-1 -> GE-100d
GE-100e -> GE-100d
GE-100e-1 -> GE-100e
GE-100f -> GE-100e
GE-100f-1 -> GE-100f
GE-100g -> GE-100a
GE-100g-1 -> GE-100g
GE-100h (no dependencies)
GE-100h-1 -> GE-100h
```

## Agent Assignments

| Agent | Tickets |
|-------|---------|
| commit | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16, 17 |
| pr-reviewer | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16, 17 |
| pull-request | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16, 17 |
| python-coder | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16, 17 |
| test-runner | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16, 17 |
| test-writer | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16, 17 |

