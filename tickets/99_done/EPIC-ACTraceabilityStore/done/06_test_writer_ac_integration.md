---
title: "Update test-writer to read AC files and emit covers: tags in tests"
status: done
components:
  - build_pipeline
created: 2026-06-04
depends_on:
  - 02_ac_store_directory_scaffold.md
  - 03_precommit_hook_test_tagging.md
priority: medium
roadmap_phase: phase_2
advances_current_outcome: false
requires_diagram: false
requires_adr: false
files_touched:
  - templates/agents/test-writer.md
agents:
  architect-review: not_needed
  test-writer: not_needed
  python-coder: not_needed
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: signed_off
  adr-author: not_needed
  architecture-diagram-author: not_needed
  explanation-author: not_needed
  how-to-author: not_needed
  reference-author: not_needed
  user-surface-smoker: not_needed
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: signed_off
---

# 06: Update test-writer to read AC files and emit covers: tags in tests

## Actor / Goal

In order to produce tests that are machine-linked to ACs from the moment they
are written, we need to update the `test-writer` agent template to check
`docs/acceptance-criteria/` for AC files referenced by the ticket and emit
`# covers: XX-NNN` tags on every test function it writes, so that the
bidirectional coverage check (ticket 04) passes for all newly authored tests.

## Context

Currently `test-writer` derives tests from the `## Acceptance Criteria` section
of the ticket body. With the AC store, the ticket body still contains Gherkin
scenarios (for human readability), but the canonical criteria live in AC YAML
files.

The updated test-writer workflow:

1. Check if `docs/acceptance-criteria/` exists and if the ticket references
   any AC IDs (via "implements AC-FIN-003" or similar in the ticket body).
2. If AC files are found: read each AC YAML, use the `criteria` field as the
   primary source for the test scenarios.
3. For each test function written: add `# covers: <AC-ID>` as the first
   comment in the function body.
4. If AC store does not exist or ticket references no AC IDs: fall back to
   the existing ticket-body-Gherkin approach. Still emit a `# covers:` tag
   using a placeholder format: `# covers: UNKNOWN` (so the hook produces a
   warning, not silence).

### Tag placement

```python
def test_merge_executes_before_test_runner():
    # covers: FIN-001
    # Verify that git merge origin/main runs before test-runner dispatch.
    ...
```

The tag must be the first line of the function body (after the `def` line).

## Acceptance Criteria

```gherkin
Given test-writer runs on a ticket that references AC-FIN-001
 And docs/acceptance-criteria/finalize/FIN-001.yaml exists
When test-writer writes a test for FIN-001
Then the test function body begins with # covers: FIN-001

Given test-writer runs on a ticket with no AC store present
When test-writer writes tests from the ticket's Gherkin
Then each test function body begins with # covers: UNKNOWN

Given test-writer runs on a ticket referencing AC-FIN-001 with status: deprecated
When test-writer processes the AC
Then it logs a warning "AC FIN-001 is deprecated — skipping test generation for this AC"
 And it does not write a test function for the deprecated AC
```

## Sign-offs

- [x] documentation-expert — 2026-06-04 12:00
- [x] pr-reviewer — 2026-06-04 12:05
- [x] commit — 2026-06-04 12:10
- [x] pull-request — 2026-06-04 12:15

## Comments

### 2026-06-04 12:15 — pull-request (status: ok)
feedback-id: fb_2026-06-04_11b072eb
completion_manifest:
  branch_pushed: true
  pr_created: true
  pr_body_complete: true
Pushed commit 536476f to origin/EPIC-ACTraceabilityStore. Existing PR #46 (feat(ac-store): AC YAML schema, validator hook, and ADR-008) now includes this commit. No new PR created — one PR per epic convention. Branch is ahead of remote by 0 commits after push.

### 2026-06-04 12:10 — commit (status: ok)
feedback-id: fb_2026-06-04_2a77f16b
completion_manifest:
  pre_commit_hooks_pass: true
  commit_message_valid: true
  ticket_staged: true
Staged `templates/agents/test-writer.md` and `tickets/.../06_test_writer_ac_integration.md`. Commit 536476f created: "feat(EPIC-ACTraceabilityStore/06): update test-writer with AC store integration". 2 files changed, 103 insertions(+), 4 deletions(-). Pre-commit hook absent (PRE_COMMIT_ALLOW_NO_CONFIG=1 used per repo convention).

### 2026-06-04 12:05 — pr-reviewer (status: ok)
feedback-id: fb_2026-06-04_4fcd43cb
completion_manifest:
  diff_reviewed: true
  no_high_findings: true
  scope_verified: true
Reviewed diff for ticket 06. Base: EPIC-ACTraceabilityStore. Diff size: 78 lines added to `templates/agents/test-writer.md`. No high-confidence findings. Step 1 sub-step 5 (AC store pre-flight), Step 2i (`# covers:` tag placement), and `ac_ids_covered` manifest item are all correct, well-structured, and match the ticket requirements. Scope matches `files_touched: [templates/agents/test-writer.md]`. Suppressed: 0 low-confidence nits.

## Escalation

Branch: none
Reason: not escalated: medium count was 0 (threshold > 3)

### 2026-06-04 12:00 — documentation-expert (status: ok)
feedback-id: fb_2026-06-04_7d746428
completion_manifest:
  doc_written: true
  cross_links_added: true
  diataxis_genre_correct: true
Updated `templates/agents/test-writer.md` with three additions: (1) Step 1 pre-flight sub-step 5 — AC store lookup that reads `docs/acceptance-criteria/` YAML files, loads criteria as the authoritative test source, and skips deprecated/superseded ACs with a warning; (2) Step 2i — mandatory `# covers: <AC-ID>` tag placement on the first line of every test function body, with sourcing rules and fallback to `# covers: UNKNOWN`; (3) expanded completion manifest section with `ac_ids_covered` field and two examples (AC store hit and fallback path). All three implementation tasks from the ticket are complete. No cross-repo links added (template is self-contained; the ticket-04 bidirectional coverage check is referenced inline). Diataxis genre: reference (agent template update).

## Implementation Tasks

- [ ] In `templates/agents/test-writer.md`, add a pre-flight step:
  - "Before writing any test functions, check if `docs/acceptance-criteria/`
    exists. If yes, extract all AC IDs referenced in the ticket body (regex:
    `AC-[A-Z]{2,6}-[0-9]{3}`). For each referenced ID, read the corresponding
    YAML file and load `id`, `status`, and `criteria`."
  - "Skip test generation for ACs with `status: deprecated` or
    `status: superseded_by` (log a warning for each skipped AC)."
- [ ] Update test-writing instructions: "For each test function, place
  `# covers: <AC-ID>` as the first line of the function body. If the AC
  store is absent, use `# covers: UNKNOWN`."
- [ ] Add a note in the completion manifest for test-writer: the manifest
  should record which AC IDs were covered in each test file.

## Risk & Safety

- Touches money? No.
- Touches data? No. Template edit only.
- Reversibility? Reverting the test-writer template restores prior behaviour.
  Existing test files with `covers:` tags are not affected.
- The `# covers: UNKNOWN` fallback ensures the test-tagging hook still
  fires a warning (not silence) when test-writer runs without AC context.
