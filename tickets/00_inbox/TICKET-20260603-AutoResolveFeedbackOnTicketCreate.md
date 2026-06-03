---
title: "Auto-resolve feedback entries when a ticket is created from them"
status: todo
components:
  - build_pipeline
created: 2026-06-03
depends_on:
  - TICKET-20260603-FeedbackResolutionTracking.md
priority: medium
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - leafcutter-ai/scripts/feedback/link_feedback.py
  - leafcutter-ai/templates/skills/ticket-wiring/SKILL.md
  - leafcutter-ai/templates/agents/business-analyst.md
agents:
  architect-review: not_needed
  test-writer: signed_off
  python-coder: signed_off
  sql-coder: not_needed
  test-runner: signed_off
  documentation-expert: not_needed
  pr-reviewer: signed_off
  commit: needed
  pull-request: needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
  user-surface-smoker: not_needed
---

# Auto-resolve feedback entries when a ticket is created from them

## Actor / Goal

In order to prevent resolved feedback entries from surfacing as actionable noise
in future review runs, we need create-ticket to automatically close out the
originating feedback entry in `debugging/logs/feedback.jsonl` when it produces
a ticket, so that operators and retrospective-agent always work from an accurate
set of genuinely open issues.

## Context

The feedback write side is fully wired: `submit_feedback.py` appends structured
JSONL entries to `debugging/logs/feedback.jsonl`. The `link_feedback.py` script
retroactively adds `addressed_by` refs when a ticket, commit, or PR is produced
for an issue — but it does NOT mark the entry as resolved. The forthcoming
`resolve_feedback.py` (from TICKET-20260603-FeedbackResolutionTracking) writes
a `resolved_at` UTC timestamp and an optional `resolution_ticket` field onto the
entry so aggregate/retrospective-agent can filter it out.

The gap: when the create-ticket pipeline runs and the user's request was
motivated by a known feedback entry (i.e. the invocation carries a `feedback_id`
in context, or `link_feedback.py` is called with a ticket ref), neither
`link_feedback.py` nor the ticket-wiring skill currently calls
`resolve_feedback.py`. The entry therefore remains flagged as open indefinitely.

### Integration points

- **ticket-wiring SKILL.md** — after writing the ticket file in Step 3, check
  whether a `feedback_id` is present in the invocation context. When present,
  call `resolve_feedback.py --feedback-id <id> --ticket <new_ticket_path>` to
  close the entry. This is the primary integration point.

- **link_feedback.py** — when `--ticket` is supplied to `link_feedback.py`, the
  script should additionally call `resolve_feedback.py` on the same
  `feedback_id` so that the retroactive linking operation also resolves the
  entry in one step. This prevents the two operations from diverging.

- **business-analyst.md (optional / stretch)** — during Step 1 analysis, the
  BA can run `aggregate.py --unresolved --category <relevant category>` to
  surface related unresolved feedback entries in its payload. This lets the user
  know that the ticket they are creating already partially addresses existing
  open feedback before they even confirm it.

### What is out of scope

- Automatically resolving feedback entries that are not explicitly linked by
  `feedback_id` at invocation time (heuristic matching is not part of this
  ticket).
- Changes to `submit_feedback.py` — entries continue to be written without
  resolution state; resolution remains retroactive.
- UI or reporting changes to the `/feedback-report` command.

## Acceptance Criteria

```gherkin
Given create-ticket is invoked with a feedback_id present in the invocation context
When the ticket-wiring skill writes the new ticket file
Then resolve_feedback.py is called with --feedback-id <id> and --ticket <new_ticket_path>
And the feedback entry gains a resolved_at UTC timestamp
And the feedback entry gains a resolution_ticket field containing the ticket path
And the ticket file itself is written normally (resolution is a post-write side-effect)

Given create-ticket is invoked WITHOUT a feedback_id in context
When the ticket-wiring skill writes the new ticket file
Then resolve_feedback.py is NOT called
And no error is produced

Given link_feedback.py is invoked with --feedback-id and --ticket arguments
When the script completes successfully
Then resolve_feedback.py is called on the same feedback_id with the same ticket path
And the entry is marked resolved_at in addition to having the addressed_by ref updated
And if resolve_feedback.py returns a no-op (already resolved), link_feedback.py still exits 0

Given business-analyst is run for a new ticket request
When the request category matches existing unresolved feedback entries
Then the BA payload includes a related_feedback list with matching feedback_ids, notes, and categories
And the create-ticket orchestrator surfaces these to the user before proceeding to Step 2
```

## Sign-offs

- [x] test-writer — 2026-06-03 10:30
- [x] python-coder — 2026-06-03 11:00
- [x] test-runner — 2026-06-03 11:15
- [x] pr-reviewer — 2026-06-03 11:30
- [ ] commit
- [ ] pull-request

