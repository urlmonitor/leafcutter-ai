---
title: "EPIC-SuppressionNarrowsNeverDisables — narrowing a security check never switches it off"
epic_name: EPIC-SuppressionNarrowsNeverDisables
created: 2026-08-31
status: in_progress
type: epic
depends_on: []
requires_diagram: false
requires_adr: false
change_target:
  - code
  - prompt
  - docs
risk_surface: contract_boundary
components:
  - commit_guardian
  - security_scanner
source_ac: GE-123
---
# EPIC-SuppressionNarrowsNeverDisables

## Goal

This epic implements AC GE-123: Trust that the last check between you and a leaked credential is still on. It consists of 27 ticket(s) generated from the leaf ACs beneath GE-123, assembled in topological build order with all inter-ticket dependencies derived from the AC depends_on graph.

## Tickets

| # | File | Title | Source AC | Depends On |
|---|------|-------|-----------|------------|
| 01 | [01_TICKET-20260831-GE-123a-1.md](./01_TICKET-20260831-GE-123a-1.md) | A file recognised by its sensitive filename is also read line by line for its contents | GE-123a-1 | — |
| 02 | [02_TICKET-20260831-GE-123a-1-i.md](./02_TICKET-20260831-GE-123a-1-i.md) | Every sensitively-named file in the same run is read, not just the first one, and no finding is lost between the per-file scan and the run's report | GE-123a-1-i | — |
| 03 | [03_TICKET-20260831-GE-123a-2.md](./03_TICKET-20260831-GE-123a-2.md) | Suppressing the filename finding leaves every content finding in that file reported | GE-123a-2 | 01_TICKET-20260831-GE-123a-1.md |
| 04 | [04_TICKET-20260831-GE-123a-3.md](./04_TICKET-20260831-GE-123a-3.md) | A file whose name marks it as sensitive is still reported for its name — de-privileging the name signal must not delete it | GE-123a-3 | — |
| 05 | [05_TICKET-20260831-GE-123a-4.md](./05_TICKET-20260831-GE-123a-4.md) | The reference says that recognising a file by its name adds to the checking rather than ending it | GE-123a-4 | — |
| 06 | [06_TICKET-20260831-GE-123b-1.md](./06_TICKET-20260831-GE-123b-1.md) | A suppression that would leave a file with no rule able to report is refused for that file | GE-123b-1 | — |
| 07 | [07_TICKET-20260831-GE-123b-1-i.md](./07_TICKET-20260831-GE-123b-1-i.md) | The author is told which line was declined and which file it would have left unprotected, without the commit being stopped | GE-123b-1-i | — |
| 08 | [08_TICKET-20260831-GE-123b-2.md](./08_TICKET-20260831-GE-123b-2.md) | One allowlist line cannot silence every file in the repository | GE-123b-2 | 06_TICKET-20260831-GE-123b-1.md |
| 09 | [09_TICKET-20260831-GE-123b-3.md](./09_TICKET-20260831-GE-123b-3.md) | A file with nothing to report has not lost its coverage, and is not treated as though it had | GE-123b-3 | 06_TICKET-20260831-GE-123b-1.md |
| 10 | [10_TICKET-20260831-GE-123b-4.md](./10_TICKET-20260831-GE-123b-4.md) | The guarantee holds however many lines the author spreads the suppression across | GE-123b-4 | 06_TICKET-20260831-GE-123b-1.md |
| 11 | [11_TICKET-20260831-GE-123b-5.md](./11_TICKET-20260831-GE-123b-5.md) | The reference says when a suppression is declined, what it is judged against, and what the author will see | GE-123b-5 | — |
| 12 | [12_TICKET-20260831-GE-123c-1.md](./12_TICKET-20260831-GE-123c-1.md) | A suppression whose line-number field is not a line number is reported instead of being loaded as a rule that can never fire | GE-123c-1 | — |
| 13 | [13_TICKET-20260831-GE-123c-1-i.md](./13_TICKET-20260831-GE-123c-1-i.md) | An entry carrying a fourth field, including a Windows drive letter, is caught by the same unmatchable-entry rule | GE-123c-1-i | — |
| 14 | [14_TICKET-20260831-GE-123c-2.md](./14_TICKET-20260831-GE-123c-2.md) | A note written after a two-field suppression is reported rather than absorbed into the file path it follows | GE-123c-2 | — |
| 15 | [15_TICKET-20260831-GE-123c-2-i.md](./15_TICKET-20260831-GE-123c-2-i.md) | A suppression naming a rule the scanner cannot report is told so, instead of waiting silently for a finding that will never arrive | GE-123c-2-i | — |
| 16 | [16_TICKET-20260831-GE-123c-3.md](./16_TICKET-20260831-GE-123c-3.md) | The author is told about an unmatchable entry on the real commit path, in the one warning shape this file already uses, and the commit still proceeds | GE-123c-3 | 12_TICKET-20260831-GE-123c-1.md, 14_TICKET-20260831-GE-123c-2.md |
| 17 | [17_TICKET-20260831-GE-123c-3-i.md](./17_TICKET-20260831-GE-123c-3-i.md) | The repository's own live suppressions produce no warning and continue to suppress exactly what they suppress today | GE-123c-3-i | — |
| 18 | [18_TICKET-20260831-GE-123c-3-ii.md](./18_TICKET-20260831-GE-123c-3-ii.md) | A suppression that could have matched but had nothing to match this time is left alone | GE-123c-3-ii | — |
| 19 | [19_TICKET-20260831-GE-123c-4.md](./19_TICKET-20260831-GE-123c-4.md) | Someone writing their first suppression can find out how to write one instead of copying a neighbouring line | GE-123c-4 | 16_TICKET-20260831-GE-123c-3.md |
| 20 | [20_TICKET-20260831-GE-123c-5.md](./20_TICKET-20260831-GE-123c-5.md) | The document that lists the accepted suppression forms also says what is rejected and why | GE-123c-5 | 16_TICKET-20260831-GE-123c-3.md |
| 21 | [21_TICKET-20260831-GE-123d-1.md](./21_TICKET-20260831-GE-123d-1.md) | A quoted value that names a file is not read as a credential, in any file | GE-123d-1 | — |
| 22 | [22_TICKET-20260831-GE-123d-2.md](./22_TICKET-20260831-GE-123d-2.md) | In a named prose location, a credential-shaped line whose value is recognisably not a credential is not reported | GE-123d-2 | — |
| 23 | [23_TICKET-20260831-GE-123d-3.md](./23_TICKET-20260831-GE-123d-3.md) | A real credential written into a ticket or a requirement is still caught and still blocks | GE-123d-3 | — |
| 24 | [24_TICKET-20260831-GE-123d-4.md](./24_TICKET-20260831-GE-123d-4.md) | Source, configuration and any location not on the list never inherit the exemption | GE-123d-4 | — |
| 25 | [25_TICKET-20260831-GE-123d-4-i.md](./25_TICKET-20260831-GE-123d-4-i.md) | An executable script inside a prose location does not inherit the exemption | GE-123d-4-i | — |
| 26 | [26_TICKET-20260831-GE-123d-4-ii.md](./26_TICKET-20260831-GE-123d-4-ii.md) | The reference states where the exemption applies, in one place, as a closed list | GE-123d-4-ii | — |
| 27 | [27_TICKET-20260831-GE-123d-5.md](./27_TICKET-20260831-GE-123d-5.md) | Every exemption granted is announced, and the announcement never echoes the value | GE-123d-5 | — |

