---
epic_name: EPIC-TrustworthyTestGate
created: 2026-06-24
status: in_progress
components:
  - testing-quality
source_ac: TQ-100
---
# EPIC-TrustworthyTestGate

## Goal

This epic implements AC TQ-100: Your test suite only blocks main for failures that actually matter. It consists of 25 ticket(s) generated from the leaf ACs beneath TQ-100, assembled in topological build order with all inter-ticket dependencies derived from the AC depends_on graph.

## Tickets

| # | File | Title | Source AC | Depends On |
|---|------|-------|-----------|------------|
| 01 | [01_TICKET-20260624-TQ-100a-1.md](./01_TICKET-20260624-TQ-100a-1.md) | The suite runs every loadable test even when one file fails to load | TQ-100a-1 | TQ-100a |
| 02 | [02_TICKET-20260624-TQ-100a-1-i.md](./02_TICKET-20260624-TQ-100a-1-i.md) | A test file importing a nonexistent module does not stop the other files | TQ-100a-1-i | TQ-100a-1 |
| 03 | [03_TICKET-20260624-TQ-100a-1-ii.md](./03_TICKET-20260624-TQ-100a-1-ii.md) | A test file that raises at module scope does not stop the other files | TQ-100a-1-ii | TQ-100a-1 |
| 04 | [04_TICKET-20260624-TQ-100a-1-iii.md](./04_TICKET-20260624-TQ-100a-1-iii.md) | Collection isolation still surfaces genuine failures among the loadable tests | TQ-100a-1-iii | TQ-100a-1 |
| 05 | [05_TICKET-20260624-TQ-100b-1.md](./05_TICKET-20260624-TQ-100b-1.md) | A test linked to a not-done AC runs informationally and never fails the run | TQ-100b-1 | TQ-100b |
| 06 | [06_TICKET-20260624-TQ-100b-1-ii.md](./06_TICKET-20260624-TQ-100b-1-ii.md) | A test tagged with an AC id absent from the store is enforced, not silently skipped | TQ-100b-1-ii | TQ-100b-1 |
| 07 | [07_TICKET-20260624-TQ-100b-1-iii.md](./07_TICKET-20260624-TQ-100b-1-iii.md) | The AC store is read once per session and the enforced set is stable across repeated runs | TQ-100b-1-iii | TQ-100b-1 |
| 08 | [08_TICKET-20260624-TQ-100b-2.md](./08_TICKET-20260624-TQ-100b-2.md) | A test linked to a done AC is enforced and its failure fails the run | TQ-100b-2 | TQ-100b |
| 09 | [09_TICKET-20260624-TQ-100b-1-i.md](./09_TICKET-20260624-TQ-100b-1-i.md) | When its AC flips to done, the same test transitions from informational to enforced with no test edit | TQ-100b-1-i | TQ-100b-1, TQ-100b-2 |
| 10 | [10_TICKET-20260624-TQ-100b-3.md](./10_TICKET-20260624-TQ-100b-3.md) | State diagram of a tagged test's informational-to-enforced lifecycle | TQ-100b-3 | TQ-100b, TQ-100b-1, TQ-100b-2 |
| 11 | [11_TICKET-20260624-TQ-100c-1.md](./11_TICKET-20260624-TQ-100c-1.md) | A test with no covers tag is enforced by default, requiring no backfill | TQ-100c-1 | TQ-100c |
| 12 | [12_TICKET-20260624-TQ-100c-1-i.md](./12_TICKET-20260624-TQ-100c-1-i.md) | Removing a covers tag makes a test unlinked-and-enforced, not informational | TQ-100c-1-i | TQ-100c-1 |
| 13 | [13_TICKET-20260624-TQ-100c-2.md](./13_TICKET-20260624-TQ-100c-2.md) | A done-AC test has no in-test path to downgrade itself to informational | TQ-100c-2 | TQ-100c |
| 14 | [14_TICKET-20260624-TQ-100c-2-i.md](./14_TICKET-20260624-TQ-100c-2-i.md) | An AC marked done with zero covering tests is flagged by the integrity check | TQ-100c-2-i | TQ-100c-2 |
| 15 | [15_TICKET-20260624-TQ-100c-2-ii.md](./15_TICKET-20260624-TQ-100c-2-ii.md) | Downgrading an AC from done to not-done while its test is failing is flagged, not silently relaxed | TQ-100c-2-ii | TQ-100c-2 |
| 16 | [16_TICKET-20260624-TQ-100d-1.md](./16_TICKET-20260624-TQ-100d-1.md) | A failing test on a valid, unexpired allowlist entry does not block the run | TQ-100d-1 | TQ-100d |
| 17 | [17_TICKET-20260624-TQ-100d-1-i.md](./17_TICKET-20260624-TQ-100d-1-i.md) | An allowlist entry whose expiry date has passed is flagged and fails the check | TQ-100d-1-i | TQ-100d-1 |
| 18 | [18_TICKET-20260624-TQ-100d-1-ii.md](./18_TICKET-20260624-TQ-100d-1-ii.md) | An allowlisted test that has started passing is flagged so the stale entry is removed | TQ-100d-1-ii | TQ-100d-1 |
| 19 | [19_TICKET-20260624-TQ-100d-1-iii.md](./19_TICKET-20260624-TQ-100d-1-iii.md) | An allowlist entry missing its ticket reference or expiry date is rejected | TQ-100d-1-iii | TQ-100d-1 |
| 20 | [20_TICKET-20260624-TQ-100d-2.md](./20_TICKET-20260624-TQ-100d-2.md) | State diagram of an allowlist entry's added-tracked-flagged lifecycle | TQ-100d-2 | TQ-100d, TQ-100d-1 |
| 21 | [21_TICKET-20260624-TQ-100e-1.md](./21_TICKET-20260624-TQ-100e-1.md) | Enforcement mode is one of three values selected by explicit configuration | TQ-100e-1 | TQ-100e |
| 22 | [22_TICKET-20260624-TQ-100e-1-i.md](./22_TICKET-20260624-TQ-100e-1-i.md) | Report-only mode surfaces results but never fails the run | TQ-100e-1-i | TQ-100e-1 |
| 23 | [23_TICKET-20260624-TQ-100e-1-ii.md](./23_TICKET-20260624-TQ-100e-1-ii.md) | With no explicit config, enforcement defaults to the safe non-blocking mode | TQ-100e-1-ii | TQ-100e-1 |
| 24 | [24_TICKET-20260624-TQ-100e-1-iii.md](./24_TICKET-20260624-TQ-100e-1-iii.md) | Switching enforcement modes changes behavior with no edits to any test | TQ-100e-1-iii | TQ-100e-1 |
| 25 | [25_TICKET-20260624-TQ-100e-2.md](./25_TICKET-20260624-TQ-100e-2.md) | Reference doc for the enforcement rollout stages and their controlling configuration | TQ-100e-2 | TQ-100e, TQ-100e-1 |

