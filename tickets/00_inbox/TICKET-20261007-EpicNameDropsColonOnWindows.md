---
title: "Derived epic names keep only letters and digits, so a title with ':' builds on Windows"
status: todo
components:
  - ac_driven_dev
created: 2026-10-07
depends_on: []
priority: medium
requires_diagram: false
requires_adr: false
change_target: code
risk_surface: internal
roadmap_phase: phase_1
advances_current_outcome: true
tags:
  - epic-generation
  - windows
  - portability
  - naming
last_updated: 2026-10-07
files_touched:
  - scripts/ac_store/epic_naming.py
  - unit_tests/ac_store/test_epic_name_path_safe.py  # new
  - unit_tests/ac_store/test_master_plan_frontmatter_gates.py
agents:
  architect-review: not_needed
  test-writer: needed
  python-coder: needed
  llm-expert: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  status-checker: not_needed
---

# Derived epic names keep only letters and digits, so a title with ':' builds on Windows

## Actor / Goal
In order that `goal_to_epic` can build an epic from any AC title, on any OS, we need the derived
epic name to contain only ASCII letters and digits. Then `EPIC-<name>` is always a valid, single
folder name.

## Context
- **Cause.** `_derive_epic_name` (`scripts/ac_store/epic_naming.py:302-343`) returns
  `_to_pascal_case(title)` when it is 40 characters or less (:332-335). Otherwise it returns the LLM
  summary, which is validated against `^[A-Za-z][A-Za-z0-9]{0,39}$` (:245), or a truncation of the
  naive name (:343).
- `_to_pascal_case` (:123-174):
  - strips quote characters (:163);
  - turns non-ASCII punctuation into spaces (:164, `_normalize_non_ascii_punct` at :84);
  - then splits only on whitespace, `-` and `_` (:173).
  So ASCII punctuation passes through. Its idempotence guard (:171) also returns any single token
  that starts with a capital unchanged, punctuation included.
- **Probe (2026-10-07).**
  - `'Ship parts: the "fast" path'` → `'ShipParts:TheFastPath'`
  - `'read/write split'` → `'Read/writeSplit'`
  - `'why? because'` → `'Why?Because'`
  - `'a<b>c|d*e'` → `'A<b>c|d*e'`
  - `'trailing dot.'` → `'TrailingDot.'`
- **Effect.** `epic_pipeline.py` builds `EPIC-{epic_name}` (:112, :119 and :226). On Windows,
  `build_epic_from_ids` then fails to create the folder with WinError 267, because `:` is not
  allowed in a Windows file name. A `/` creates a nested folder on every OS.
- **A test works around it.** `unit_tests/ac_store/test_master_plan_frontmatter_gates.py::test_title_with_colon_round_trips`
  (EPIC-BuildToolingRunsThrough ticket 09, branch `feature/build-tooling-generators`, commit
  7a96c3f8a) patches `epic_pipeline._derive_epic_name` to return `"ShipParts"`. Its `_generate`
  helper (:123-126) says: "_derive_epic_name keeps ':' from a title, which Windows cannot create as a
  directory (separate defect, out of scope here)".
- **Related AC.** ACD-1200a-3-iii (`todo`) promises an ASCII-safe slug. The note for its
  implementation says the derived folder name "contains only ASCII alphanumeric characters"
  (`scripts/goal_to_epic.py:406-410`), but only non-ASCII punctuation was handled.
- **Size.** `epic_naming.py` has 389 raw lines; check-file-size measures 145 of the 400 allowed
  (2026-10-07).

## Acceptance Criteria
- [ ] AC-1: For any title, `_derive_epic_name` returns a non-empty name of ASCII letters and digits only, starting with a letter: the pattern the LLM path already enforces at :245. ASCII punctuation, including `: / \ * ? " < > | .`, is a word boundary, like non-ASCII punctuation.
- [ ] AC-2: `'Ship parts: the "fast" path'` gives `ShipPartsTheFastPath`, and `'read/write split'` gives `ReadWriteSplit`.
- [ ] AC-3: An already PascalCase name is still returned unchanged (dry-run / real-run parity, ACD-1200a-3-iii). A single token with punctuation is cleaned: `ShipParts:Fast` gives `ShipPartsFast`.
- [ ] AC-4: A title with no letters or digits gives a fixed fallback name, never an empty one, and the run logs that it used the fallback.
- [ ] AC-5: Through the real `goal_to_epic.build_epic_from_ids`, a temporary store whose first AC title contains `:` creates `EPIC-<letters and digits>`, without patching `_derive_epic_name`, on Windows and on Linux.
- [ ] AC-6: The existing naming tests stay green: `unit_tests/ac_driven_dev/test_acd_1200a_3_iii.py`, `unit_tests/ac_store/test_concise_epic_name.py`, `tests/test_goal_to_epic_apostrophe.py` and `tests/test_goal_to_epic_basename_collision.py`.

## Test Requirements

```yaml
tests:
  - name: test_derived_epic_name_is_letters_and_digits_only
    location: unit_tests/ac_store/test_epic_name_path_safe.py
    type: unit
    covers: [AC-1, AC-2, AC-3, AC-4]
    description: |
      Run _derive_epic_name over the probe titles in Context, a single token with ':', an already
      PascalCase name, and a title of punctuation only. Every result matches
      ^[A-Za-z][A-Za-z0-9]*$; the named examples give the names in AC-2 and AC-3; the punctuation-only
      title gives the fallback. Red today.
  - name: test_epic_folder_for_a_title_with_a_colon_is_created
    location: unit_tests/ac_store/test_epic_name_path_safe.py
    type: integration
    covers: [AC-5]
    description: |
      Temporary store; the first AC's title is 'Ship parts: the "fast" path'. Call the real
      build_epic_from_ids with no patch on the name. The EPIC folder exists and its name after
      "EPIC-" is letters and digits only. Red on Windows today (WinError 267); on Linux the folder
      is created but its name contains ':', so the name assertion is red there too.
```

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | test_derived_epic_name_is_letters_and_digits_only | | |
| AC-2 | test_derived_epic_name_is_letters_and_digits_only | | |
| AC-3 | test_derived_epic_name_is_letters_and_digits_only | | |
| AC-4 | test_derived_epic_name_is_letters_and_digits_only | | |
| AC-5 | test_epic_folder_for_a_title_with_a_colon_is_created | | |
| AC-6 | (existing tests) | | |

## Comments

_(Append-only log — leave blank when authoring.)_

## Implementation Tasks

### test-writer
- [ ] Write `unit_tests/ac_store/test_epic_name_path_safe.py`.

### python-coder
- [ ] `_to_pascal_case` (123-174): treat ASCII punctuation as a word boundary, and make the idempotence
  guard (171) apply only to a token of letters and digits. Add the fallback for an empty result.
- [ ] Add a DECISION HISTORY entry naming ACD-1200a-3-iii.
- [ ] Once ticket 09 has merged, remove the `epic_name` patch from `_generate` in
  `unit_tests/ac_store/test_master_plan_frontmatter_gates.py` (:123-126), so
  `test_title_with_colon_round_trips` runs through the real name.

### test-runner / pr-reviewer / commit
- [ ] Run the new file and the AC-6 tests.

## Risk & Safety
- Touches money? No.
- Touches data? Names of newly generated epic folders only. Existing folders are not renamed.
- Reversibility: revert the commit.

## Out of Scope
- The Master_Plan `title`, which keeps the original text, quoting included (ticket 09).
- Ticket file names; they are built from AC ids.