## Dependencies

```
GE-123a-1 (no dependencies)
GE-123a-1-i -> GE-123a-1
GE-123a-2 -> GE-123a-1
GE-123a-3 (no dependencies)
GE-123a-4 (no dependencies)
GE-123b-1 (no dependencies)
GE-123b-1-i -> GE-123b-1
GE-123b-2 -> GE-123b-1
GE-123b-3 -> GE-123b-1
GE-123b-4 -> GE-123b-1
GE-123b-5 (no dependencies)
GE-123c-1 (no dependencies)
GE-123c-1-i -> GE-123c-1
GE-123c-2 (no dependencies)
GE-123c-2-i -> GE-123c-2
GE-123c-3 -> GE-123c-1, GE-123c-2
GE-123c-3-i -> GE-123c-3
GE-123c-3-ii -> GE-123c-3
GE-123c-4 -> GE-123c-3
GE-123c-5 -> GE-123c-3
GE-123d-1 (no dependencies)
GE-123d-2 (no dependencies)
GE-123d-3 (no dependencies)
GE-123d-4 (no dependencies)
GE-123d-4-i -> GE-123d-4
GE-123d-4-ii -> GE-123d-4
GE-123d-5 (no dependencies)
```

## Agent Assignments

| Agent | Tickets |
|-------|---------|
| ac-fulfillment-gate | 01, 02, 03, 04, 06, 07, 08, 09, 10, 12, 13, 14, 15, 16, 17, 18, 21, 22, 23, 24, 25, 27 |
| ac-validator | 01, 02, 03, 04, 06, 07, 08, 09, 10, 12, 13, 14, 15, 16, 17, 18, 21, 22, 23, 24, 25, 27 |
| architect-review | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16, 17, 18, 20, 21, 22, 23, 24, 25, 26, 27 |
| commit | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27 |
| documentation-expert | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27 |
| documentation-verifier | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27 |
| llm-expert | 05, 11, 20, 26 |
| pr-reviewer | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27 |
| pull-request | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27 |
| python-coder | 01, 02, 03, 04, 06, 07, 08, 09, 10, 12, 13, 14, 15, 16, 17, 18, 21, 22, 23, 24, 25, 27 |
| test-runner | 01, 02, 03, 04, 06, 07, 08, 09, 10, 12, 13, 14, 15, 16, 17, 18, 21, 22, 23, 24, 25, 26, 27 |
| test-writer | 01, 02, 03, 04, 06, 07, 08, 09, 10, 12, 13, 14, 15, 16, 17, 18, 21, 22, 23, 24, 25, 26, 27 |

