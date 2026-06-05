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
  architect-review: needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
  test-writer: needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
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

- [ ] architect-review
- [ ] test-writer
- [ ] python-coder
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

### architect-review

- [ ] Read `templates/skills/ticket-prioritizer/scripts/prioritize.py` to
  understand its current CLI and JSON schema.
- [ ] Confirm the complexity-to-priority mapping (S→high, M→medium, L/XL→low)
  is consistent with how `estimated_complexity` values appear in the AC store
  (sample 10 ACs to verify the enum values used).
- [ ] Approve the `--include-acs` flag design: confirm it is backward-compatible
  and does not alter the output format when absent.

### test-writer

- [ ] Write `tests/ac_store/test_ac_prioritizer.py`:
  - `test_merged_list_contains_both_sources`: mock both scan and prioritize
    outputs; assert merged output has correct counts and source fields.
  - `test_deduplication_suppresses_ac`: mock AC ready list containing
    ACS-100a-1; mock ticket list with source_ac: ACS-100a-1; assert AC absent.
  - `test_complexity_mapping_S_to_high`: assert S maps to high priority.
  - `test_missing_scan_script_exits_1`: mock missing scan_ac_store.py; assert exit 1.
- [ ] Write `tests/test_prioritize_ac_integration.py`:
  - `test_include_acs_flag_off_by_default`: run prioritize.py without flag;
    assert source field absent or all entries are ticket.
  - `test_include_acs_flag_produces_merged_output`: run with --include-acs;
    assert ac entries present.

### python-coder

- [ ] Implement `scripts/ac_store/ac_prioritizer.py`:
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
- [ ] Modify `templates/skills/ticket-prioritizer/scripts/prioritize.py`:
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
