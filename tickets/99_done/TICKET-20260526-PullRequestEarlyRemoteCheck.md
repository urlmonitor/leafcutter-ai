---
title: "Pull-request agent should detect missing git remote early"
status: done
components:
  - build_pipeline
created: 2026-05-26
depends_on: []
priority: high
tags:
  - pull-request
  - fast-fail
  - agent-reliability
files_touched:
  - templates/agents/pull-request.md
agents:
  architect-review: signed_off
  python-coder: not_needed
  test-writer: not_needed
  test-runner: not_needed
  documentation-expert: not_needed
  change-scope-reviewer: not_needed
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: signed_off
  sql-coder: not_needed
  sql-query: not_needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
  explanation-author: not_needed
  how-to-author: not_needed
  reference-author: not_needed
  user-surface-smoker: signed_off
requires_diagram: false
requires_adr: false
user_facing_surface: agent_orchestrated
actuation_contract: "Invokes the pull-request agent in a repo with no git remote configured; agent emits an immediate blocker status ('no git remote configured — cannot push or create PR') and stops without entering the push or retry loop."
roadmap_phase: phase_1
advances_current_outcome: true
---

# Pull-request agent should detect missing git remote early

## Actor / Goal

In order to prevent wasted adjudication cycles on structurally impossible
operations, we need the pull-request agent to check for a configured git
remote as its first step so that it fails fast with a clear blocker message
instead of exhausting the retry and adjudication ladder.

## Context

Feedback log entries from 2026-05-19 describe a hard blocker during the
pull-request phase:

- **fb_2026-05-19_2c797c2f** (category: blocker): the pull-request phase hit
  a hard failure because no git remote was configured. The agent proceeded to
  attempt `git push` and `gh pr create` regardless.
- **fb_2026-05-19_7e0cc800** (category: subagent-quality): the ticket-supervisor
  logged an adjudication finding because the ladder was fully exhausted with no
  recovery path. The pull-request agent kept retrying an operation that could
  never succeed — "no remote" is a structural precondition failure, not a
  transient error.

The current `pull-request.md` template begins with commit-log inspection and
draft authoring before ever touching the remote. As a result, the first
observable failure occurs deep inside the push flow (Step 2 of the Push Flow
section), after the confirmation gate has already been opened, after the
pre-push sign-off sweep, and after the conflict-resolver delegation logic has
been prepared. By that point the adjudication ladder has been partially consumed.

A "no remote" condition is not retry-able: the agent cannot configure a remote
itself (that requires operator action), and no amount of retries will change the
outcome. It belongs in the pre-flight checks, not the push-error handling path.

Related: TICKET-20260526-git_check_precondition.md covers a similar fast-fail
pattern for `finalize-feature` and `changelog-agent` (no `.git` directory);
that ticket is complementary and independent.

## Acceptance Criteria

```gherkin
Given the pull-request agent is invoked on a branch with no git remote configured
When the agent begins its flow
Then it runs `git remote -v` as a precondition check before any other action
 And it immediately returns a blocker status: "no git remote configured — cannot push or create PR"
 And it does NOT attempt git push or gh pr create
 And it does NOT enter the conflict-resolver delegation or retry loop

Given the pull-request agent is invoked on a branch with at least one remote configured
When the agent begins its flow
Then the precondition check passes silently
 And the agent proceeds with its existing PR-Draft Contract unchanged

Given the pull-request agent returns the no-remote blocker
When ticket-supervisor processes the response
Then the agent's sign-off is written with status: failed (not signed_off)
 And no further retries are dispatched for this structural precondition failure
```

## Smoke Fixture

```yaml
surface: pull-request
fixture_input: |
  (invoke from a git repo where `git remote -v` returns empty output)
assertion: "no git remote|no remote configured|cannot push|blocker"
placeholder_signature: "TODO|PLACEHOLDER|not implemented"
```

## Sign-offs

- [x] architect-review — 2026-05-27 09:00
- [x] user-surface-smoker — 2026-05-27 09:01
- [x] pr-reviewer — 2026-05-27 09:01
- [x] commit — 2026-05-27 09:01
- [x] pull-request — 2026-05-27 09:02

## Comments

### architect-review — 2026-05-27 09:00 (status: ok)

Impact: small. Single-file additive change to `templates/agents/pull-request.md`.
Adds a precondition guard (Step 0) before any existing logic. No blast radius —
existing step numbering and flow unchanged. The `(status: blocker)` classification
is correct for structural failures that exhaust the adjudication ladder.

## Implementation Tasks

- [x] In `templates/agents/pull-request.md`: add a **Step 0 — Remote
  Precondition Check** as the very first step of the agent flow (before
  "Confirmation Contract" applies and before reading git log). Run
  `git remote -v`. If the output is empty, immediately return:
  `"Blocker: no git remote configured — cannot push or create PR. Configure
  a remote (e.g. git remote add origin <url>) and re-run this agent."` then
  stop. Do not proceed to draft generation.
- [x] Classify this failure as non-retryable in the agent's output so that
  ticket-supervisor does not dispatch a second attempt. The agent comment
  entry should use `(status: blocker)` rather than `(status: failed)` to
  signal to the ladder that the condition is structural.
- [x] Verify the happy path (remote present) is unaffected: no new prompts,
  no altered step numbering for the existing flow.
- [x] Run `python scripts/build.py --target-dir ..` to confirm the deployed
  agent file at `.claude/agents/pull-request.md` reflects the updated
  template.

## Out of Scope

- Configuring or suggesting a git remote (operator responsibility).
- Handling other push failures (e.g. authentication errors, network
  timeouts) — those remain in the existing conflict-resolver / retry path.
- Changing the adjudication ladder's retry policy — the fix is in the
  agent, not the supervisor.

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? Fully reversible — the guard is additive. Removing Step 0
  restores the current behavior. No schema, data, or config changes involved.
