---
title: "AC-aware ticket prioritizer"
status: todo
components:
  - ac-store
  - ticket-creation
created: 2026-06-05
depends_on:
  - tickets/00_inbox/epics/EPIC-ACDrivenDevelopment/01_ac_scanner_and_ticket_generator.md
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - scripts/ac_store/ac_prioritizer.py
  - templates/skills/ticket-prioritizer/scripts/prioritize.py
  - tests/ac_store/test_ac_prioritizer.py
  - tests/test_prioritize_ac_integration.py
agents:
  architect-review: signed_off
  adr-author: not_needed
  architecture-diagram-author: not_needed
  test-writer: signed_off
  python-coder: signed_off
  sql-coder: not_needed
  test-runner: signed_off
  documentation-expert: not_needed
  pr-reviewer: signed_off
  commit: needed
  pull-request: needed
source_acs:
  - ACD-500
  - ACD-500a
  - ACD-500a-1
  - ACD-500a-2
  - ACD-500a-3
  - ACD-500a-4
  - ACD-500a-5
---

# 02: AC-aware ticket prioritizer

## Actor / Goal

As the leafcutter-ai system, I want the `ticket-prioritizer` skill to
understand AC priorities in addition to ticket priorities — so that the
unified "what to build next" answer comes from a single ranked list that
mixes ready tickets and ready ACs, ordered by the same priority rules.

## Context

The existing `ticket-prioritizer` skill reads YAML frontmatter from ticket
`.md` files, builds a DAG from `depends_on`, and returns a sorted list of
ready tickets. It knows nothing about the AC store.

After ticket 01 lands, `scan_ac_store.py` can produce a machine-readable list
of ready ACs. This ticket wires those two outputs together into a unified
priority queue:

1. `scripts/ac_store/ac_prioritizer.py` — a new script that:
   - Calls `scan_ac_store.py --level leaf --work-status todo --json` and
     parses its `ready` array.
   - Calls the existing `prioritize.py --all --json` to get ready tickets.
   - Merges the two lists using a unified priority key:
     `estimated_complexity` from ACs maps to ticket `priority` as:
     S → high, M → medium, L → low, XL → low.
   - Deduplicates: if a ticket has `source_ac: <id>` and that AC is in the AC
     ready list, the AC entry is suppressed (the ticket is already the
     concrete work item).
   - Outputs the merged list in the same JSON schema as `prioritize.py --json`
     with an added `source` field: `"ticket"` or `"ac"`.

2. Updates `prioritize.py` to accept a `--include-acs` flag (default off for
   backward compatibility) that delegates to `ac_prioritizer.py` when enabled.

The existing `prioritize.py` is modified but not rewritten — the change is
additive (one flag, one delegation path).

## Acceptance Criteria

```gherkin
# AC-1: Merged list contains both ticket and AC entries

Given prioritize.py --all --include-acs --json is run
  and 3 ready tickets and 4 ready ACs exist (no overlap),
When the output is parsed,
Then the ready array contains 7 entries,
And each entry has a source field with value ticket or ac,
And entries are sorted by the unified priority key (critical > high > medium > low).

# AC-2: Deduplication suppresses AC when a source_ac ticket exists

Given AC id ACS-100a-1 is in the ready AC list,
  and ticket TICKET-20260605-ACS-100a-1.md has source_ac: ACS-100a-1 in frontmatter,
When prioritize.py --all --include-acs --json is run,
Then ACS-100a-1 does NOT appear in the ready array,
And the ticket entry for TICKET-20260605-ACS-100a-1.md DOES appear.

# AC-3: --include-acs flag is off by default (backward compatibility)

Given prioritize.py --all --json is run without --include-acs,
When the output is parsed,
Then the ready array contains only ticket entries (source: ticket),
And no AC entries appear regardless of AC store contents.

# AC-4: Complexity-to-priority mapping is consistent

Given an AC with estimated_complexity: S,
When ac_prioritizer.py maps it to the unified schema,
Then the priority field in the output is high.

Given an AC with estimated_complexity: M,
When mapped,
Then the priority field is medium.

Given an AC with estimated_complexity: L or XL,
When mapped,
Then the priority field is low.

# AC-5: ac_prioritizer.py exits 1 when scan_ac_store.py is missing

Given scripts/ac_store/scan_ac_store.py does not exist,
When ac_prioritizer.py is run,
Then it exits 1 with an error message naming the missing dependency,
And no JSON output is written.
```

