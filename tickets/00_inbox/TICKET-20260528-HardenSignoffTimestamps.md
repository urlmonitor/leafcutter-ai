---
title: "Harden sign-off timestamps: mandatory capture step + strict validator regex"
status: todo
components:
  - build_pipeline
created: 2026-05-28
depends_on: []
priority: medium
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - leafcutter-ai/templates/skills/signoff/SKILL.md
  - leafcutter-ai/templates/commit-guardian/check_ticket_signoff_parity.py
  - leafcutter-ai/templates/commit-guardian/_signoff_parity_checks.py
  - leafcutter-ai/scripts/commit_guardian/_signoff_parity_checks.py
  - unit_tests/commit_guardian/test_signoff_timestamp_enforcement.py
agents:
  architect-review: not_needed
  test-writer: needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: not_needed
  change-scope-reviewer: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  status-checker: not_needed
  frontend-coder: not_needed
  sql-query: not_needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
  explanation-author: not_needed
  how-to-author: not_needed
  reference-author: not_needed
  user-surface-smoker: needed
user_facing_surface: pre_commit_hook
ac_traceability:
  L0: BP-100
  L1: BP-100e
  l2:
    - BP-100e-1
    - BP-100e-2
    - BP-100e-3
    - BP-100e-4
    - BP-100e-5
  l3:
    - BP-100e-2-i
    - BP-100e-5-i
  ac_path: docs/acceptance-criteria/build_pipeline/BP-100-reliable-builds/BP-100e.yaml
  routing: direct_to_ba
actuation_contract: "The check_ticket_signoff_parity pre-commit hook rejects any ticket commit where a signed-off or failed sign-off line carries a timestamp that does not match \\d{4}-\\d{2}-\\d{2} \\d{2}:\\d{2}, blocking known bad patterns such as '(current session)' or '(now)'."
---

# Harden sign-off timestamps: mandatory capture step + strict validator regex

## Actor / Goal

In order to preserve reliable chronological audit trails in ticket sign-offs,
we need to (1) add a mandatory timestamp-capture step to the signoff skill §2
recipe and (2) tighten the pre-commit validator regex so non-conforming
timestamps are rejected at commit time.

## Context

During a recent epic drive, tickets 04 and 06 recorded `"2026-05-28 (current
session)"` instead of `"2026-05-28 15:12"` in both `## Sign-offs` lines and
`## Comments` headings. This makes post-drive chronological reconstruction
ambiguous and breaks the retrospective-agent's ability to order entries.

Two root causes:

1. **Skill gap**: The signoff skill §2 recipe defines `now_local` as an input
   under `### Inputs` but never instructs agents to *compute* it before the
   recipe steps. Agents that don't shell out to `date` substitute prose
   approximations.

2. **Validator permissiveness**: `_signoff_parity_checks.py` uses regexes that
   match the structural shape of sign-off lines (checked/unchecked box + agent
   name + em-dash + something) but do not validate that the "something" is a
   well-formed `YYYY-MM-DD HH:MM` timestamp. A line like
   `- [x] python-coder — 2026-05-28 (current session)` matches `_SIGNED_OFF_RE`
   today, so the bad timestamp slips through to the commit.

The fix is narrow: no schema changes, no new fields, no new hooks. Two targeted
edits close both gaps.

## Acceptance Criteria

```gherkin
Given the signoff skill §2 recipe is followed
When an agent performs the atomic sign-off
Then the recipe has an explicit mandatory step at the TOP that computes now_local
 via shell (date +"%Y-%m-%d %H:%M") before any Edit is issued
 And the step is labelled as non-optional

Given a ticket commit where a signed-off line reads "- [x] python-coder — 2026-05-28 (current session)"
When the pre-commit hook runs in --enforce mode
Then the hook exits 1 and emits a violation naming the malformed timestamp

Given a ticket commit where a signed-off line reads "- [x] python-coder — 2026-05-28 15:12"
When the pre-commit hook runs
Then the hook passes with no violations for that line

Given a ticket commit where a failed line reads "- [ ] python-coder — failed 2026-05-28 15:12"
When the pre-commit hook runs
Then the hook passes with no violations for that line

Given a ticket commit where a comments heading reads "### 2026-05-28 (now) — python-coder (status: ok)"
When the pre-commit hook runs in --enforce mode
Then the hook exits 1 and emits a violation naming the malformed heading timestamp
```

