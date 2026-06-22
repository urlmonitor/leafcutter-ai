---
title: "Apostrophes and quote characters in the goal title are stripped before PascalCasing the epic folder name"
status: todo
source_ac: ACD-1200a-3-ii
components:
  - ac-driven-dev
created: 2026-06-22
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - scripts/goal_to_epic.py
agents:
  python-coder: needed
  test-writer: needed
  test-runner: needed
  sql-coder: not_needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# Apostrophes and quote characters in the goal title are stripped before PascalCasing the epic folder name

## Actor / Goal

As the leafcutter-ai system, I want apostrophes and quote characters in a goal
title stripped in-place before the title is PascalCased into an epic folder
name, so that goals like "Validate user's API inputs" yield a clean
`EPIC-ValidateUsersApiInputs` instead of a broken name containing a literal
quote or a split word.

## Context

This ticket implements AC store entry `ACD-1200a-3-ii` (component
`ac-driven-dev`, assigned `python-coder`, complexity S). It fixes defect #3 of
the `goal_to_epic.py` known-quirks set: epic-name derivation PascalCases the
goal title but mishandles apostrophes / quote characters, producing broken
folder names. Length-based truncation was already handled separately by
ACD-1200a-6; this ticket closes the apostrophe gap left open by ACD-1200a-3's
"no special characters" requirement.

Part of EPIC-GoalToEpicBugfixes. Independent of tickets 01/02, but edits the
same `goal_to_epic.py`, so the supervisor serializes it under the files-touched
gate.

## AC References

- Implements ACD-1200a-3-ii (apostrophe/quote stripping in epic-name derivation)

## Acceptance Criteria

```gherkin
Given the AC store contains goal ACD-070 (level: L0) with a title
  containing an ASCII apostrophe: "Validate user's API inputs",
And ACD-070 has leaf ACs beneath it,
When the system derives the epic folder name from that title,
Then the apostrophe is stripped entirely (not replaced with a space,
  a separator, or a placeholder character),
And the derived folder is named exactly EPIC-ValidateUsersApiInputs
  (the segment "user's" becomes "Users", NOT "User's", "User-s",
  "User_s", "Users " or two separate words "User" + "S"),
And the resulting folder name contains no literal apostrophe, quote,
  backtick, or truncated/empty path segment.

Given a second goal ACD-071 (level: L0) whose title contains the
  typographic / curly apostrophe U+2019: "Reject malformed customer’s payloads",
When the system derives the epic folder name from that title,
Then the curly apostrophe U+2019 is stripped entirely, identically to
  the ASCII apostrophe U+0027,
And the derived folder is named exactly EPIC-RejectMalformedCustomersPayloads
  (the segment "customer’s" becomes "Customers"),
And the same stripping rule applies to the ASCII single quote (U+0027),
  the curly apostrophe (U+2019), the double quote (U+0022), and the
  backtick (U+0060): each is removed in-place with no separator inserted,
  so adjacent letters join into a single PascalCase word.
```

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| ACD-1200a-3-ii | | | |

## Comments

## Sign-offs

- [ ] python-coder
- [ ] test-writer
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Implementation Tasks

- [ ] Strip apostrophe/quote characters (U+0027, U+0022, U+0060, U+2019) in-place — zero-width deletion — BEFORE splitting the title into words, so a quote embedded mid-word does not create a word boundary. Do NOT extend the word-split set `[\s\-_]+` to include quote characters.
- [ ] Handle straight and curly forms identically; keep the rule deterministic and consistent with ACD-1200a-3's PascalCase / no-special-characters requirement.
- [ ] Guard against producing an empty/whitespace-only segment, a leading/trailing separator, or a literal quote in the name.
- [ ] Tests for: ASCII apostrophe, curly U+2019, double quote, backtick; idempotency of repeated derivation.

## Risk & Safety

- Touches money? No.
- Touches data? No — string derivation only.
- Reversibility? High — behavior-only change to a generator script.
