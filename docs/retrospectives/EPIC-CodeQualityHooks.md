---
title: "Retrospective: EPIC-CodeQualityHooks"
description: "Epic retrospective for EPIC-CodeQualityHooks — jscpd duplicate-code detection and diff-cover test-coverage enforcement hooks."
date: 2026-06-22
epic_branch: EPIC-CodeQualityHooks
pr: "https://github.com/urlmonitor/leafcutter-ai/pull/119"
---

# Retrospective: EPIC-CodeQualityHooks

Date: 2026-06-22
Epic duration: 2026-06-18 (first commit a31824f) to 2026-06-22 (merge 16226aa)
Commits: ~73 on epic branch (a31824f..ae6ab10), plus post-merge fix 6cc4ebd
Merge commit: 16226aa73e978f675cfe90822cd2d9069776f57d
PR: #119

## Summary

EPIC-CodeQualityHooks implemented AC GE-100: pre-commit hooks that detect
duplicate code and gate test coverage on changed lines. The epic delivered
four groups of work across 17 tickets:

1. **jscpd duplicate-code hook** (GE-100a through GE-100c-1) — Fail-open
   binary-absent guard, version 4.x rejection with actionable error, WSL2
   staged-only mode, clone-pair reporting filtered to staged files, and
   strict-mode blocking with measured/threshold percentage output.

2. **diff-cover test-coverage hook** (GE-100d through GE-100f-1) — Fail-open
   when binary or coverage.xml is absent, compare-branch fallback chain,
   warn-only advisory mode, strict-mode blocking, stale-artifact warning, and
   shallow-clone detection with HEAD~1 fallback.

3. **Onboarding wizard opt-in** (GE-100g, GE-100g-1) — A new
   `onboard_hook_opt_in.py` script that detects jscpd and diff-cover on PATH,
   prompts the user in TTY environments, atomically sets the enabled flag in
   `commit_guardian.json`, and silently adds absent tools to the post-onboard
   optional-tools checklist.

4. **Disabled-by-default shipping** (GE-100h, GE-100h-1) — Both hooks land
   with `enabled: false` in all three copies of `commit_guardian.json`; the
   `build_precommit_config()` function in `build_precommit.py` was extended to
   filter out disabled hooks so they are never emitted to
   `.pre-commit-config.yaml` until explicitly enabled.

All 17 tickets closed with status done. No blocker comments or handoff
comments were recorded by the structured fact extractor. A post-merge fix
(6cc4ebd) was required for a template-drift issue discovered during the
post-build spot-check; see Friction Points.

## Epic Facts

| Metric | Value |
|--------|-------|
| Ticket count | 17 |
| Completed tickets | 17 (100%) |
| Git commits (epic branch) | ~73 feature commits + 2 merge commits + 1 post-merge fix |
| Blocker comments | 0 |
| Handoff comments | 0 |
| Post-merge fix commits | 1 (6cc4ebd) |
| Merge commit | 16226aa |
| PR | #119 |
| Pre-existing test failures at baseline | 25 (all pre_existing, zero regressions) |

Note: `extract_epic_facts.py` is present and was run against the epic folder.
Git commit counts in that script reflect the worktree state (which had 0 at
extraction time because the branch was already merged); the counts above are
derived from `git log a31824f..ae6ab10`.

## Category Breakdown (Feedback System)

No structured feedback entries are tagged to EPIC-CodeQualityHooks in
`debugging/logs/feedback.jsonl`. The corpus contains 57 entries, all with
category `complete`, covering earlier epics (EPIC-GoalToEpic and related).
Quantitative category breakdown per ticket is unavailable for this epic.

## Metrics

Phase sign-off state derived from `extract_epic_facts.py` output:

| Phase | Signed Off | Failed | Not Needed |
|-------|-----------|--------|------------|
| test-writer | 17 | 0 | 0 |
| python-coder | 17 | 0 | 0 |
| test-runner | 17 | 0 | 0 |
| pr-reviewer | 17 | 0 | 0 |
| commit | 17 | 0 | 0 |
| pull-request | 17 | 0 | 0 |
| documentation-expert | 0 | 0 | 17 (not_needed) |
| sql-coder | 0 | 0 | 17 (not_needed) |

Zero failed phases across all 17 tickets. The adjudication ladder was never
triggered.

## What Went Well

- **Perfect phase completion.** All 17 tickets completed all assigned phases
  (test-writer, python-coder, test-runner, pr-reviewer, commit, pull-request)
  with zero failures. The adjudication ladder was not invoked once.

