---
title: "Backfill AC store with axes + real-store end-to-end computed-map test"
status: todo
components:
  - ac_store
created: 2026-07-07
depends_on:
  - 08_ac_axes_schema_and_generator_emit.md
priority: high
requires_adr: false
requires_diagram: false
change_target: config
risk_surface: internal
files_touched:
  - docs/acceptance-criteria
  - unit_tests/test_generate_ticket_from_ac.py
  - .security-allowlist
agents:
  test-writer: needed
  python-coder: needed
  test-runner: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# 10: Backfill AC store with axes + real-store end-to-end computed-map test

## Actor / Goal

In order to make computed quality gates actually fire on the existing acceptance criteria — and to prove it does with a test that would have caught the original phantom-done — we need to backfill every existing AC record with `change_target` + `risk_surface`, and add a real-store end-to-end test that generates a ticket from a real AC and asserts the computed guardrail agents appear in the emitted `agents:` map.

## Context

Ticket 08 makes the axes valid AC fields and has the generator consume + emit them. But the existing store still carries no axes, so until it is backfilled the computed path stays dormant for real inputs. This ticket performs the backfill and installs the behavioral gate that proves the whole chain works end-to-end.

**Backfill method (user decision, 2026-07-06): agent-classified, batch-reviewed.** An agent reads each AC's `criteria` prose and proposes `change_target`/`risk_surface`; the proposals are applied in batches, each surfaced as a diff for human approval before write. Many ACs already describe their axes in prose (e.g. `BO-620`: "Schema changes at a contract boundary…", "Code changes with internal risk…"), so classification is well-grounded.

The end-to-end test is the anti-phantom-done gate: it must exercise the REAL generator against a REAL (post-backfill) AC and assert the guardrail union is present — not a synthetic AC with hard-coded axes (that is what let the original defect ship green).

## AC References

- Depends on 08_ac_axes_schema_and_generator_emit.md (axes must be valid + emitted first).

## Acceptance Criteria

- [ ] AC-1: Every existing AC record in `docs/acceptance-criteria/` carries a valid `change_target` and `risk_surface` (verified by the ticket-08 schema validator over the whole store; zero validation errors).
- [ ] AC-2: The backfill was applied via agent classification with per-batch human-approved diffs (record the batch approvals in this ticket's Comments); no AC is left with a placeholder/unknown axis.
- [ ] AC-3: A real-store end-to-end test generates a ticket from an actual AC classified as a code/production-risk change and asserts the emitted `agents:` frontmatter contains the guardrail union (e.g. `architect-review`, `test-writer`, `test-runner`) — NOT the legacy map, and NOT via a synthetic hard-coded AC.
- [ ] AC-4: A `--dry-run` spot-check on a representative real AC shows the computed map (documented in Comments as evidence, mirroring the diagnostic that exposed the original defect).
- [ ] AC-5 (tooling): The `.security-allowlist` entries for `unit_tests/test_generate_ticket_from_ac.py` are converted from brittle per-line numbers to a single glob entry (`ENTROPY_HIGH:unit_tests/test_generate_ticket_from_ac.py:*`) so future edits don't re-break the suppressions.

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | | | |
| AC-2 | | | |
| AC-3 | | | |
| AC-4 | | | |
| AC-5 | | | |

## Comments

## Sign-offs
- [ ] test-writer
- [ ] python-coder
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Implementation Tasks

### test-writer
- [ ] Add the real-store end-to-end test (real AC → generated ticket → assert guardrail union in `agents:`), independent of synthetic fixtures (AC-3).

### python-coder
- [ ] Run/assist the agent-classified backfill of `docs/acceptance-criteria/` in batches; apply each approved batch (AC-1/AC-2).
- [ ] Validate the whole store with the ticket-08 schema validator (zero errors).
- [ ] Capture the `--dry-run` evidence in Comments (AC-4).
- [ ] Convert the test-file `.security-allowlist` entries to a glob (AC-5).

## Out of Scope
- Teaching `it-po-v3` to author the axes for *new* ACs — deferred to ticket 09 (blocked on it-po-v3 source reaching main).
- Fixing the `check_feedback_id.py` `[NO-FEEDBACK-CHECK]`-via-`COMMIT_EDITMSG` bypass defect (git writes `COMMIT_EDITMSG` after the pre-commit stage; only `GIT_COMMIT_MSG` works) — track as a standalone precommit-hooks ticket.

## Risk & Safety
- Touches money? No.
- Touches data? Yes — mutates every AC record in the store (adds two fields). Reversible via git revert; each batch is human-reviewed before write.
- Reversibility? All changes are on the epic branch; revert restores prior AC records.
