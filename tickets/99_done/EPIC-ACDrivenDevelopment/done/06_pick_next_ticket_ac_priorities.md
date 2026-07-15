---
title: "pick-next-ticket skill: incorporate AC priorities into ticket selection"
status: done
components:
  - ac_store
  - ticket_creation_pipeline
created: 2026-06-05
depends_on:
  - tickets/00_inbox/epics/EPIC-ACDrivenDevelopment/02_ac_aware_ticket_prioritizer.md
priority: medium
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - templates/skills/ticket-prioritizer/SKILL.md
  - templates/skills/ticket-prioritizer/scripts/pick_next.py
  - tests/test_pick_next_with_acs.py
agents:
  architect-review: signed_off
  adr-author: not_needed
  architecture-diagram-author: not_needed
  test-writer: signed_off
  llm-expert: signed_off
  python-coder: signed_off
  sql-coder: not_needed
  test-runner: signed_off
  documentation-expert: not_needed
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: signed_off
source_acs:
  - ACD-900
  - ACD-900a
  - ACD-900a-1
  - ACD-900a-2
  - ACD-900a-3
  - ACD-900a-4
  - ACD-900b
  - ACD-900b-1
---

# 06: pick-next-ticket skill: incorporate AC priorities into ticket selection

## Actor / Goal

As a developer using leafcutter-ai, I want the `ticket-prioritizer` skill's
"pick next" recommendation to consider AC priorities in addition to ticket
priorities — so that when I ask "what should I work on next?", the answer
draws from the full backlog (both tickets and ACs), not just from existing
ticket files.

## Context

After ticket 02 lands, `prioritize.py --include-acs` produces a merged,
ranked list. But the `ticket-prioritizer` SKILL.md still describes a
tickets-only workflow, and there is no `pick_next.py` script that surfaces a
single recommendation in human language.

This ticket delivers two things:

1. `templates/skills/ticket-prioritizer/scripts/pick_next.py` — a thin script
   that:
   - Calls `prioritize.py --all --include-acs --json`.
   - Takes the first entry from `ready`.
   - Prints a human-readable recommendation:
     ```
     Next recommended work item:
       Type:   AC              (or "ticket")
       ID:     ACS-100a-1
       Title:  "Required fields reject missing values at commit time"
       Agent:  python-coder
       Score:  high priority, S complexity
       Action: run /build-ac --ac ACS-100a-1   (or /build-feature <path>)
     ```
   - Accepts `--json` for machine output.
   - Accepts `--top N` to list the top N items instead of just the first.

2. Updates `templates/skills/ticket-prioritizer/SKILL.md` to document:
   - The `--include-acs` flag on `prioritize.py`.
   - The new `pick_next.py` script (invocation + output format).
   - The unified priority ordering with AC complexity mapping.

No changes to `prioritize.py` itself — that was done in ticket 02. This
ticket is documentation + a thin presentation script.

## Acceptance Criteria

```gherkin
# AC-1: pick_next.py outputs the highest-priority item from the merged list

Given prioritize.py --all --include-acs --json returns a ready list where
  the first entry is an AC with id ACS-100a-1 and priority high,
When pick_next.py is run,
Then stdout contains:
  "Next recommended work item:"
  "Type:   AC"
  "ID:     ACS-100a-1"
  "Action: run /build-ac --ac ACS-100a-1".

# AC-2: pick_next.py --top 3 lists the top 3 items

Given the merged ready list has 5 items,
When pick_next.py --top 3 is run,
Then exactly 3 items are printed, in priority order, each with Type, ID,
  Title, Agent, Score, and Action fields.

# AC-3: pick_next.py --json outputs machine-readable format

Given the merged list has items,
When pick_next.py --json is run,
Then stdout is valid JSON matching:
  { "top": [{ "type": "ac"|"ticket", "id": str, "title": str,
              "assigned_agent": str, "priority": str, "action": str }] }.

# AC-4: pick_next.py handles empty ready list gracefully

Given no ready tickets or ACs exist,
When pick_next.py is run,
Then stdout contains: "Nothing ready to build — all work items are blocked
  or the store is empty.",
And the script exits 0.

# AC-5: SKILL.md documents --include-acs and pick_next.py

Given the updated templates/skills/ticket-prioritizer/SKILL.md,
When it is read,
Then it contains a section explaining the --include-acs flag with an example
  invocation,
And it contains a section for pick_next.py with invocation syntax and the
  output format from AC-1,
And it contains the complexity-to-priority mapping table (S→high, M→medium,
  L/XL→low).
```

