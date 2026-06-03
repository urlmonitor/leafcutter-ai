---
title: "Feedback review skill (/feedback-review) and feedback lifecycle architecture diagram"
status: todo
components:
  - build_pipeline
created: 2026-06-03
depends_on:
  - TICKET-20260603-FeedbackResolutionTracking.md
priority: medium
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: true
requires_adr: false
requires_documentation:
  - architecture
user_facing_surface: slash_command
actuation_contract: "Runs aggregate.py --unresolved, presents grouped unresolved feedback entries to the user, and for each entry dispatches create-ticket, marks the entry resolved via resolve_feedback.py, or skips it; exits after printing a summary of N resolved, M tickets created, K skipped."
files_touched:
  - templates/skills/feedback-review/SKILL.md
  - templates/agents/retrospective-agent.md
  - docs/architecture/feedback-lifecycle.md
agents:
  architect-review: needed
  adr-author: not_needed
  architecture-diagram-author: needed
  test-writer: not_needed
  python-coder: not_needed
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: not_needed
  pr-reviewer: needed
  user-surface-smoker: needed
  commit: needed
  pull-request: needed
---

# Feedback review skill (/feedback-review) and feedback lifecycle architecture diagram

## Actor / Goal

In order to act on accumulated unresolved feedback rather than letting it age
unread in `feedback.jsonl`, we need a `/feedback-review` skill that lets the
user (or retrospective-agent) triage each unresolved entry — creating a ticket,
dismissing it with a rationale, or deferring it — so the feedback corpus stays
actionable rather than growing without bound.

## Context

The feedback write path (`scripts/feedback/submit_feedback.py`) appends
structured JSONL entries to `debugging/logs/feedback.jsonl`. These entries are
emitted by ticket-supervisor (subagent failures), pre-commit hooks (via
`emit_hook_finding.py`), and signoff skill (phase agent outcomes).

`TICKET-20260603-FeedbackResolutionTracking` adds `resolved_at` and
`resolution_note` fields to the schema and ships `resolve_feedback.py` plus
the `--unresolved` flag on `aggregate.py`. This ticket builds the triage skill
on top of those primitives.

A companion integration ticket (`TICKET-20260603-FeedbackCreateIntegration`,
not yet authored) will wire create-ticket to auto-resolve the originating
feedback entry when a ticket is created from feedback context. Until that
ticket ships, the skill manually calls `resolve_feedback.py` after ticket
dispatch.

`retrospective-agent` currently reads the feedback corpus at epic close but
has no way to recommend a triage session. This ticket adds that recommendation
path so the agent surfaces the `/feedback-review` command when unresolved count
exceeds zero.

### Skill invocation contexts

| Trigger | Who | When |
|---------|-----|------|
| `user → /feedback-review` | User directly | On-demand, any time |
| `retrospective-agent → recommend /feedback-review` | retrospective-agent | At epic close, when unresolved count > 0 |

### Dependencies

- **TICKET-20260603-FeedbackResolutionTracking** (required before this ticket
  can be driven): provides `aggregate.py --unresolved` and `resolve_feedback.py`.
- **TICKET-20260603-FeedbackCreateIntegration** (sibling, may arrive later):
  auto-resolves feedback entry when create-ticket is dispatched from the skill.
  The skill must work without this integration — it calls `resolve_feedback.py`
  explicitly as a fallback.

## Architecture Plan

### Diagrams

- `data_flow` diagram at `docs/architecture/feedback-lifecycle.md` (parent: `docs/architecture/`)

### Documentation

- `architecture` doc at `docs/architecture/feedback-lifecycle.md` — C4-style mermaid diagram documenting the complete feedback lifecycle: producers (ticket-supervisor, pre-commit hooks, signoff skill) → storage (feedback.jsonl) → evaluators (retrospective-agent, /feedback-review) → resolution (create-ticket integration, skill manual triage, resolve_feedback.py CLI)

## Acceptance Criteria

```gherkin
Given unresolved feedback entries exist in feedback.jsonl
When the user invokes /feedback-review
Then aggregate.py --unresolved is called and entries are presented grouped by category

Given a feedback entry is presented during /feedback-review
When the user selects "Create ticket"
Then create-ticket is dispatched with the entry as context
And resolve_feedback.py is called to mark the entry resolved with resolution_ticket set

Given a feedback entry is presented during /feedback-review
When the user selects "Dismiss"
Then resolve_feedback.py is called with a resolution_note explaining why not actionable
And the entry is marked resolved without a ticket being created

Given a feedback entry is presented during /feedback-review
When the user selects "Skip"
Then the entry is left unresolved and no resolve_feedback.py call is made

Given the triage session completes (all entries handled or skipped)
When /feedback-review exits
Then a summary is printed: "N resolved, M tickets created, K skipped"

Given unresolved feedback count > 0 after epic close
When retrospective-agent completes its report
Then the agent's output includes a recommendation to run /feedback-review
And the count of unresolved entries is surfaced in the recommendation

Given feedback.jsonl has no unresolved entries
When the user invokes /feedback-review
Then the skill exits immediately with "No unresolved feedback entries — nothing to triage."
```

## Sign-offs

- [ ] architect-review
- [ ] architecture-diagram-author
- [ ] pr-reviewer
- [ ] user-surface-smoker
- [ ] commit
- [ ] pull-request

## Comments

## Smoke Fixture

```yaml
surface: feedback-review
fixture_input: |
  (invoke /feedback-review with a feedback.jsonl containing at least one unresolved entry)
assertion: "(?i)(resolved|skipped|tickets? created|no unresolved)"
placeholder_signature: "(?i)(TODO|placeholder|not implemented|lorem ipsum)"
```