## Smoke Fixture

```yaml
surface: check_ticket_signoff_parity
fixture_input: |
  A ticket file with agents: {python-coder: signed_off} and a Sign-offs line:
  - [x] python-coder — 2026-05-28 (current session)
  Run: python scripts/commit_guardian/check_ticket_signoff_parity.py --enforce <ticket_path>
assertion: "violation|malformed|timestamp|does not match"
placeholder_signature: "All files pass"
```

## Sign-offs

- [ ] test-writer
- [ ] python-coder
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request
- [ ] user-surface-smoker

## Comments

## Implementation Tasks

### python-coder

**Deliverable 1 — Tighten timestamp regexes in `_signoff_parity_checks.py`**

The regex constants live in both the template copy
(`leafcutter-ai/templates/commit-guardian/_signoff_parity_checks.py`) and the
deployed copy (`leafcutter-ai/scripts/commit_guardian/_signoff_parity_checks.py`).
Both must be updated identically.

- [ ] Update `_SIGNED_OFF_RE` so the trailing timestamp group requires exactly
  `\d{4}-\d{2}-\d{2} \d{2}:\d{2}` and is anchored to end-of-line:
  ```python
  # Before:
  _SIGNED_OFF_RE = re.compile(
      r"^- \[x\]\s+(?P<agent>[a-zA-Z0-9_-]+)\s+—\s+\d{4}-\d{2}-\d{2} \d{2}:\d{2}\s*$"
  )
  # The existing pattern already uses \d{4}-\d{2}-\d{2} \d{2}:\d{2} but the
  # \s* at the end allows trailing whitespace that could hide "(current session)".
  # Confirm that the pattern ends with \d{2}:\d{2}\s*$ and does NOT use a
  # greedy .* before \d{2}:\d{2}. If the current pattern is already strict,
  # add an explicit negative lookahead (?!\s*\() to reject parenthesised suffixes:
  _SIGNED_OFF_RE = re.compile(
      r"^- \[x\]\s+(?P<agent>[a-zA-Z0-9_-]+)\s+—\s+\d{4}-\d{2}-\d{2} \d{2}:\d{2}(?!\s*\S)\s*$"
  )
  ```
  The key change: add `(?!\s*\S)` negative lookahead after `\d{2}:\d{2}` so any
  non-whitespace character after the timestamp (like `(current session)`) causes
  the line to NOT match `_SIGNED_OFF_RE`. A line that does not match any of the
  three patterns (`_SIGNED_OFF_RE`, `_FAILED_RE`, `_NEEDED_RE`) is treated as
  unrecognised by `_build_signoffs_map`, which then triggers an orphan or parity
  violation in `_check_parity` / `_check_orphans`.

- [ ] Apply the same negative-lookahead fix to `_FAILED_RE`:
  ```python
  _FAILED_RE = re.compile(
      r"^- \[ \]\s+(?P<agent>[a-zA-Z0-9_-]+)\s+—\s+failed \d{4}-\d{2}-\d{2} \d{2}:\d{2}(?!\s*\S)\s*$"
  )
  ```

- [ ] Add a comment heading validator in `_check_parity` or as a new helper
  `_check_comment_headings(content: str) -> list[str]` that scans `## Comments`
  for headings matching `^### ` and validates each against:
  ```python
  _COMMENT_HEADING_RE = re.compile(
      r"^### \d{4}-\d{2}-\d{2} \d{2}:\d{2} — [a-z][a-z0-9-]* \(status: (ok|blocker|question|handoff)\)$"
  )
  ```
  This regex is already in §5 of the signoff skill. Any heading that starts with
  `### ` but does not match this full pattern should produce a violation. Wire
  `_check_comment_headings` into `_validate_ticket_content` via `violations.extend(...)`.

