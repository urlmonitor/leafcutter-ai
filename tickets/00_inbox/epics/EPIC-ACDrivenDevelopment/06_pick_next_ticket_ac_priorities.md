---
title: "pick-next-ticket skill: incorporate AC priorities into ticket selection"
status: todo
components:
  - ac-store
  - ticket-creation
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
  architect-review: needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
  test-writer: needed
  llm-expert: needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
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

- [ ] architect-review
- [ ] test-writer
- [ ] llm-expert
- [ ] python-coder
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

### architect-review

- [ ] Read `templates/skills/ticket-prioritizer/SKILL.md` to identify the
  existing section structure and confirm where to insert the new content
  (--include-acs flag, pick_next.py) without breaking the existing sections.
- [ ] Confirm whether `pick_next.py` should live inside
  `templates/skills/ticket-prioritizer/scripts/` (alongside `prioritize.py`)
  or in `scripts/ac_store/`. Decision: use the same folder as `prioritize.py`
  for discoverability.

### test-writer

- [ ] Write `tests/test_pick_next_with_acs.py`:
  - `test_human_output_top_item`: mock prioritize.py returning one AC entry;
    run pick_next.py; assert all required fields in stdout.
  - `test_top_3_returns_3_items`: mock 5-item ready list; run --top 3; assert
    3 items printed.
  - `test_json_output_schema`: run --json; parse output; validate schema.
  - `test_empty_list_graceful_exit`: mock empty ready list; assert correct
    message; assert exit 0.

### llm-expert

- [ ] Author the documentation update for `SKILL.md`:
  - Insert `## AC-aware prioritization` section after the existing
    `## Integration with epic-supervisor` section.
  - Content: explanation of `--include-acs`, complexity-to-priority table,
    link to `ac_prioritizer.py`.
  - Insert `## pick_next.py — human recommendation` section with invocation
    syntax, output format (from AC-1), and `--top N` flag.
  - Do NOT remove or restructure existing sections — additive only.

### python-coder

- [ ] Implement `templates/skills/ticket-prioritizer/scripts/pick_next.py`:
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