## Comments

### 2026-06-03 10:30 — test-writer (status: ok)
feedback-id: fb_2026-06-03_4dd92b26
completion_manifest:
  test_stubs_created: true
  all_tests_red: true
  red_baseline_captured: true
red_baseline:
  - test_name: test_ticket_flag_triggers_resolve_subprocess
    file: unit_tests/test_link_feedback_resolve.py
    error: "AssertionError: False is not true : subprocess.run was not called with resolve_feedback.py when --ticket was supplied."
  - test_name: test_aggregate_unresolved_produces_list
    file: unit_tests/test_ticket_wiring_resolve.py
    error: "AssertionError: 2 != 0 : aggregate.py --unresolved --json must exit 0. aggregate.py does not yet support --json flag (use --format json instead)."

## Test Writer — Completion Report

### Tests Written
| File | Directory | Framework | Status |
|---|---|---|---|
| test_link_feedback_resolve.py | unit_tests/ | unittest | written |
| test_ticket_wiring_resolve.py | unit_tests/ | unittest | written |

### Verification Run
- Command: `python -m pytest unit_tests/test_link_feedback_resolve.py unit_tests/test_ticket_wiring_resolve.py -v`
- Result: 2 failures, 7 passed — red baseline established
  - `test_ticket_flag_triggers_resolve_subprocess` FAILS: subprocess.run not called with resolve_feedback.py (link_feedback.py not yet updated)
  - `test_aggregate_unresolved_produces_list` FAILS: aggregate.py does not support `--json` flag yet

### Notes
7 tests pass immediately (regression/contract tests for existing resolve_feedback.py and aggregate.py behaviour). 2 tests are correctly red for the new functionality to be implemented by python-coder.

### 2026-06-03 11:00 — python-coder (status: ok)
feedback-id: fb_2026-06-03_2fb8bba5
completion_manifest:
  link_feedback_resolve_call: true
  ticket_wiring_step_3b: true
  business_analyst_step_1_5: true
  aggregate_json_flag: true
  all_tests_green: true
  ruff_clean: true

Extended `link_feedback.py` with `_call_resolve_feedback()` helper and auto-resolve call gated on `--ticket` presence. Added `Step 3b` to `ticket-wiring/SKILL.md`. Added `Step 1.5` and `related_feedback` field to `business-analyst.md`. Added `--json` flag to `aggregate.py` (outputs plain JSON list, distinct from `--format json` which outputs wrapped object). All 27 tests pass, Ruff clean.

### 2026-06-03 11:15 — test-runner (status: ok)
feedback-id: fb_2026-06-03_148c1464
completion_manifest:
  full_suite_run: true
  new_tests_green: true
  no_new_regressions: true

137 of 139 tests pass. 2 pre-existing failures in `test_build_workflow_phase.py` (missing `build-feature.js` in this environment — unrelated to this ticket's changes). All 9 new tests (`test_link_feedback_resolve.py` x5, `test_ticket_wiring_resolve.py` x4) pass. No regressions in `unit_tests/feedback/` (18 tests all pass).

### 2026-06-03 11:30 — pr-reviewer (status: ok)
feedback-id: fb_2026-06-03_1ba1ee5c
completion_manifest:
  acceptance_criteria_met: true
  error_handling_policy_followed: true
  tests_adequate: true
  no_security_concerns: true

All acceptance criteria met. `_call_resolve_feedback()` correctly implements the four-rule error policy (subprocess wrapped in try/except OSError, non-zero exit logged but not propagated). `--ticket`-only guard correctly prevents resolve call for --commit-only and --pr-only invocations. `ticket-wiring` Step 3b and `business-analyst` Step 1.5 match the ticket specification. The `--json` flag for aggregate.py is a clean addition that doesn't break existing `--format json` callers. Approved.

## Implementation Tasks

### python-coder — extend link_feedback.py to call resolve_feedback.py

- [x] After the `_write_jsonl` call in `link_feedback.py`'s `main()` (i.e. after
  a ref was successfully added to `addressed_by`), call `resolve_feedback.py`
  on the same `feedback_id` and `--ticket` arg.

  Use `subprocess.run` (not `os.system`). Wrap in `try/except OSError` per the
  four-rule error policy. If `resolve_feedback.py` exits non-zero but does NOT
  raise an OS error (e.g. "already resolved" no-op), treat it as acceptable:
  log a debug note to stderr but do not change `link_feedback.py`'s exit code.

  The call should use the same `--jsonl` path override when the caller passed
  `--jsonl`, so that worktree-safe paths are forwarded correctly.

  **Guard:** only invoke `resolve_feedback.py` when `--ticket` was supplied
  (it is the resolution ref of record). Do not call it for `--commit`-only or
  `--pr`-only invocations, since those refs do not indicate a ticket was created.

  Add a `# ====================================================================`
  DECISION HISTORY entry documenting the rationale.