- **Pre-existing test failures correctly classified throughout.** Every
  test-runner sign-off explicitly identified the 11-25 pre-existing failures
  in `test_transform_hooks_and_autofix_emission.py` (caused by missing
  `transform_doc_frontmatter.py`, `transform_description_field.py`, and
  `check_exception_handling.py` scripts from earlier epics) as unrelated to
  the ticket in flight. No regressions were introduced by any of the 17
  tickets.

- **Error handling policy enforced throughout.** Every python-coder sign-off
  confirmed compliance with the four-rule error handling policy (external I/O
  wrapped, no bare `except`, no silent swallowing, no try/except on pure
  functions). pr-reviewer caught and flagged edge cases (e.g. temp-file
  cleanup `except OSError: pass` in GE-100b) but correctly did not block on
  intentional fail-open patterns.

- **AC tree structure corrected inline.** During the GE-100b commit phase the
  `check-ac-tree-limits` hook fired and triggered an AC tree split: GE-100d/e/f
  were renamed to GE-101a/b/c (and their children renamed correspondingly) to
  fix structural parent attribution. The commit agent resolved this without
  escalation.

- **Dependency sequencing worked as planned.** The 17-ticket dependency graph
  (dual chains: GE-100a → b → c → c-1 and GE-100d/101a → b → c → c-1, with
  GE-100g and GE-100h as independent roots) was respected throughout the drive
  with no ordering violations.

- **Three copies of commit_guardian.json kept in sync.** Every ticket that
  modified the hook configuration (scripts/, templates/scripts/, and
  templates/commit-guardian/ copies) updated all three locations. pr-reviewer
  verified multi-copy consistency on every relevant ticket.

- **Onboarding wizard integration clean.** The `onboard_hook_opt_in.py` module
  shipped as stdlib-only with no leafcutter package imports, no global
  mutations, and a composable result-dict return. The onboard agent template
  was updated with a deterministic Step 11b section.

- **EMU account constraint handled without escalation.** All 17 pull-request
  phases identified the EMU `gh pr create` block, fell back to the REST API
  or push-to-existing-PR path, and signed off cleanly. The first ticket
  (GE-100a) created PR #119 via the REST API; subsequent tickets pushed to
  the existing branch.

## Friction Points

- **Template-drift post-merge fix required (6cc4ebd — highest-severity
  finding).** After the epic merged, a post-build spot-check found that the
  jscpd hook template (`templates/scripts/commit_guardian/check_duplicate_code.py`)
  had drifted from the canonical `scripts/` copy: the `_extract_percentage()`
  function (GE-100c) and the measured%/threshold% blocking message were
  missing from the template. Because `build.py` deploys from `templates/`,
  consumers were receiving a jscpd hook that silently failed GE-100c. The fix
  also added 42 tests covering all 7 jscpd ACs (GE-100a through GE-100c-1) —
  the hook had previously shipped with zero dedicated test coverage. Root
  cause: no ticket was assigned to write a test file for `check_duplicate_code.py`;
  the test-writer phase was skipped on all jscpd tickets because
  `test_requirements` was empty (docs-only classification), even though the
  module itself is a Python implementation requiring unit tests.

- **Consistent `feedback-id: (submit-failed)` across most commit/pull-request
  phases.** The majority of commit and pull-request sign-off comments carry
  `feedback-id: (submit-failed)` rather than a real ID (e.g. `fb_2026-06-18_...`).
  This indicates the feedback sink submission failed on every commit/PR phase
  during the drive. The pre-drive feedback sink check was either skipped or the
  sink was unreachable.

- **test-writer phase systematically skipped for implementation tickets.**
  Fourteen of seventeen tickets had the test-writer phase skipped with
  "test_requirements empty — test-writer phase skipped." Many of these tickets
  implement real Python modules (`check_duplicate_code.py`,
  `check_diff_coverage.py`, `onboard_hook_opt_in.py`) that are not docs-only
  or config-only. The AC generation pipeline did not produce `## Test
  Requirements` blocks for these tickets, so the test-writer had no stubs to
  write. The post-merge fix demonstrates the gap: 42 tests had to be added
  after merge for code that had been "done" for days.

- **AC tree limits hook triggered mid-drive (GE-100b commit).** The
  `check-ac-tree-limits` pre-commit hook fired during the GE-100b commit
  phase, requiring an inline AC tree split (GE-100d/e/f → GE-101a/b/c).
  This mid-drive structural rename was handled automatically but was
  unplanned. The rename affected AC YAML file paths referenced by subsequent
  tickets (GE-100f references GE-101c), requiring pr-reviewer to flag the
  stale references.

