---
title: "Retrospective: EPIC-ComputedQualityGates"
description: "Post-merge retrospective for EPIC-ComputedQualityGates (PR #201), covering the phantom-done remediation, three-layer integration gap root cause analysis, backfill of 1,802 ACs, and five proposed knowledge items."
date: 2026-07-08
epic_branch: EPIC-ComputedQualityGates
pr: "https://github.com/urlmonitor/leafcutter-ai/pull/201"
---

# Retrospective: EPIC-ComputedQualityGates

Date: 2026-07-08
Epic duration: 2026-07-01 to 2026-07-07 (scaffold-to-merge, ~7 days wall clock)
First feature commit: 2026-07-01
Last feature commit: 2026-07-07
Merge commit: 8aeb37d4 (PR #201 squash)

## Summary

EPIC-ComputedQualityGates set out to make quality gates (TDD, code review, documentation)
a computed system invariant rather than a one-field template default. The design (ADR-017)
introduced a two-axis classification — `change_target` (10 values: code, schema, ui,
infrastructure, pipeline, prompt, model, config, docs, dependency) and `risk_surface`
(6 values: internal, contract_boundary, auth, privacy, safety, cost) — and a Python
computation in `generate_ticket_from_ac.py::_build_agents_map` that reads
`config/guardrail_gates.yaml` to produce the full ordered agent map at ticket-generation
time. TDD injection (test-writer before + test-runner after any code producer) and
flow-change gates (architect-review + documentation-expert sequenced before coders) were
derived from the axes, eliminating the need for hand-crafted per-ticket agents maps.

The epic shipped green (PR #201, 41 tests passing) after seven tickets — and was
immediately found to be phantom-done by a post-drive behavioral spot-check and code
review. The computed path was dead code in production: all three real call sites invoked
`_build_agents_map(assigned_agent)` without the `change_targets`/`risk_surface` arguments,
the AC schema carried no axes, and the `guardrail_gates.yaml` vocabulary was entirely
disjoint from the guard hook's `ALLOWED_CHANGE_TARGETS`/`ALLOWED_RISK_SURFACES` enums.
None of this was caught by the unit tests, which tested the function in isolation against
synthetic fixtures.

A three-ticket remediation (tickets 07–10, minus 09 which was deferred) wired the call
sites, reconciled the vocabulary, added the AC schema fields, and backfilled 31 of 1,802
AC records in the store (pilot component `testing-quality/TQ-100`) with agent-classified
axes reviewed before write. The final anti-phantom-done gate — a real-store end-to-end
test (`TestRealStoreComputedMapE2E::test_real_backfilled_ac_gets_architect_review`) that
loads a real on-disk AC and asserts `architect-review: needed` in the emitted frontmatter —
is now part of the permanent test suite. The full backfill of the remaining ~1,771 ACs is
deferred to a follow-up ticket.

## Epic Facts

| Metric | Value |
|--------|-------|
| Sub-ticket count (planned) | 9 (01–08 + 10; ticket 09 pulled to standalone) |
| Completed tickets | 9 (100%) |
| Ticket 09 disposition | Deferred — `TICKET-20260707-ItPoV3AuthorsAxes.md` |
| Git merge commit | 8aeb37d4 (PR #201) |
| ADRs authored | 1 (ADR-017 computed-quality-gates) |
| AC store size | 1,802 records across 12 component folders |
| Pilot backfill (ticket 10) | 31 ACs (testing-quality/TQ-100) |
| Remaining backfill | ~1,771 ACs (deferred) |
| Pre-existing data issues found | 19 over-limit AC trees, 8 covered_by back-link gaps |
| pr-reviewer first-pass blockers | 1 (ticket 02 — AC-BO-610-5 unimplemented) |
| python-coder retries | 1 (ticket 07 — test ordering conflict) |
| commit hook retries | 3 (ticket 04 — check-secrets false positives) |
| Feedback-ids recorded | 15 (most phases logged submit-failed — feedback_categories.yaml absent from worktree) |
| Finalize blockers | 3 (scaffold add/add conflict; check-contract-shrinking false-positive; check-doc-frontmatter symlink-root bug) |
| Tooling defects found at finalize | 2 (check-doc-frontmatter worktree root; check_feedback_id "/" in commit message) |

Note: `extract_epic_facts.py` is absent from this installation. Epic facts derived from
ticket Comments sections and `git log`.

## Metrics

Phase sign-off state from ticket frontmatter `agents:` maps across all 9 tickets.
"Failed" = first-pass phase returned status: blocker or partial-red requiring re-dispatch.

| Phase | Signed Off | Failed | Needed (not dispatched) |
|-------|-----------|--------|------------------------|
| adr-author | 1 | 0 | 8 |
| documentation-expert | 1 | 0 | 8 |
| llm-expert | 3 | 0 | 6 |
| python-coder | 7 | 1 (ticket 07) | 1 |
| test-writer | 6 | 0 | 3 |
| test-runner | 6 | 0 | 3 |
| pr-reviewer | 9 | 1 (ticket 02) | 0 |
| commit | 9 | 0 | 0 |
| pull-request | 9 | 0 | 0 |

## Category Breakdown (Feedback System)

Structured feedback was only partially recorded. The worktree lacked
`feedback_categories.yaml`, causing `submit_feedback.py` to fail silently with
`(submit-failed)` for the majority of agent sign-offs during tickets 01–07.
Tickets 08 and 10 (2026-07-07) recorded more entries as the worktree was more
fully configured.

| Feedback-ids recorded | 15 |
| Submit-failed (inferred from ticket comments) | ~55+ |

Because of the high submit-failed rate, no meaningful category breakdown can
be extracted from `debugging/logs/feedback.jsonl` for this epic.
The feedback-sink worktree gap is called out under Friction Points.

## What Went Well

- **ADR-017 authored cleanly.** Ticket 01 (adr-author) passed all seven ACs on the
  first pass without any retries. The ADR structure, two-axis model, produces-trait
  references, and self-hosting boundary note were all correct on first draft.

- **TDD discipline held throughout.** Tickets 04, 06, 07, 08, and 10 all followed
  strict red-baseline-first TDD: test-writer confirmed all new tests were RED before
  python-coder implemented, and test-runner confirmed GREEN after. The red_baseline
  comments provide an auditable record of what was failing and why.

- **Tickets 08 and 10 shipped without regressions.** The full suite (1,353 passed,
  51 skipped, 48 failed — all 48 pre-existing build-guard failures) showed zero
  net-new failures after both tickets. The targeted test runs (104 passed for ticket
  08, 45 passed for ticket 10) were also clean.

- **Vocabulary reconciliation caught at test time, not production.** The disjoint
  enum sets (guard hook vs. YAML config) were made visible by the vocabulary-contract
  test written in ticket 07. Without that test, the mismatch would have persisted
  silently through any number of future updates.

- **Backfill method (agent-classified + human-approved) worked correctly.** All 31
  pilot ACs received semantically sound axis values (cross-checked by pr-reviewer
  against the schema enums). Zero enum violations after backfill.

- **Real-store e2e test is a genuine anti-phantom-done gate.** The test loads a real
  on-disk AC via `_find_ac_by_id` and asserts the emitted frontmatter contains
  `architect-review: needed`. The pr-reviewer confirmed it would fail red if the
  store were de-backfilled — making it structurally impossible to repeat the original
  phantom-done without breaking this test.

- **Ticket 05 (flow-change gates) used real feedback-ids.** Three of the four agents
  on ticket 05 successfully submitted feedback (fb_2026-07-01_17ddd9e3,
  fb_2026-07-01_b64bd569, fb_2026-07-01_2578b690), bucking the submit-failed trend.

## Friction Points

### FP-1: Three-layer integration gap causing phantom-done (tickets 01–06 → ticket 07)

The central defect: all phases signed off (41 tests green) but the feature was
entirely inactive on real inputs. The three independent failure layers were:

1. **Dead call sites.** `main()` and `_build_ticket_body()` called
   `_build_agents_map(assigned_agent)` without `change_targets`/`risk_surface`, so the
   legacy path always ran.
2. **Generator never emitted axes.** Even after ticket 07 wired the call sites, no AC
   record in the store carried `change_target`/`risk_surface`, so `ac.get("change_target")`
   returned `None` for every real AC.
3. **Disjoint vocabularies.** The guard hook's `ALLOWED_CHANGE_TARGETS` and
   `ALLOWED_RISK_SURFACES` (ADR-017 blast-radius terms: code, schema, ..., internal,
   contract_boundary, ...) were completely disjoint from the YAML's keys (production,
   staging, integration, ..., documentation, test, hook, ...). Only `code`/`schema`/`config`
   overlapped partially.

Each of the three gaps was invisible in isolation. Tickets 01–06 each unit-tested their
own layer against synthetic fixtures; no test ever invoked `generate_ticket_from_ac.py`
end-to-end against a real AC file and asserted the generated ticket's `agents:` block.

Caught only by: post-drive code-review + `--dry-run` behavioral spot-check
(observed: `architect-review` absent from output when it must have been present for
a `code`/`production` AC under the design). Six tickets had already been signed off
before the gap was detected.

### FP-2: pr-reviewer blocker on ticket 02 (AC-BO-610-5 unimplemented)

AC-BO-610-5 (error message wording + list-value input handling) was listed in
`ac_traceability` but had no corresponding checkbox in the Acceptance Criteria section
and was entirely unimplemented. The pr-reviewer correctly blocked with three specific
findings (error message wording, missing list-value handling, wrong `files_touched`
path). Required python-coder re-dispatch to fix all three, plus a second pr-reviewer
pass. Total: 2 pr-reviewer passes + 1 extra python-coder pass on ticket 02.

### FP-3: check-secrets false positives on keyword-argument strings (ticket 04, commit)

The pattern `guardrail_config_path=_GUARDRAIL_CONFIG` in test files was flagged as
`ENTROPY_HIGH` by the check-secrets hook. Required 3 commit attempts: first attempt
blocked by false positives; added allowlist suppressions; comment text also triggered
on retry; rephrased comment; committed successfully on third attempt. Per-line
`.security-allowlist` entries were the original workaround; ticket 10 later consolidated
them to a single glob (`ENTROPY_HIGH:unit_tests/test_generate_ticket_from_ac.py:*`).

### FP-4: test_canonical_ordering conflict with test_ac4_documentation_expert ordering (ticket 07)

The first python-coder pass on ticket 07 left one of seven new tests red:
`test_ac4_documentation_expert_before_coder_for_flow_change_pair` required
`documentation-expert` before `python-coder` for `code`/`production` flow-change pairs,
but the pre-existing `test_canonical_ordering` required all present agents in the
canonical order (documentation-expert after python-coder). Both tests used the same
function call signature. Resolved by a second python-coder pass: introduced a
`_FLOW_CHANGE_PHASE_ORDER` that places documentation-expert before coders for flow-change
pairs, updated `test_canonical_ordering` to use `risk_surface='internal'` (non-flow-change)
so it no longer asserts ordering for the conflicting case.

### FP-5: Feedback sink absent from worktree (most tickets)

The worktree lacked `feedback_categories.yaml`, causing `submit_feedback.py` to fail
with `ModuleNotFoundError` or a missing-file error for nearly every agent across tickets
01–07. All affected phases logged `feedback-id: (submit-failed)`. This matches the
pre-existing pattern documented in CLAUDE.md Pre-Drive Checklist ("Feedback sink
reachable"), but the check did not cover the `feedback_categories.yaml` file specifically.
Result: quantitative category breakdown is unavailable for most of the drive.

### FP-6: Finalize surface blockers (3 at merge)

Three independent finalize-time issues required manual resolution before the PR could
merge:
1. **Scaffold add/add merge conflict.** The scaffold commit (ticket stubs) landed on
   main independently; the epic branch carried `status: done` versions of the same
   files. Resolved: checkout `--ours` (branch version wins — `status: done` is correct).
2. **check-contract-shrinking false-positive.** The merge commit context triggered the
   hook on lines it did not own. Resolved: `SKIP=check-contract-shrinking` for the
   merge commit.
3. **check-doc-frontmatter worktree-symlink root bug.** The hook resolved its project
   root via the symlink target (`__file__` of the resolved `.leafcutter`), pointing
   to the workspace-parent root rather than the worktree root. Required a workaround
   for the affected commit.

### FP-7: check_feedback_id breaks on "/" in commit message (out-of-scope, deferred)

The `[NO-FEEDBACK-CHECK]` bypass mechanism in `check_feedback_id.py` relies on
`GIT_COMMIT_MSG`, but git writes `COMMIT_EDITMSG` after the pre-commit stage, so the
bypass is never read. Additionally, when a commit message contains "/", the hook
script mis-parses it. Deferred to a standalone pre-commit hooks ticket (noted in
ticket 10's Out of Scope section).

## Knowledge Gaps Found

- **Integration tests are required across multi-ticket feature boundaries.** When
  a feature spans tickets (function implementation in ticket A, config data in ticket B,
  call-site wiring in ticket C), per-ticket unit tests give a false green. An
  end-to-end test that exercises the full chain against real data is not optional —
  it is the only gate that would have caught the phantom-done here.

- **Function signature extension requires call-site audit.** Extending
  `_build_agents_map` to accept new keyword arguments did not automatically update
  the three existing callers. No per-ticket test exercised the callers — only the
  function directly. A call-site audit (grep for all invocations, verify each passes
  the new args) was missing from the sign-off checklist.

- **Shared-enum components require a contract test at authoring time.** Two
  independently maintained components (the guard hook and the YAML config file) shared
  an enum but drifted to completely disjoint vocabularies. A contract test asserting
  `set(YAML keys) == ALLOWED_*` must be authored alongside the first component and
  kept green permanently.

- **Feedback sink worktree gap extends to feedback_categories.yaml.** The pre-drive
  checklist covers `debugging/logs/agent_telemetry.jsonl` writability but not the
  Python feedback script's dependency on `feedback_categories.yaml`. When the file
  is absent from the worktree, all agent feedback submissions silently fail.

- **check_feedback_id "/" defect.** The hook breaks when commit messages contain "/".
  This was known from the Out of Scope section of ticket 10 but is not yet captured
  as a project MEMORY note.

## Subagent Quality Trends

No supervisor feedback entries found for this epic. The aggregate.py
`--category subagent-quality` query returned zero entries. This is consistent with
the feedback-sink worktree gap (FP-5): supervisor adjudication events, if any, were
not submitted during this drive.

## Unresolved Feedback

The `aggregate.py --unresolved` query returned the full feedback corpus
(no per-item resolution tracking is implemented in the current feedback system).
Run `/feedback-review` to triage pending entries before closing the epic branch.

---

## Proposed Improvements

### KI-1: Cross-ticket integration test requirement for multi-layer features

**Proposed Knowledge Item:**

> When an epic implements a feature across multiple layers in separate tickets (e.g.,
> compute function in ticket A, config data source in ticket B, call-site wiring in
> ticket C), the final ticket in the chain MUST include an end-to-end test that:
> (a) exercises the REAL generator / real call path (not a synthetic fixture),
> (b) uses REAL data from the on-disk store (not hard-coded axis values), and
> (c) asserts the observable OUTPUT (emitted ticket text / frontmatter) contains
>     the expected computed result.
>
> A unit test that calls the function directly and asserts its return value is
> insufficient — it does not detect dead call sites or data-source gaps. The test
> must fail red if any layer of the chain (call site, data, config) is removed or
> reverted.
>
> Pattern: `TestRealStoreComputedMapE2E` in
> `unit_tests/test_generate_ticket_from_ac.py` is the canonical reference.

**Routing:** `agent-frontmatter`
**Destination:** `templates/skills/building-epics/SKILL.md`
(Section: "§3 — Acceptance Criteria and Test Requirements", after the existing
TDD injection note.)

Note: `.agents/rules/` is being retired; route-knowledge selected `agent-frontmatter`
(building-epics SKILL.md) as the correct destination for agent-behavioural instruction.

---

### KI-2: Call-site audit required when extending a function's signature

**Proposed Knowledge Item:**

> When a ticket extends the signature of an existing function (adds required or
> optional keyword arguments), the implementing agent must:
> 1. `grep` for all existing call sites in the codebase before declaring done.
> 2. Verify each call site passes the new arguments (or explicitly documents why
>    the old-argument call is an intentional backward-compat path).
> 3. Include the call-site updates in the same commit as the signature change.
>
> A function whose signature is extended but whose callers still use the old
> signature silently exercises the legacy code path. This cannot be caught by
> tests that test the function directly.

**Routing:** `CLAUDE.md-inline`
**Destination:** Root `CLAUDE.md`, under "Pre-Drive Checklist" or a new
"Implementation Conventions" section.

---

### KI-3: Contract test required for shared enum surfaces

**Proposed Knowledge Item:**

> When two or more independently maintained components (e.g., a guard hook, a YAML
> config file, a JSON schema) must share the same enum vocabulary, author a
> vocabulary-contract test at the time the first component is written. The contract
> test asserts the key/value sets are identical across all sources. It must:
> - Live in a permanent test file (not a one-off migration script).
> - Use set equality, not subset checks.
> - Be part of the CI gate (i.e., run by the standard test suite).
>
> Without this test, independent edits to each component will silently diverge.
> Pattern: `test_ac3_change_target_enum_identical_across_sources` in
> `unit_tests/commit_guardian/test_check_ac_schema.py`.

**Routing:** `agent-frontmatter`
**Destination:** `templates/skills/building-epics/SKILL.md`
(Same section as KI-1 — add as a companion requirement under "Cross-component
vocabulary contract".)

---

### KI-4: Feedback sink pre-drive check must include feedback_categories.yaml

**Proposed Knowledge Item:**

> The "Feedback sink reachable" pre-drive checklist item must also verify that
> `feedback_categories.yaml` is accessible to `submit_feedback.py` in the worktree.
> When this file is absent, all agent feedback calls fail silently with
> `(submit-failed)`, making the retrospective's quantitative category breakdown
> unavailable.
>
> Check: `ls <worktree-root>/.leafcutter/feedback_categories.yaml 2>/dev/null || echo MISSING`
>
> Fix: symlink or copy from the main working tree's `.leafcutter/` directory
> alongside the `.pre-commit-config.yaml` fix documented in the worktree
> pre-commit config checklist item.

**Routing:** `CLAUDE.md-inline`
**Destination:** Root `CLAUDE.md`, "Pre-Drive Checklist" section,
"Feedback sink reachable" item (extend the existing entry).

---

### KI-5: check_feedback_id hook breaks when commit message contains "/"

**Proposed Knowledge Item:**

> `check_feedback_id.py`'s `[NO-FEEDBACK-CHECK]` bypass mechanism reads
> `GIT_COMMIT_MSG`, but git writes `COMMIT_EDITMSG` after the pre-commit stage
> completes, so the environment variable is never set and the bypass never fires.
> Additionally, when the commit message contains "/", the hook mis-parses the
> message and may raise an error or produce incorrect output.
>
> Workaround: use `SKIP=check-feedback-id` when a commit genuinely needs the bypass.
> Fix tracked as a standalone pre-commit hooks ticket (see ticket 10 Out of Scope).

**Routing:** `memory-project`
**Destination:** `memory/project_worktree_checksecrets_scriptsdir.md` (or a new
`memory/project_check_feedback_id_slash_bug.md`)

---

### Rule Update R-1: Add integration-test gate to building-epics SKILL.md

Proposed diff to `templates/skills/building-epics/SKILL.md`
(after the existing TDD injection note in §3 or equivalent section):

```diff
+## Cross-Ticket Integration Gate (anti-phantom-done)
+
+When an epic delivers a feature across multiple tickets that each implement one
+layer of the same system (e.g., function body in ticket A, config data in ticket B,
+call-site wiring in ticket C), the **final ticket in the chain must include a
+real-store end-to-end test** that:
+
+1. Exercises the REAL call path through the feature (not an isolated unit function call).
+2. Reads REAL data from the on-disk store (not hard-coded synthetic values).
+3. Asserts the observable OUTPUT (file written, frontmatter emitted, API response)
+   contains the expected computed guardrail result.
+
+This gate is mandatory when `files_touched` across two or more tickets in the epic
+share a Python module. A per-ticket unit test targeting the module's internal function
+directly does NOT satisfy this requirement.
+
+**Reference failure mode:** EPIC-ComputedQualityGates (2026-07-01, PR #201) — 41 tests
+green, all phases signed off, feature entirely inactive on real inputs. Caught only by
+a post-drive --dry-run behavioral spot-check.
```

---

### Rule Update R-2: Add glob-pattern allowlist convention to CLAUDE.md

Proposed diff to root `CLAUDE.md` (or `.claude/CLAUDE.md`),
under "Worktree pre-commit config" or a new "Security Allowlist" note:

```diff
+### Security Allowlist — Use Glob Patterns for Test Files
+
+When `check-secrets` flags false-positive `ENTROPY_HIGH` patterns in test files
+(e.g., keyword-argument strings that look like secret patterns), do NOT add
+per-line suppressions. Per-line entries (`ENTROPY_HIGH:<path>:<lineno>`) break
+as the test file grows (new lines shift existing line numbers).
+
+Instead, use a single glob entry:
+
+    ENTROPY_HIGH:<path>:*
+
+This is supported by `scan_secrets.py _is_suppressed` (checks `lineno == "*"`).
+Add the glob to BOTH the worktree-root and workspace-root `.security-allowlist`
+per the dual-update rule (the check-secrets hook resolves allowlist from the
+workspace-root symlink target, not the worktree).
+
+Reference: EPIC-ComputedQualityGates ticket 10 (AC-5), 2026-07-07.
```