## Implementation Tasks

### architecture-diagram-author — feedback lifecycle diagram

- [ ] Author `docs/architecture/feedback-lifecycle.md` as a `data_flow` diagram
  documenting the complete feedback lifecycle.

  **Diagram scope** — show all of the following:

  Producers:
  - `ticket-supervisor` emits subagent-failure and submit-failed events
  - `pre-commit hooks` (via `emit_hook_finding.py`) emit hook-finding events
  - `signoff skill` emits phase-agent outcome events

  Storage:
  - All events land in `debugging/logs/feedback.jsonl` (per-worktree)
  - During `finalize-feature`, per-worktree files are merged to main

  Evaluators and timing:
  - `retrospective-agent` reads via `aggregate.py` (automated, runs at epic close)
  - `/feedback-review` skill reads via `aggregate.py --unresolved` (manual, on-demand)

  Resolution paths:
  - `create-ticket` integration (auto, marks resolved when ticket created from feedback)
  - `/feedback-review` (manual, calls `resolve_feedback.py` after user decision)
  - `resolve_feedback.py` CLI (escape hatch, direct invocation)

  Re-evaluation triggers:
  - New unresolved entries accumulating
  - `retrospective-agent` recommending `/feedback-review` when count > 0

  The diagram file must include valid frontmatter with `diagram_type: data_flow`
  and `related_code` populated with the feedback script paths.

### python-coder (skill author) — templates/skills/feedback-review/SKILL.md

- [ ] Create `templates/skills/feedback-review/SKILL.md` with YAML frontmatter
  (`name: feedback-review`, `description:`, `allowed-tools:` including Bash).

  **Skill flow** (the SKILL.md body must specify this step-by-step):

  1. **Load unresolved entries**
     Run `python scripts/feedback/aggregate.py --unresolved --format json`.
     If output is empty or entry count is zero, print
     "No unresolved feedback entries — nothing to triage." and exit.

  2. **Group by category**
     Parse the JSON output and group entries by `category` field
     (e.g. `subagent-quality`, `process-finding`, `hook-violation`,
     `submit-failed`, `miscellaneous`). Present one category at a time.

  3. **For each entry present:**
     - Show: `feedback_id`, `timestamp`, `severity`, `note`, `tags`, and
       `source` (if present).
     - Prompt: `[c]reate ticket / [d]ismiss / [s]kip`

     **Create ticket:**
     - Dispatch `/create-ticket` (or equivalent create-ticket invocation) with
       the feedback `note` and metadata as the primary request context.
     - After ticket creation, call:
       `python scripts/feedback/resolve_feedback.py --feedback-id <id> --ticket <new_ticket_path> --note "Ticket created via /feedback-review"`
     - Increment `tickets_created` counter.

     **Dismiss:**
     - Prompt user: "Dismiss reason (one line):"
     - Call:
       `python scripts/feedback/resolve_feedback.py --feedback-id <id> --note "<user_reason>"`
     - Increment `resolved_count` counter.

     **Skip:**
     - No `resolve_feedback.py` call.
     - Increment `skipped_count` counter.

  4. **Summary**
     After all entries are processed, print:
     ```
     /feedback-review complete: <resolved_count> resolved, <tickets_created> tickets created, <skipped_count> skipped.
     ```

  **Error handling** in the SKILL.md procedural steps:
  - If `aggregate.py` exits non-zero: surface stderr verbatim and abort with
    "aggregate.py failed — check feedback.jsonl path and try again."
  - If `resolve_feedback.py` exits non-zero: surface stderr and mark the entry
    as "resolve-failed" in the summary line (do not crash the loop).

  **Dependency note** the SKILL.md must state:
  > Requires TICKET-20260603-FeedbackResolutionTracking to be shipped
  > (provides aggregate.py --unresolved and resolve_feedback.py).

### python-coder (agent modifier) — templates/agents/retrospective-agent.md

- [ ] Add a new section or extend the existing output format in
  `templates/agents/retrospective-agent.md` so the agent:

  1. Calls `aggregate.py --unresolved --format json` as part of its post-epic
     summary step.
  2. When the returned entry count is > 0, appends to its output:
     ```
     ## Unresolved Feedback

     There are <N> unresolved feedback entries in feedback.jsonl.
     Run `/feedback-review` to triage them before closing the epic branch.
     ```
  3. When count is 0, omits the section entirely (no noise when clean).

  The modification must not break the existing retrospective flow — it is
  an additive output section only.

## Risk & Safety

- Touches money? No.
- Touches data? The skill calls `resolve_feedback.py`, which rewrites
  `feedback.jsonl` in place. This is the same rewrite pattern used by
  `link_feedback.py` and is covered by the reversibility guarantee in
  TICKET-20260603-FeedbackResolutionTracking. In the worst case, a failed
  write can be recovered from a git history snapshot of `feedback.jsonl` if
  it is tracked, or from the pre-write backup that `resolve_feedback.py` is
  expected to produce.
- Reversibility? Skill creation and agent modification are fully reversible
  (delete the skill file, revert the agent template). Resolved feedback entries
  are reversible by manually clearing `resolved_at` from the JSONL entry.
- Shared contract? The skill reads `aggregate.py` JSON output format. The
  `--unresolved` flag and JSON output shape are defined in
  TICKET-20260603-FeedbackResolutionTracking; if that ticket's output shape
  changes, this skill's parse step must be updated accordingly.
- Backward compatibility? `retrospective-agent.md` modification is additive —
  new output section only, no removal of existing sections.