- **Merge conflict in `commit_guardian.json` during finalization.** The
  `ae6ab10` pre-merge sync commit ("Merge remote-tracking branch
  'origin/main' into EPIC-CodeQualityHooks") resolved conflicts in
  `commit_guardian.json` (both the `scripts/` and `templates/` copies). The
  conflict arose because the main branch had accumulated changes to
  `commit_guardian.json` from other epics during the EPIC-CodeQualityHooks
  drive. The resolution was correct but required manual intervention at
  finalization time.

- **Duplicate `feedback-id` pattern on ticket-supervisor phase.** The
  `check-feedback-id` pre-commit hook repeatedly fired during commit phases to
  add `feedback-id:` fields to ticket-supervisor comment headings. This was a
  mechanical pre-commit fix that repeated on nearly every ticket, suggesting
  the ticket-supervisor template does not emit a `feedback-id:` line by
  default and the hook is enforcing a convention the template does not produce.

- **EMU account blocks `gh pr create` on every pull-request phase.** All 17
  pull-request phases encountered the EMU constraint and fell back to either
  the REST API or a push-to-existing-PR workaround. This is expected given the
  documented constraint but creates noise in every sign-off log.

## Knowledge Gaps Found

- **Implementation tickets generated without `## Test Requirements` blocks.**
  When AC generation produces tickets for Python hooks (`check_duplicate_code.py`,
  `check_diff_coverage.py`), the resulting ticket lacks a `## Test Requirements`
  section. The test-writer phase skips when this block is absent, and no
  dedicated unit test file is created. The post-merge fix showed that 42 tests
  were needed. The gap: the ticket generation pipeline needs to populate
  `## Test Requirements` for any ticket whose `files_touched` includes a
  `.py` file that is not a config or docs file.

- **Template parity is not mechanically verified before merge.** The
  post-merge fix (6cc4ebd) found that `templates/scripts/commit_guardian/
  check_duplicate_code.py` was missing `_extract_percentage()` — a function
  that had been in `scripts/commit_guardian/check_duplicate_code.py` since
  the GE-100c ticket. The pr-reviewer verified within-ticket template parity
  but did not catch the cumulative drift from earlier tickets. There is no
  automated check that `scripts/` and `templates/scripts/` stay in sync across
  the full epic.

- **Feedback sink pre-drive check was not performed.** The near-universal
  `feedback-id: (submit-failed)` on commit/pull-request phases means the
  feedback sink was unreachable for the entire drive. The pre-drive checklist
  includes a feedback-sink reachability probe but it was not run (or not
  verified). This is the same pattern that occurred in an earlier epic
  (TICKET-20260527-FeedbackSinkPreDriveCheck).

- **AC tree structure limits are not surfaced during epic planning.** The
  `check-ac-tree-limits` hook fired mid-drive on the GE-100b commit. This
  structural constraint (an L0 AC can have at most N direct L2 children) was
  not caught during AC authoring or epic scaffold generation. The mid-drive
  rename worked but added unplanned churn; an earlier detection pass at
  `/create-epic` time would prevent it.

## Subagent Quality Trends

No supervisor feedback entries found for this epic (the feedback corpus
contains 57 entries, all category `complete`, covering earlier epics; no
`subagent-quality` entries exist for EPIC-CodeQualityHooks). No adjudication
events occurred during this drive.

## Unresolved Feedback

The `aggregate.py --unresolved` output returned all 57 entries (the
script returns the full corpus when no `resolved` field is present in
entries). There are no entries specifically tagged to EPIC-CodeQualityHooks
to triage.

---

## Proposed Improvements

### KI-1: Test Requirements block required for all implementation tickets

**Problem:** Fourteen of seventeen tickets were classified "docs-only or
config-only" by ticket-supervisor and had their test-writer phase skipped
because `## Test Requirements` was absent from the ticket body. This
classification is incorrect for tickets whose `files_touched` includes
a non-trivial Python implementation file. The result was that
`check_duplicate_code.py` shipped with zero dedicated test coverage for
four days; 42 tests were added in a post-merge fix.

**Proposed Knowledge Item:**

```
When generating a ticket from an AC whose files_touched list includes
a .py file that is not a YAML/JSON config or a Markdown docs file,
the ticket generation pipeline (goal_to_epic.py / generate_ticket_from_ac.py)
MUST produce a populated ## Test Requirements section. The presence or
absence of ## Test Requirements drives the test-writer phase decision;
an absent block causes all tests to be silently skipped.

Rule: if ANY entry in files_touched matches *.py and does NOT match
  - docs/**
  - *.yaml / *.json (config)
  - tickets/**
then the ticket MUST contain a ## Test Requirements section with at
least one test stub entry.
```

Routing: `templates/agents/ticket-supervisor.md` (classification rule for
test-writer skip) and `scripts/generate_ticket_from_ac.py` (ticket scaffold
generation).

Note: `.agents/rules/` is being retired; route-learning selects the agent
template and the scaffold generation script as the correct destinations.

---

### KI-2: Script/template parity check required before epic merge

**Problem:** `scripts/commit_guardian/check_duplicate_code.py` and
`templates/scripts/commit_guardian/check_duplicate_code.py` diverged
during the drive — the template was missing `_extract_percentage()` and
the updated blocking message. `build.py` deploys from `templates/`, so
consumers received a downgrade. pr-reviewer caught per-ticket parity but
not cumulative drift across tickets.

**Proposed rule update (diff):**

```diff
--- a/templates/skills/building-epics/SKILL.md
+++ b/templates/skills/building-epics/SKILL.md
@@ finalize / pre-merge checks @@
+### Template parity check (mandatory before merge)
+
+When any script under `scripts/commit_guardian/` or `scripts/` has been
+modified during the epic drive, run a final parity diff before the merge
+commit:
+
+```bash
+diff -r scripts/commit_guardian/ templates/scripts/commit_guardian/
+```
+
+Any diff output indicates template drift that must be resolved before the
+branch is merged. The deploying file is templates/, not scripts/; a
+consumer receiving a build from a diverged template gets downgraded behavior.
+
+This check supplements per-ticket template sync verification — it catches
+drift introduced across multiple tickets where each ticket kept parity but
+later tickets silently overwrote or omitted earlier additions.
```

Routing: `templates/skills/building-epics/SKILL.md` (finalize / pre-merge
checklist section).

---

### KI-3: Feedback sink pre-drive probe was skipped

**Problem:** Nearly all commit and pull-request phase sign-offs carry
`feedback-id: (submit-failed)`, indicating the feedback sink was
unreachable for the entire drive. The pre-drive checklist mandates a
writability probe for `debugging/logs/agent_telemetry.jsonl` but it was
not executed (or the result was not acted on). This is a repeat of the
pattern documented in TICKET-20260527-FeedbackSinkPreDriveCheck.

**Proposed Knowledge Item (enforcement suggestion):**

```
The pre-drive feedback sink check (Pre-Drive Checklist §2 in CLAUDE.md)
must be performed and its output verified before invoking /build-feature.
If the probe returns a non-zero exit, the drive MUST NOT START.

Checklist item (to add to the pre-drive verification flow):
  - [ ] echo '{"probe":"pre-drive-check"}' >> debugging/logs/agent_telemetry.jsonl
    exits 0
  - [ ] Inspect the last 3 lines of feedback.jsonl to confirm recent writes

When the feedback sink is unreachable and the drive proceeds anyway,
post-drive retrospective data is degraded and post-merge triage is blind.
```

Routing: `leafcutter-ai/CLAUDE.md` Pre-Drive Checklist section (the check
is already documented; this KI adds an enforcement note that the drive must
be blocked, not merely warned, when the probe fails).

---

### KI-4: AC tree structure limits should be validated at create-epic time

**Problem:** The `check-ac-tree-limits` pre-commit hook fired mid-drive
(during the GE-100b commit) requiring an unplanned AC tree split. GE-100
had accumulated more direct L2 children than the hook allows, causing a
structural rename of GE-100d/e/f → GE-101a/b/c and all their children.
This churn was unplanned and required updating `implemented_by` references
in subsequent tickets.

**Proposed Knowledge Item:**

```
When scaffolding an epic via /create-epic, run the AC tree validation
check before generating the ticket stubs:

  python scripts/check_ac_tree.py --root <L0-AC-ID>

If the check returns a limit violation, split the AC tree before
generating ticket files. Mid-drive splits require renaming YAML files,
updating implemented_by references in all downstream tickets, and
re-running the check — all avoidable by catching the violation at
scaffold time.
```

Routing: `templates/agents/create-epic.md` (pre-scaffold validation step)
or the `create-epic` skill if one exists.

---

*All proposed changes above are presented as diffs/KI text for user approval.
No file has been modified. Type "yes" to apply each item, "skip" to skip, or
"edit" to revise.*