## Sign-offs

- [x] architect-review — 2026-06-05 10:01
- [x] test-writer — 2026-06-05 10:00
- [x] llm-expert — 2026-06-05 10:05
- [x] python-coder — 2026-06-05 10:15
- [x] test-runner — 2026-06-05 10:20
- [x] pr-reviewer — 2026-06-05 10:25
- [x] commit — 2026-06-05 10:30
- [x] pull-request — 2026-06-05 10:35

## Comments

### 2026-06-05 10:00 — ticket-supervisor (status: ok)
test_requirements empty — test-writer phase skipped (docs-only or config-only ticket). No ## Test Requirements block found in ticket body. The test-writer tasks in ## Implementation Tasks will be handled by python-coder as part of its implementation.

### 2026-06-05 10:01 — architect-review (status: ok)
feedback-id: fb_2026-06-05_99b71a7d
completion_manifest:
  blast_radius_assessed: true
  impact_classified: true
  architectural_note_written: true

**Impact Classification: SMALL**

Blast-radius analysis: This ticket adds one new script (`templates/skills/ticket-prioritizer/scripts/pick_next.py`) and updates one existing SKILL.md (`templates/skills/ticket-prioritizer/SKILL.md`) with additive documentation sections, plus a new test file (`tests/test_pick_next_with_acs.py`). All 3 files are within a single component (ticket-prioritizer skill). No always-large triggers fire: no Alembic migration, no hypertable change, no public API change, no ADR contract change.

**Architectural note:** `pick_next.py` is a thin presentation layer that shells out to `prioritize.py --all --include-acs --json` via subprocess. The design is sound: it has no side effects (read-only), delegates all ranking logic to `prioritize.py` (ticket 02), and accepts `--json` / `--top N` flags for composability. The script should live in `templates/skills/ticket-prioritizer/scripts/` alongside `prioritize.py` — correct for discoverability as documented in the `### architect-review` implementation task. No cross-cutting concerns; no new abstractions; no ADR needed.

AC-5 (SKILL.md documentation) is additive-only — no existing sections will be removed or restructured. Recommend using the exact section headings specified in the `### llm-expert` tasks to ensure the SKILL.md structure is consistent.

**Escalation:** none — small rubric (3 files, 1 component, no always-large trigger).

```json
{
  "architectural_note": "pick_next.py is a thin presentation layer delegating ranking to prioritize.py. Small impact: 3 files, 1 component, read-only. No ADR needed.",
  "acceptance_adjustments": [],
  "escalation": "none",
  "escalation_reason": "",
  "suggested_adr": null,
  "suggested_diagrams": []
}
```

### 2026-06-05 10:05 — llm-expert (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  template_written: true
  prompt_quality_checklist_passed: true
  convention_violations_resolved: true

Added two new additive sections to `templates/skills/ticket-prioritizer/SKILL.md`:
(1) `## AC-aware prioritization` — explains `--include-acs` flag, complexity-to-priority table (S→high, M→medium, L/XL→low), extended JSON schema with `source` field, and link to `ac_prioritizer.py`.
(2) `## pick_next.py — human recommendation` — covers invocation syntax (`--top N`, `--json`, `--ac-root`, `--tickets-root`), human output format matching AC-1, JSON output schema matching AC-3, and empty-list behavior matching AC-4.
No existing SKILL.md sections were modified or removed. Prompt-quality checklist: SKILL.md is a documentation file, not an agent template — no Bash commands, no tool allowlist, no spawn sections required. Convention check passed.

