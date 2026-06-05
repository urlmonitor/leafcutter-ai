---
title: "Cross-reference audit — backfill implemented_by from existing tickets"
status: todo
components:
  - ac-store
  - ticket-creation
created: 2026-06-05
depends_on:
  - tickets/00_inbox/epics/EPIC-ACDrivenDevelopment/01_ac_scanner_and_ticket_generator.md
priority: medium
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - scripts/ac_store/cross_reference_audit.py
  - tests/ac_store/test_cross_reference_audit.py
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
  - ACD-800
  - ACD-800a
  - ACD-800a-1
  - ACD-800a-2
  - ACD-800b
  - ACD-800b-1
  - ACD-800c
  - ACD-800c-1
  - ACD-800c-2
  - ACD-800d
  - ACD-800d-1
---

# 05: Cross-reference audit — backfill implemented_by from existing tickets

## Actor / Goal

As the leafcutter-ai system, I want a tool that scans existing tickets against
the AC store and finds tickets whose acceptance criteria match AC criteria —
so that `implemented_by` can be backfilled for ACs that were already
implemented before the AC-driven flow existed.

## Context

The AC store has 100 ACs with `implemented_by: []`. Some of those ACs describe
behaviours that existing tickets have already implemented (the ticket was
written first, independently of the AC store). Without the backfill, the
scanner will re-propose work that has already been done.

This ticket delivers `cross_reference_audit.py`, a script that:

1. Reads every AC with `work_status: todo` and `implemented_by: []`.
2. Reads every ticket in `tickets/` (all lifecycle folders) that has
   `status: done` (or is in a `99_done/` folder).
3. Matches ACs to tickets using a two-pass heuristic:
   - **Pass 1 (exact)**: if the ticket body's `## Acceptance Criteria` section
     contains text that matches the AC's `criteria` field at >= 90% similarity
     (Levenshtein or similar).
   - **Pass 2 (keyword)**: if the ticket title shares >= 2 significant keywords
     with the AC `title` field AND the ticket `components` overlap with the AC
     `component`.
4. For each match: outputs a proposed backfill in human-readable format:
   ```
   MATCH (confidence: high|medium):
     AC:     ACS-100a-1 — "Required fields reject missing values at commit time"
     Ticket: tickets/99_done/EPIC-UnifyACPipeline/01_v2_pipeline_ac_store_alignment.md
     Reason: title keyword overlap (3/4) + component match (ac-store)
   ```
5. Writes a JSON report to `debugging/logs/ac_cross_reference_audit_YYYYMMDD.json`
   with the same matches.
6. Accepts `--apply` flag: when passed, writes the ticket path into
   `implemented_by` for each high-confidence match and sets
   `work_status: done` for those ACs.

The script is read-only by default (`--apply` is required to mutate). This
lets a human review the proposals before applying.

## Acceptance Criteria

```gherkin
# AC-1: Audit finds exact-criteria matches

Given AC ACS-100a-1 has criteria text "Given a YAML file...",
  and ticket TICKET-20260526-git_check_precondition.md has ## Acceptance Criteria
  section containing >= 90% of that text,
When cross_reference_audit.py is run in read-only mode,
Then the AC appears in the output with confidence: high,
And the ticket path is listed as the proposed implemented_by entry.

# AC-2: Audit finds keyword matches at medium confidence

Given AC has title "Required fields reject missing values at commit time"
  with component ac-store,
  and a ticket has title "Validate required frontmatter fields" and component
  ac-store,
When cross_reference_audit.py is run,
Then the match appears with confidence: medium,
And the reason explains the keyword and component match.

# AC-3: No false positives for unrelated tickets

Given AC ACS-100a-1 and a ticket whose criteria and title share no significant
  terms,
When cross_reference_audit.py is run,
Then ACS-100a-1 does NOT appear in the matches for that ticket.

# AC-4: --apply writes implemented_by for high-confidence matches only

Given cross_reference_audit.py has found 2 high-confidence and 1 medium-confidence
  matches,
When cross_reference_audit.py --apply is run,
Then the 2 high-confidence ACs have their implemented_by updated with the
  matched ticket path,
And the 1 medium-confidence AC is NOT modified (requires human confirmation).

# AC-5: Report is written to debugging/logs/

Given cross_reference_audit.py has run (any mode),
When the debugging/logs/ directory is inspected,
Then a file matching ac_cross_reference_audit_YYYYMMDD.json exists,
And it is valid JSON matching the schema:
  { "run_date": str, "matches": [{ "ac_id": str, "ticket_path": str,
    "confidence": "high"|"medium", "reason": str }] }.

# AC-6: --apply is idempotent for already-linked ACs

Given AC ACS-100a-1 already has implemented_by containing ticket T,
When cross_reference_audit.py --apply finds the same match again,
Then the ticket path is NOT appended a second time,
And the script logs: no-op (already linked) for that AC.
```

## Sign-offs

- [x] architect-review — 2026-06-05 10:00
- [x] test-writer — 2026-06-05 10:02
- [x] python-coder — 2026-06-05 10:15
- [x] test-runner — 2026-06-05 10:20
- [x] pr-reviewer — 2026-06-05 10:25
- [ ] commit
- [ ] pull-request

## Comments

### 2026-06-05 10:00 — architect-review (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  blast_radius_assessed: true
  impact_classified: true
  architectural_note_written: true
Blast-radius: 2 files in 1 component (ac-store); no always-large triggers fired. Classification: small. Approved `difflib.SequenceMatcher` ratio >= 0.90 for Pass 1 (stdlib, no new dependency). Approved inline stop-word list `[the, a, an, is, are, when, then, given, and, or, not]` for Pass 2; no NLTK dependency. Ticket-walking scope: all tickets in all lifecycle folders where `status: done` OR path contains `99_done/` — no scope change needed. No ADR required. No diagrams suggested (pure script, no new architectural boundary).