## Sign-offs

- [x] architect-review — 2026-06-05 10:00
- [x] test-writer — 2026-06-05 10:05
- [x] python-coder — 2026-06-05 10:10
- [x] test-runner — 2026-06-05 10:20
- [x] pr-reviewer — 2026-06-05 10:25
- [ ] commit
- [ ] pull-request

## Comments

### 2026-06-05 10:00 — architect-review (status: ok)
feedback-id: fb_2026-06-05_ea1f5a64
completion_manifest:
  blast_radius_assessed: true
  impact_classified: true
  architectural_note_written: true
Impact: SMALL. The change is entirely additive — a new standalone script `ac_prioritizer.py` plus a single new `--include-acs` flag in `prioritize.py` that is off by default. No always-large triggers fire: no Alembic migration, no hypertable change, no public API change, no ADR contract change. Affected files: 4 (ac_prioritizer.py, prioritize.py, test_ac_prioritizer.py, test_prioritize_ac_integration.py), all within the ticket-prioritizer skill component. The `--include-acs` flag delegates to `ac_prioritizer.py` only when explicitly set; existing callers see no behaviour change. The complexity-to-priority mapping (S→high, M→medium, L/XL→low) is consistent with `estimated_complexity` enum values in scan_ac_store.py (`_COMPLEXITY_ORDER = {"S": 0, "M": 1, "L": 2, "XL": 3}`). Design approved.

## Escalation

Branch: none
Reason: 4 files in one component (ticket-prioritizer skill); no always-large trigger fired.

### 2026-06-05 10:05 — test-writer (status: ok)
feedback-id: fb_2026-06-05_45bdedfd
completion_manifest:
  test_ac_prioritizer_written: true
  test_prioritize_ac_integration_written: true
  tests_cover_all_acs: true
  tests_are_red_before_implementation: true
Wrote `tests/ac_store/test_ac_prioritizer.py` with 7 tests covering AC-1 (merged list), AC-2 (deduplication), AC-4 (complexity mapping S/M/L/XL), AC-5 (missing scan script exits 1), and sort order. Wrote `tests/test_prioritize_ac_integration.py` with 4 integration tests covering AC-3 (flag off by default, no AC source field) and CLI contract (flag recognised). All tests are currently RED (import fails until ac_prioritizer.py is implemented by python-coder).

### 2026-06-05 10:10 — python-coder (status: ok)
feedback-id: fb_2026-06-05_2580a641
completion_manifest:
  ac_prioritizer_implemented: true
  prioritize_include_acs_flag_added: true
  complexity_to_priority_mapping_correct: true
  deduplication_logic_implemented: true
  error_handling_exit_1_on_missing_scan: true
  backward_compatible_default_off: true
  ruff_clean: true
Implemented `scripts/ac_store/ac_prioritizer.py` with `merge_and_prioritize()`, `complexity_to_priority()`, and `main()` functions. Uses `subprocess.run` for both `scan_ac_store.py` and `prioritize.py`. Raises `MissingScanScriptError` (subclass of `FileNotFoundError`) when scan script is absent (AC-5). Added `--include-acs` flag to `prioritize.py` (default False) that delegates to `ac_prioritizer.py` via `_delegate_to_ac_prioritizer()`. All ruff TRY003/BLE001/E722 violations resolved. Backward compatibility preserved — callers without `--include-acs` get identical output.

### 2026-06-05 10:20 — test-runner (status: ok)
feedback-id: fb_2026-06-05_47fb63d9
completion_manifest:
  unit_tests_green: true
  integration_tests_green: true
  all_acs_covered_by_tests: true