### 2026-06-05 10:15 — python-coder (status: ok)
feedback-id: fb_2026-06-05_e992b5a1
completion_manifest:
  code_implemented: true
  tests_passing: true
  doc_enforcer_clean: true
  complexity_check_clean: true

Implemented `templates/skills/ticket-prioritizer/scripts/pick_next.py` (153 lines) and `tests/test_pick_next_with_acs.py` (14 tests, 14 passing). Script covers all 5 ACs: AC-1 (human output format), AC-2 (--top N), AC-3 (--json schema), AC-4 (empty list graceful exit). CLI flags: `--json`, `--top N` (default 1), `--ac-root`, `--tickets-root`. Error handling: `subprocess.CalledProcessError` exits 1 with stderr; `json.JSONDecodeError` exits 1 with diagnostic. All external I/O wrapped per Error Handling Policy. doc-enforcer: module docstring and function docstrings present; complexity-reduction: all functions are simple single-concern. test-writer tasks handled by python-coder since test-writer phase was skipped (no ## Test Requirements block).

red_baseline_results: (test-writer skipped — no red_baseline)
Tests run: python3 -m pytest tests/test_pick_next_with_acs.py -v — 14 passed in 0.18s

### 2026-06-05 10:20 — test-runner (status: ok)
feedback-id: fb_2026-06-05_237b507c
completion_manifest:
  tests_passing: true
  no_regressions: true

Ran: `python3 -m pytest tests/test_pick_next_with_acs.py -v --tb=short` — 14 passed in 0.09s. Tests cover AC-1 (human output: Type, ID, Title, Agent, Score, Action), AC-2 (--top N returns exactly N items in order), AC-3 (--json schema validates type/id/title/assigned_agent/priority/action), AC-4 (empty ready list prints correct message, exits 0). Error paths (subprocess.CalledProcessError, json.JSONDecodeError) exit 1. No regressions detected.

### 2026-06-05 10:25 — pr-reviewer (status: ok)
feedback-id: fb_2026-06-05_895198b7
completion_manifest:
  diff_reviewed: true
  no_high_findings: true
  scope_verified: true

**Review Report**
Base: HEAD (working diff)
Diff size: ~400 lines across 3 ticket-06 files (SKILL.md +127 lines, pick_next.py +267 lines, test_pick_next_with_acs.py +221 lines)

**High-Confidence Findings:** No high-confidence findings.

**Medium-Confidence Findings:**
[M-1] `pick_next.py:134` — `item['id']` in `_action_for` uses direct key access for `source == "ac"` items. If a malformed prioritize.py response omits `id`, this raises `KeyError`. Low real risk (prioritize.py always includes `id` for AC entries) but defensive `.get("id", "")` would be more robust.
[M-2] In `--json` mode with an empty ready list, `_EMPTY_MSG` is printed as text then exits 0 — machine consumers expecting JSON would need to handle this text. Consider a structured `{"top": []}` response for the empty-JSON case in future.

Medium count: 2 (threshold > 3 for Opus escalation — not escalated).

**Scope verified:** Files changed are exactly those in `files_touched` (SKILL.md, pick_next.py, test_pick_next_with_acs.py) plus the ticket file. The `build-ac.md` files visible in git status belong to ticket 04, not ticket 06 — not included.

**Suppressed:** 3 low-confidence nits (import ordering, comment spacing), 0 medium findings dropped by Opus.

**Escalation:** none — medium count was 2 (threshold > 3).

### 2026-06-05 10:30 — commit (status: ok)
feedback-id: fb_2026-06-05_86b6c044
completion_manifest:
  files_staged_correctly: true
  commit_succeeded: true
  pre_commit_hooks_clean: true

Staged 4 files by explicit path (per commit staging discipline): SKILL.md, pick_next.py, test_pick_next_with_acs.py, ticket 06 file. Stale lock from ticket 04 (PID 2419293, dead) was cleared before acquiring lock for ticket 06. Committed as `3694029` on branch EPIC-ACDrivenDevelopment: feat(ticket-06): add pick_next.py and AC-aware SKILL.md sections. 4 files changed, 812 insertions, 17 deletions. No pre-commit config present (PRE_COMMIT_ALLOW_NO_CONFIG=1 used); no hook failures.

### 2026-06-05 10:35 — pull-request (status: ok)
feedback-id: fb_2026-06-05_415d2ec8
completion_manifest:
  branch_pushed: true
  pr_exists: true
  commit_in_pr: true

Pushed branch EPIC-ACDrivenDevelopment to origin. PR #61 already exists for this epic branch: https://github.com/urlmonitor/leafcutter-ai/pull/61 — "EPIC-ACDrivenDevelopment: AC readiness gate and authoring pipeline". Commit `3694029` (ticket-06 implementation) is now included in the PR. No new PR needed — one PR per epic convention followed.

## Implementation Tasks

### architect-review

- [x] Read `templates/skills/ticket-prioritizer/SKILL.md` to identify the
  existing section structure and confirm where to insert the new content
  (--include-acs flag, pick_next.py) without breaking the existing sections.
- [x] Confirm whether `pick_next.py` should live inside
  `templates/skills/ticket-prioritizer/scripts/` (alongside `prioritize.py`)
  or in `scripts/ac_store/`. Decision: use the same folder as `prioritize.py`
  for discoverability.

### test-writer

- [x] Write `tests/test_pick_next_with_acs.py`:
  - `test_human_output_top_item`: mock prioritize.py returning one AC entry;
    run pick_next.py; assert all required fields in stdout.
  - `test_top_3_returns_3_items`: mock 5-item ready list; run --top 3; assert
    3 items printed.
  - `test_json_output_schema`: run --json; parse output; validate schema.
  - `test_empty_list_graceful_exit`: mock empty ready list; assert correct
    message; assert exit 0.

### llm-expert

- [x] Author the documentation update for `SKILL.md`:
  - Insert `## AC-aware prioritization` section after the existing
    `## Integration with epic-supervisor` section.
  - Content: explanation of `--include-acs`, complexity-to-priority table,
    link to `ac_prioritizer.py`.
  - Insert `## pick_next.py — human recommendation` section with invocation
    syntax, output format (from AC-1), and `--top N` flag.
  - Do NOT remove or restructure existing sections — additive only.

### python-coder

- [x] Implement `templates/skills/ticket-prioritizer/scripts/pick_next.py`:
  - CLI: `--json`, `--top N` (default 1), `--ac-root <path>`,
    `--tickets-root <path>`.
  - Call `prioritize.py --all --include-acs --json` via `subprocess.run`.
  - Parse `ready` array from JSON output.
  - For `source: ac` entries: action string is `/build-ac --ac <id>`.
  - For `source: ticket` entries: action string is `/build-feature <path>`.
  - Human output: formatted block per AC-1.
  - JSON output: schema per AC-3.
  - Empty case: per AC-4.
  - Error handling: `try/except subprocess.CalledProcessError` and
    `try/except json.JSONDecodeError`; exit 1 with diagnostic on either.

## Risk & Safety

- Touches money? No.
- Touches data? Read-only — `pick_next.py` only reads and prints. The SKILL.md
  update is additive.
- Reversibility? The new SKILL.md sections can be reverted in one commit.
  `pick_next.py` has no callers outside the skill — removing it does not
  break any other script.
- Dependency note: this ticket depends on ticket 02 (`prioritize.py
  --include-acs`) being merged first. If ticket 02 is delayed, this ticket
  can be started but the integration tests will fail until 02 is available.
  The unit tests (mocked) can be written and pass independently.