### python-coder — extend ticket-wiring SKILL.md to call resolve_feedback.py

- [x] Add a new **Step 3b — Auto-resolve originating feedback** subsection to
  `templates/skills/ticket-wiring/SKILL.md`, positioned immediately after
  the current "Step 3 — Error Recovery Path" section and before "Step 4 — Verify".

  Content of the new subsection:

  ```markdown
  ## Step 3b — Auto-resolve originating feedback (when feedback_id present)

  After the ticket file is written successfully (Step 2 complete, Step 4 not
  yet run), check whether a `feedback_id` is present in the invocation context
  (passed by the user, by create-ticket's orchestrator, or injected by a
  retrospective-agent session).

  **When `feedback_id` is present:**

  Run:
  ```bash
  python scripts/feedback/resolve_feedback.py \
      --feedback-id <feedback_id> \
      --ticket <relative_ticket_path>
  ```

  Use the same `__file__`-relative path resolution pattern as
  `link_feedback.py` so the script works from any working directory.

  - If the script exits 0 (`resolved ...` or `no-op ...`): log the one-line
    stdout to the ticket's `## Comments` section as an informational note
    (status: ok), then continue to Step 4.
  - If the script exits 1 (feedback_id not found): emit a **warning** to the
    user but do NOT abort ticket creation. The ticket file is already written;
    the resolution failure is non-fatal.
  - If the script exits 2 (filesystem error): emit a **warning** and surface
    the stderr output. Do NOT abort ticket creation.

  **When `feedback_id` is absent:** skip this step entirely.
  ```

### python-coder — optional: surface related feedback in business-analyst.md

- [x] In `templates/agents/business-analyst.md`, add a Step 1.5 after the
  six-dimension scoping step and before spawning test-planner:

  ```markdown
  ### Step 1.5 — Surface related unresolved feedback (when available)

  Run `python scripts/feedback/aggregate.py --unresolved --json` to obtain
  the current set of unresolved feedback entries. If the command is
  unavailable or fails, skip silently — this step is best-effort.

  Filter the returned entries to those whose `category`, `tags`, or `note`
  text overlaps with the user's request topic (LLM judgment). If any overlap
  is found, include a `related_feedback` field in the output payload:

  ```json
  "related_feedback": [
    {
      "feedback_id": "fb_YYYY-MM-DD_XXXXXXXX",
      "category": "<category>",
      "note": "<truncated note, 120 chars max>",
      "severity": "<severity>"
    }
  ]
  ```

  When `related_feedback` is non-empty, `create-ticket` MUST surface this
  list to the user with the message:
  "The following unresolved feedback entries appear related to this request.
   Creating this ticket will resolve them once implemented. [list]"
  before proceeding to Step 2.
  ```

### test-writer

- [x] Write tests in `unit_tests/test_link_feedback_resolve.py`:
  - When `--ticket` is supplied and the feedback_id exists, `resolve_feedback`
    subprocess is called with the correct args.
  - When `--commit`-only is supplied, `resolve_feedback` is NOT called.
  - When `resolve_feedback.py` returns exit code 0 with "no-op" stdout,
    `link_feedback.py` still exits 0.
  - When `resolve_feedback.py` raises an `OSError` (binary not found / path
    error), `link_feedback.py` logs to stderr but still exits 0 for the
    linking step.

- [x] Write tests in `unit_tests/test_ticket_wiring_resolve.py` (or extend
  existing ticket-wiring tests):
  - When `feedback_id` is present in context and `resolve_feedback.py` exits 0,
    a comment line is appended to the ticket's `## Comments` section.
  - When `feedback_id` is absent, `resolve_feedback.py` is not called.
  - When `resolve_feedback.py` exits 1, the ticket file is still returned
    without abort.

## Risk & Safety

- Touches money? No.
- Touches data? `resolve_feedback.py` rewrites `feedback.jsonl` in place. Risk
  is the same as the dependency ticket: low operational friction if the entry
  is misidentified, reversible by manually removing `resolved_at`.
- Reversibility? Fully reversible. `resolved_at` is an additive field.
- Backward compatibility? `link_feedback.py` gains a new subprocess call gated
  on `--ticket` being present; all other invocation patterns are unchanged.
  The ticket-wiring skill step is opt-in (gated on `feedback_id` presence).
- Shared contract? The `business-analyst.md` change adds an optional
  `related_feedback` field to the BA output payload. Downstream agents that do
  not read this field are unaffected.