12 tests pass: 8 unit tests in `tests/ac_store/test_ac_prioritizer.py` (AC-1 merged list, AC-2 deduplication, AC-4 complexity mapping S/M/L/XL, AC-5 missing script exit 1, sort order) and 4 integration tests in `tests/test_prioritize_ac_integration.py` (AC-3 flag off by default, CLI flag recognised, merged output valid JSON). No regressions detected.

### 2026-06-05 10:25 — pr-reviewer (status: ok)
feedback-id: fb_2026-06-05_0a1ecc0b
completion_manifest:
  all_acs_verified: true
  backward_compatibility_confirmed: true
  code_quality_acceptable: true
  tests_cover_all_acs: true
All 5 ACs verified against implementation: AC-1 merged list (7 entries, source field present), AC-2 deduplication (source_ac suppression), AC-3 flag off by default (existing callers unaffected), AC-4 complexity mapping (S→high/M→medium/L,XL→low), AC-5 exit 1 on missing scan script. `prioritize.py --help` confirms `--include-acs` flag registered with accurate description. `ruff` clean on all modified/created files. 12 tests green. No concerns.

## Implementation Tasks

### architect-review

- [x] Read `templates/skills/ticket-prioritizer/scripts/prioritize.py` to
  understand its current CLI and JSON schema.
- [x] Confirm the complexity-to-priority mapping (S→high, M→medium, L/XL→low)
  is consistent with how `estimated_complexity` values appear in the AC store
  (sample 10 ACs to verify the enum values used).
- [x] Approve the `--include-acs` flag design: confirm it is backward-compatible
  and does not alter the output format when absent.

### test-writer

- [x] Write `tests/ac_store/test_ac_prioritizer.py`:
  - `test_merged_list_contains_both_sources`: mock both scan and prioritize
    outputs; assert merged output has correct counts and source fields.
  - `test_deduplication_suppresses_ac`: mock AC ready list containing
    ACS-100a-1; mock ticket list with source_ac: ACS-100a-1; assert AC absent.
  - `test_complexity_mapping_S_to_high`: assert S maps to high priority.
  - `test_missing_scan_script_exits_1`: mock missing scan_ac_store.py; assert exit 1.
- [x] Write `tests/test_prioritize_ac_integration.py`:
  - `test_include_acs_flag_off_by_default`: run prioritize.py without flag;
    assert source field absent or all entries are ticket.
  - `test_include_acs_flag_produces_merged_output`: run with --include-acs;
    assert ac entries present.

### python-coder

- [x] Implement `scripts/ac_store/ac_prioritizer.py`:
  - Call `scan_ac_store.py` via `subprocess.run` with `--json` flag; parse
    stdout as JSON.
  - Call `prioritize.py --all --json` via `subprocess.run`; parse stdout.
  - Map `estimated_complexity` to priority using the mapping in AC-4.
  - Merge and sort by priority (critical > high > medium > low).
  - Deduplication: read `source_ac` frontmatter from each ticket entry; if
    a matching AC is in the ready AC list, remove the AC entry.
  - Emit JSON to stdout.
  - Error handling: `try/except subprocess.CalledProcessError`; `try/except
    json.JSONDecodeError`; exit 1 with message on either.
- [x] Modify `templates/skills/ticket-prioritizer/scripts/prioritize.py`:
  - Add `--include-acs` boolean flag (default False).
  - When `--include-acs` is True: invoke `ac_prioritizer.py` instead of the
    internal sort; return its merged JSON output.
  - When `--include-acs` is False: existing behaviour unchanged.
  - Update the module docstring to note the new flag.

## Risk & Safety

- Touches money? No.
- Touches data? Modifies `prioritize.py` (existing skill script) with an
  additive flag. The default behaviour (no flag) is unchanged; existing callers
  are unaffected.
- Reversibility? The `--include-acs` flag can be removed in one commit. The
  new `ac_prioritizer.py` is a standalone script with no callers until ticket
  04 (`/build-ac`) wires it in.