## Dependencies

```
TQ-100a-1 (no dependencies)
TQ-100a-1-i -> TQ-100a-1
TQ-100a-1-ii -> TQ-100a-1
TQ-100a-1-iii -> TQ-100a-1
TQ-100b-1 (no dependencies)
TQ-100b-1-i -> TQ-100b-1, TQ-100b-2
TQ-100b-1-ii -> TQ-100b-1
TQ-100b-1-iii -> TQ-100b-1
TQ-100b-2 (no dependencies)
TQ-100b-3 -> TQ-100b-1, TQ-100b-2
TQ-100c-1 (no dependencies)
TQ-100c-1-i -> TQ-100c-1
TQ-100c-2 (no dependencies)
TQ-100c-2-i -> TQ-100c-2
TQ-100c-2-ii -> TQ-100c-2
TQ-100d-1 (no dependencies)
TQ-100d-1-i -> TQ-100d-1
TQ-100d-1-ii -> TQ-100d-1
TQ-100d-1-iii -> TQ-100d-1
TQ-100d-2 -> TQ-100d-1
TQ-100e-1 (no dependencies)
TQ-100e-1-i -> TQ-100e-1
TQ-100e-1-ii -> TQ-100e-1
TQ-100e-1-iii -> TQ-100e-1
TQ-100e-2 -> TQ-100e-1
```

## Agent Assignments

| Agent | Tickets |
|-------|---------|
| architecture-diagram-author | 10, 20 |
| commit | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25 |
| pr-reviewer | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25 |
| pull-request | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25 |
| python-coder | 01, 02, 03, 04, 05, 06, 07, 08, 09, 11, 12, 13, 14, 15, 16, 17, 18, 19, 21, 22, 23, 24 |
| reference-author | 25 |
| test-runner | 01, 02, 03, 04, 05, 06, 07, 08, 09, 11, 12, 13, 14, 15, 16, 17, 18, 19, 21, 22, 23, 24 |
| test-writer | 01, 02, 03, 04, 05, 06, 07, 08, 09, 11, 12, 13, 14, 15, 16, 17, 18, 19, 21, 22, 23, 24 |

