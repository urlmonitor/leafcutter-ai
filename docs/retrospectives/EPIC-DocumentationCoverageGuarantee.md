---
title: 'Retrospective: EPIC-DocumentationCoverageGuarantee'
type: retrospective
status: active
created: 2026-08-10
epic: EPIC-DocumentationCoverageGuarantee
source_ac: BO-2200
components:
- build_orchestration
last_updated: '2026-08-10'
description: 'Overview of Retrospective: EPIC-DocumentationCoverageGuarantee.'
---
# Retrospective: EPIC-DocumentationCoverageGuarantee
Date: 2026-08-10
Epic duration: 2026-07-15 to 2026-08-10 (26 days)
Merge commit: 981f4280c (PR #337, squash)

## Summary

EPIC-DocumentationCoverageGuarantee delivered the BO-2200 documentation coverage guarantee
feature: a declarative `documentation_gates` policy in `guardrail_gates.yaml`, a new
`documentation-verifier` phase agent (priority 11.9, post-coder), an `Agent Contracts`
block injected into every doc-required generated ticket, and post-coder ordering that places
`documentation-expert` after the coder phase rather than in the pre-coder flow-change slot.
The implementation touched 63 files (+9,982 / -391 lines) across config, template, generator
script, and 20 new unit test files.

The finalization arc was unusual. The feature code was developed as direct branch commits on
`feature/BO-2200-doc-coverage` and landed as a single squash commit (PR #337) on 2026-08-10.
The parallel per-ticket epic drive was partially run but abandoned before completion; as a
result, per-ticket sign-offs and AC YAML store fields (`work_status`, `implemented_by`,
`covered_by`) were never reconciled at merge time. Post-merge, an evidence-based audit using
the `ac-audit` skill (213 cited tests, four parallel skeptical verification agents) found 24
of 29 leaf ACs genuinely done with 0 phantom-dones and 5 real remaining gaps. The audit
required because reconciliation was skipped at merge — a friction pattern worth documenting
for future epics.

## Phase Metrics

`extract_epic_facts.py` was not found in this repository's script paths; per-phase signed-off
/ failed / needed counts are not available from the structured telemetry script. The table
below uses the feedback category breakdown from `aggregate.py` as the available proxy.

### Feedback Category Breakdown

| Category | Count |
|----------|-------|
| complete | 131 |
| blocker | 11 |
| quality-concern | 8 |
| knowledge-gap | 1 |
| **Total** | **151** |

### Feedback Phase Distribution

| Phase | Feedback Entries |
|-------|-----------------|
| test-runner | 45 |
| test-writer | 23 |
| commit | 24 |
| pull-request | 21 |
| python-coder | 18 |
| pr-reviewer | 14 |
| llm-expert | 5 |
| documentation-expert | 1 |
| **Total** | **151** |

Notes: `commit` (24 entries) and `pull-request` (21 entries) are the highest non-test
phases, reflecting the many sequential sign-offs emitted during the direct-commit drive.
`pr-reviewer` (14 entries) includes 11 of the 11 blockers concentrated in that phase.
`documentation-expert` ran on exactly 1 ticket (ticket 24 — the reference doc).

## Epic Facts

| Metric | Value |
|--------|-------|
| Ticket count | 29 |
| Completed leaf ACs (post-merge audit) | 24 |
| Genuine gaps remaining | 5 |
| Git merge commit | 981f4280c (squash, PR #337) |
| Files changed | 63 |
| Lines added | +9,982 |
| Lines deleted | -391 |
| Feedback entries — total | 151 |
| Feedback entries — blocker | 11 |
| Unit test files added | 20 |

## What Went Well

- **Core feature is complete and behaviorally tested.** All BO-2200a (policy gate), BO-2200b
  (verifier phase + suppression protection), and BO-2200d-1/d-2 (post-coder ordering) ACs
  shipped with dedicated unit tests. 24 of 29 leaf ACs are genuinely done.
- **Evidence-based audit found zero phantom-dones.** The `ac-audit` skill methodology
  (grep evidence map → green-test confirmation → parallel skeptical agents) validated that
  every "done" verdict was anchored to real code and a genuinely passing test. No xfail-masked
  or opposite-behavior cases were found.
- **Blocker at commit time surfaced a latent validation gap quickly.** The `registry_validator`
  rule A failure (missing `requires_verification: true` on the documentation-verifier template)
  was caught by the build gate before any CI run and was fixed in the same session.
- **List-form `delivers_to`/`expects_from` crash was caught and fixed within the same epic.**
  The AC-generator crash on v3 BA-authored `delivers_to` list form (BO-2200c-5) was
  discovered, fixed, and tested in one pass.
- **Two post-merge CI failures were precisely diagnosed and fixed.** The `test_bp_300e_6`
  (machine-parsed-producer contract) and `test_ac3` (vocab-parity section exclusion) failures
  were both deterministic and fixed in a single targeted commit, with no test regression.
- **Direct-commit drive was productive.** Bypassing the per-ticket epic drive allowed the
  implementation to move at code-first pace. The cost (reconciliation work) was manageable
  because the `ac-audit` skill provided a structured recovery path.

## Friction Points

- **FP-1: Per-ticket sign-offs and AC YAML store fields were never reconciled at merge time.**
  The per-ticket epic drive ran partially and then was abandoned in favour of direct branch
  commits. At merge, `work_status`, `implemented_by`, and `covered_by` in the AC YAML files
  were stale or absent. Recovery required a post-merge `ac-audit` session with four parallel
  verification agents. Tickets: all 29.

- **FP-2: `documentation-verifier` template was missing `requires_verification: true`.**
  The template declared `Edit` in its `tools:` list but lacked `requires_verification: true`.
  This triggered `registry_validator.py` rule A, which failed the `build.py` install-shims
  step and blocked the `Test suite (pytest)` required CI gate before any test ran. The
  failure was not detectable from the template file alone without reading the registry
  validator rules. Fixed in the finalization session.

- **FP-3: Two genuine post-merge CI test failures not caught on the branch.**
  (a) `test_bp_300e_6`: `documentation-verifier.md` lacked the `## Machine-Parsed Dispatch
  Output Contract` section required of every phase agent dispatched in the ticket phase order.
  (b) `test_ac3`: `test_ticket_frontmatter_guard.py::TestGuardrailYamlVocabularyContract`
  ran a vocab-parity check against `guardrail_gates.yaml` but did not exclude the new
  top-level sections `documentation_gates` and `surgical_removal_guard` that the branch
  introduced (only `flow_change_gates` was excluded). Both were invisible on the branch
  because the branch tests did not cover the combined state. Fixed in the finalization session.

- **FP-4: AC-store hygiene hook cascade at finalization.**
  Multiple pre-existing AC-store hygiene violations surfaced as hook blockers during the
  finalization commit drive: child-limit cap violations on BO-2200b/c ACs, incomplete parent
  `covered_by` back-links, and a schema-invalid `test_rationale` field. These violations
  existed before the epic drive began but were only discovered one-by-one as hooks fired
  at commit time. Each required a targeted fix commit, extending the finalization session.

- **FP-5: 5 genuine gaps left open at merge.**
  BO-2200c-3 (genre from parent L1), BO-2200c-3-i (fail-soft marker), BO-2200c-4-i
  (bare-path doc_links not surfaced), BO-2200d-2-i (real bug: `frontend-coder` absent from
  `_CANONICAL_PHASE_ORDER`), and BO-2200d-3 (sequence diagram deliverable) were
  implemented against incorrect assumptions or were genuinely not reached in the direct
  commit drive. They are open ACs requiring follow-up tickets.

## Knowledge Gaps Found

- **KG-1: No documented rule for AC store reconciliation when abandoning a per-ticket drive.**
  When a team pivots from a per-ticket epic drive to direct branch commits, there is no
  checklist item or convention requiring that `work_status` / `implemented_by` / `covered_by`
  fields be reconciled before the PR is opened. The gap was discovered only at post-merge
  audit time.

- **KG-2: `requires_verification: true` is a silent required field for any Edit-capable agent.**
  The constraint that any agent template declaring `Edit` (or `Write`) in its `tools:` list
  must also carry `requires_verification: true` is not documented in `CLAUDE.md` or the
  agent template authoring how-to. The `registry_validator` enforces it, but agents
  (including `llm-expert`) have no in-template reminder.

- **KG-3: New top-level config sections require vocabulary-parity test exclusion updates.**
  Adding a top-level policy section (e.g., `documentation_gates`, `surgical_removal_guard`)
  to `guardrail_gates.yaml` requires a corresponding exclusion entry in
  `test_ticket_frontmatter_guard.py::TestGuardrailYamlVocabularyContract`. This is not
  documented anywhere, so failures surface only post-merge when `origin/main`'s stricter
  parity tests combine with the branch's new sections.

- **KG-4: AC-store hygiene should be validated in bulk before epic finalization.**
  The child-limit, `covered_by` back-link, and `test_rationale` schema checks are enforcement-
  only (hooks fire at commit time). There is no pre-flight script that validates the entire
  epic's AC YAML set before the finalization drive begins, so hygiene violations are discovered
  serially rather than in a single audit pass.

- **KG-5: `frontend-coder` is absent from `_CANONICAL_PHASE_ORDER` (real bug, AC BO-2200d-2-i).**
  `generate_ticket_from_ac.py`'s `_CANONICAL_PHASE_ORDER` list does not include
  `frontend-coder`. On multi-coder tickets where the phase sequence includes `frontend-coder`,
  `documentation-verifier` is not adjacent to `commit`, violating the BO-2200d-2 ordering
  invariant. This is a genuine code gap, not just a documentation gap.

## Subagent Quality Trends

No supervisor feedback entries found for this epic (supervisors may pre-date
EPIC-SupervisorFeedback or no adjudication events occurred during this drive).

## Unresolved Feedback

There are 151 unresolved feedback entries in feedback.jsonl.
Run `/feedback-review` to triage them before closing the epic branch.

## Proposed Improvements

### KI-1: AC-store reconciliation when abandoning per-ticket drive

**Proposed addition to CLAUDE.md — "Pre-Drive Checklist" section:**

```diff
+### AC-store reconciliation when pivoting to direct-commit drive
+
+**What to check:** If you abandon a per-ticket epic drive in favour of direct
+branch commits, reconcile the AC YAML store fields for every affected AC
+**before opening the PR** — not post-merge. Required fields:
+
+- `work_status: done` (or `gap` for genuinely unfinished work)
+- `implemented_by: [<commit-sha or PR ref>]` — the real commit that
+  contains the implementation
+- `covered_by: [<test-file path>]` — the passing unit test that exercises
+  the AC's behavior
+
+**Why this matters:** Skipping reconciliation at merge time requires a
+post-merge `ac-audit` skill run (four parallel verification agents, full
+green-test confirmation pass) to determine the true state. The audit takes
+significantly longer than in-line reconciliation, and the store is left in
+an inconsistent state during the window between merge and audit completion.
+(Source: EPIC-DocumentationCoverageGuarantee FP-1, 2026-08-10.)
```

Routing: `CLAUDE.md-inline` (Step 4 — project-wide implementation rule that every agent driving an epic needs to know; fits as a checklist item in the Pre-Drive Checklist section).

---

### KI-2: Agent templates with Edit tool must declare `requires_verification: true`

**Proposed addition to CLAUDE.md — "Implementation Conventions" section:**

```diff
+### Agent templates — `requires_verification: true` is mandatory when Edit or Write is in tools
+
+Any agent template (`templates/agents/*.md`) that lists `Edit` or `Write` in its
+`tools:` frontmatter field MUST also declare `requires_verification: true`.
+Omitting this flag triggers `registry_validator.py` rule A, which fails
+`build.py`'s `install_shims` step. Since `install_shims` runs as part of the
+pytest setup build guard, a missing flag blocks the required `Test suite (pytest)`
+CI gate before any test executes — making the failure appear as a build failure
+rather than a template authoring error.
+
+Verify after authoring any new agent template:
+```bash
+grep -n "requires_verification\|Edit\|Write" templates/agents/<new-agent>.md
+```
+
+(Source: EPIC-DocumentationCoverageGuarantee FP-2, 2026-08-10.)
```

Routing: `CLAUDE.md-inline` (Step 4 — short project-wide rule; the condition and check command fit in one paragraph that every agent authoring templates needs).

---

### KI-3: New top-level `guardrail_gates.yaml` sections require parity-test exclusion updates

**Proposed addition to CLAUDE.md — "Implementation Conventions" section:**

```diff
+### guardrail_gates.yaml — exclude new top-level sections from vocab-parity tests
+
+`test_ticket_frontmatter_guard.py::TestGuardrailYamlVocabularyContract` runs a
+`change_target` vocabulary-parity check against `guardrail_gates.yaml`. When a
+branch introduces a new **top-level** policy section (not a `change_target` vocab
+entry — e.g. `documentation_gates`, `surgical_removal_guard`), add that section
+name to the `_non_target_sections` exclusion set in that test class before
+committing. Failing to do so produces a post-merge CI failure: the new section
+looks like a malformed `change_target` entry to the test, but the failure only
+surfaces after `origin/main` merges the stricter form of the test.
+
+(Source: EPIC-DocumentationCoverageGuarantee FP-3, 2026-08-10.)
```

Routing: `CLAUDE.md-inline` (Step 4 — short project-wide rule about a specific test file and a specific invariant; every coder working on guardrail config needs it).

---

### KI-4: AC-store hygiene pre-flight before epic finalization

**Proposed addition to CLAUDE.md — "Pre-Drive Checklist" section:**

```diff
+### AC-store hygiene — bulk pre-flight before finalization drive
+
+**What to check:** Before running a finalization drive (or any sequential commit
+batch that will fire AC-store hooks), validate the entire epic's AC YAML files
+in bulk for known hygiene violations:
+
+1. Child-limit cap — no composite AC has more children than the configured cap.
+2. `covered_by` back-links — every leaf AC that declares `implemented_by` also
+   carries at least one `covered_by` entry pointing to a test file.
+3. Schema validity — no AC carries a field with an invalid type (e.g.,
+   `test_rationale` must be a string, not a list).
+
+Run the AC schema validator against the epic's AC directory before opening a
+finalization PR:
+```bash
+python scripts/ac_store/validate_ac_schema.py docs/acceptance-criteria/<component>/
+```
+
+**Why this matters:** When hygiene violations exist, the commit-time hooks surface
+them one-by-one on each commit attempt, requiring a separate targeted fix commit per
+violation. A bulk pre-flight turns a serial hook cascade into a single batch fix.
+(Source: EPIC-DocumentationCoverageGuarantee FP-4, 2026-08-10.)
```

Routing: `CLAUDE.md-inline` (Step 4 — adds a concrete pre-flight check item with a command; fits as one checklist block in the Pre-Drive Checklist section that already carries similar entries).

---

### KI-5 (Bug): `frontend-coder` missing from `_CANONICAL_PHASE_ORDER` — open gap BO-2200d-2-i

This is a real bug in `scripts/ac_store/generate_ticket_from_ac.py`, not a documentation
gap. `frontend-coder` is absent from `_CANONICAL_PHASE_ORDER`, so on any multi-coder
ticket including `frontend-coder`, `documentation-verifier` is placed just before commit
rather than adjacent to it, violating the BO-2200d-2 ordering invariant.

**Proposed routing:** `ticket-body` — this requires a follow-up AC (or a direct fix ticket
under BO-2200d-2-i). No CLAUDE.md rule change is proposed for this item; it should be
tracked as open work rather than documented as an accepted limitation.

**No diff is presented for this item** — it is a code bug requiring an implementation fix,
not a process rule to add. Create a follow-up ticket referencing AC BO-2200d-2-i before
closing the epic branch.