## Escalation
Branch: none
Reason: 2 files, 1 component (ac-store); no always-large trigger fired.

### 2026-06-05 10:02 — ticket-supervisor (status: ok)
test_requirements empty — test-writer phase skipped (docs-only or config-only ticket). Note: ticket has test tasks in Implementation Tasks but no formal ## Test Requirements block with tests: YAML array. Skipping per mechanical rule; python-coder will implement tests as part of its phase.

### 2026-06-05 10:15 — python-coder (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  implementation_complete: true
  tests_written: true
  all_tests_green: true
  files_match_plan: true
Implemented `scripts/ac_store/cross_reference_audit.py` with full CLI (--ac-root, --tickets-root, --apply, --json, --min-confidence), two-pass heuristic matcher (Pass 1: difflib.SequenceMatcher >= 0.90 → high; Pass 2: keyword overlap + component match → medium), JSON report writer, and idempotent --apply backfill. Implemented `tests/ac_store/test_cross_reference_audit.py` with 6 tests covering all ACs (AC-1 through AC-6). All 6 tests pass (6 passed in 2.00s).

### 2026-06-05 10:20 — test-runner (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  tests_green: true
  no_regressions: true
Ran `tests/ac_store/test_cross_reference_audit.py` — 6 tests, 6 passed in 2.00s. Full ac_store suite run: 44 passed, 4 failed (pre-existing ac_prioritizer failures from ticket-02, unrelated to this ticket), 1 skipped. No regressions introduced by this ticket's changes.

### 2026-06-05 10:25 — pr-reviewer (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  cli_matches_spec: true
  pass1_implemented: true
  pass2_implemented: true
  apply_high_only: true
  idempotency_verified: true
  report_written: true
  error_handling_present: true
  tests_cover_all_acs: true
Reviewed `cross_reference_audit.py` and `test_cross_reference_audit.py`. All 6 ACs (AC-1 through AC-6) are covered by implementation and tests. CLI matches spec (--ac-root, --tickets-root, --apply, --json, --min-confidence). Pass 1 uses difflib.SequenceMatcher >= 0.90, Pass 2 uses keyword overlap + component match with approved stop-word list. --apply writes only high-confidence matches. Idempotency check present. Error handling via try/except on all file I/O and YAML parsing. Logging module used for diagnostics. No issues found.

## Implementation Tasks

### architect-review

- [x] Evaluate similarity libraries available in the project Python environment:
  check if `difflib`, `rapidfuzz`, or `Levenshtein` are installed (run
  `pip show rapidfuzz` or `pip show python-Levenshtein`). Approve the
  library to use for AC-1 similarity matching.
- [x] Define "significant keywords" for Pass 2: approve a stop-word list or
  approve using NLTK / simple split-and-filter approach.
- [x] Confirm the ticket-walking scope: should the audit walk only `99_done/`
  tickets, or all tickets in all lifecycle folders?

### test-writer

- [x] Write `tests/ac_store/test_cross_reference_audit.py`:
  - `test_exact_criteria_match_high_confidence`: fixture AC + ticket with
    matching criteria text; assert confidence=high.
  - `test_keyword_match_medium_confidence`: fixture AC + ticket with overlapping
    title keywords; assert confidence=medium.
  - `test_no_match_for_unrelated_ticket`: fixture with no overlap; assert empty
    matches.
  - `test_apply_writes_only_high_confidence`: fixture with one high + one medium
    match; run with --apply; assert only high AC modified.
  - `test_report_written_to_logs`: run audit; assert JSON file exists in
    debugging/logs/ with correct schema.
  - `test_apply_idempotent`: AC already has implemented_by; run --apply again;
    assert no duplicate.

### python-coder

- [x] Implement `scripts/ac_store/cross_reference_audit.py`:
  - CLI: `--ac-root <path>`, `--tickets-root <path>`, `--apply`, `--json`,
    `--min-confidence {high,medium}` (default: medium — show both).
  - Walk AC root: load all ACs with `work_status: todo` and `implemented_by: []`.
  - Walk ticket root: load all ticket `.md` files with `status: done` OR in
    `99_done/` folder.
  - Pass 1 (exact): for each AC, extract `criteria` text; for each done ticket,
    extract `## Acceptance Criteria` section body. Use `difflib.SequenceMatcher`
    ratio >= 0.90 → high confidence.
  - Pass 2 (keyword): tokenize AC `title` and ticket `title`; filter stop words
    (the, a, an, is, are, when, then, given, and, or, not); if >= 2 tokens
    overlap AND `component` matches → medium confidence.
  - Dedup: one ticket per AC (highest confidence wins if multiple matches).
  - Report: print human-readable format per the Context section; also write JSON.
  - `--apply`: for each high-confidence match, append ticket path to
    `implemented_by` (idempotency check first); set `work_status: done`.
  - Error handling: `try/except` on all file I/O; `try/except yaml.YAMLError`.
  - Logging: use `logging` module, not print, for internal diagnostic messages.

## Risk & Safety

- Touches money? No.
- Touches data? Read-only by default. `--apply` mode modifies AC YAML files
  (two fields: `implemented_by` and `work_status`). Both are targeted edits.
- False-positive risk: the medium-confidence heuristic may match unrelated
  tickets. Mitigated by the read-only default and the `--min-confidence high`
  flag for automated use. Human review of the JSON report before `--apply` is
  the intended workflow.
- Reversibility? `implemented_by` can be cleared and `work_status` reset in a
  single targeted edit per AC. The JSON report provides the full audit trail.