- [ ] Update the `# DECISION HISTORY` block in both `_signoff_parity_checks.py`
  copies to document this change (date: 2026-05-28, ticket: this ticket basename).

**Deliverable 2 — Add mandatory time-capture step to `templates/skills/signoff/SKILL.md`**

- [ ] In §2, immediately after the `### Inputs` block (which lists `now_local`),
  insert a new `### Step 0 — Capture current timestamp (mandatory)` subsection
  **before the existing `### Steps` list**:

  ```markdown
  ### Step 0 — Capture current timestamp (mandatory, before any Edit)

  Before reading the ticket file or issuing any Edit, capture the current local
  time by running:

  ```bash
  now_local=$(date +"%Y-%m-%d %H:%M")
  ```

  This value is `now_local` referenced in Steps 2 and 3. **Do not skip this
  step.** Do not substitute prose like "(current session)", "(now)", or a
  date-only string. The pre-commit hook `check_ticket_signoff_parity.py`
  enforces `YYYY-MM-DD HH:MM` and will block a commit that carries an
  imprecise timestamp.
  ```

  Renumber the existing `### Steps` list to `### Steps (atomic edits)` to make
  the two-step structure visually clear.

### test-writer

- [ ] Create `unit_tests/commit_guardian/test_signoff_timestamp_enforcement.py`
  with the following test cases:

  - `test_signed_off_with_current_session_suffix_is_rejected`:
    Build a minimal ticket string with frontmatter
    `agents: {python-coder: signed_off}` and a Sign-offs line
    `- [x] python-coder — 2026-05-28 (current session)`.
    Call `_validate_ticket_content(content, "tickets/01_todo/test.md", set())`.
    Assert the returned list is non-empty and at least one violation mentions
    the agent name.

  - `test_signed_off_with_valid_timestamp_passes`:
    Same setup but Sign-offs line is `- [x] python-coder — 2026-05-28 15:12`.
    Assert violations list is empty (no parity errors).

  - `test_failed_with_now_suffix_is_rejected`:
    Frontmatter `agents: {python-coder: failed}`, Sign-offs line
    `- [ ] python-coder — failed 2026-05-28 (now)`.
    Assert violations list is non-empty.

  - `test_failed_with_valid_timestamp_passes`:
    Same setup with `- [ ] python-coder — failed 2026-05-28 15:12`.
    Assert violations list is empty.

  - `test_comment_heading_with_imprecise_timestamp_is_rejected`:
    Ticket with a `## Comments` heading
    `### 2026-05-28 (current session) — python-coder (status: ok)`.
    Assert at least one violation is returned mentioning the malformed heading.

  - `test_comment_heading_with_valid_timestamp_passes`:
    `### 2026-05-28 15:12 — python-coder (status: ok)`.
    Assert no violations are returned for the heading.

## Risk & Safety

- Touches money? No.
- Touches data? No — read-only validation changes only.
- Reversibility? Fully reversible. The regex changes are one-line edits in
  both `_signoff_parity_checks.py` copies. The skill edit is a text insertion
  with no deletions from existing content.
- Backward compatibility: Existing properly-formatted `YYYY-MM-DD HH:MM`
  timestamps continue to match; the only new rejections are timestamps carrying
  non-whitespace trailing content. Tickets already committed with imprecise
  timestamps will only be re-validated if those tickets are staged again in
  a future commit.
- Build pipeline: Both the template copy and the deployed (scripts/) copy of
  `_signoff_parity_checks.py` must be updated identically. Failing to update
  both will cause `build.py --validate` to detect a drift between templates and
  deployed outputs.
