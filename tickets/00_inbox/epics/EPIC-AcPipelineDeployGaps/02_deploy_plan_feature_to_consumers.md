---
title: "Deploy plan-feature.js to consumer installs via templates/workflows-js"
status: in_progress
components:
  - build_pipeline
  - workflow_deployment
created: 2026-06-16
depends_on: []
priority: high
origin_agent: BrainCandy
requires_diagram: false
requires_adr: false
agents:
  python-coder: signed_off
  test-writer: signed_off
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: signed_off
files_touched:
  - templates/workflows-js/plan-feature.js
  - scripts/workflows/plan-feature.js
test_requirements:
  tests:
    - name: test_build_workflow_scripts_includes_plan_feature
      path: tests/test_build_phases.py
      coverage: |
        Unit test verifying that build_workflow_scripts() copies plan-feature.js
        from templates/workflows-js/ to the output .claude/workflows/ directory.
    - name: test_plan_feature_deployed_in_consumer_config
      path: tests/test_build_phases.py
      coverage: |
        Integration test verifying that with config.workflows.enabled=true,
        plan-feature.js is present in the final deployment package.
---

# 02: Deploy plan-feature.js to Consumer Installs

## Goal

Make plan-feature.js available to consumer installs by placing it in templates/workflows-js/ so that build_workflow_scripts() deploys it alongside other workflow scripts. This closes a gap where /plan-feature works in local dev but fails in field deployments due to a missing deployment artifact.

## Context

**The Problem**

plan-feature.js (14 KiB, verified correct logic) currently lives in `scripts/workflows/plan-feature.js`. However, the build_workflow_scripts() function (scripts/build_phases.py:348) copies only from `templates/workflows-js/`, where plan-feature.js is absent.

**Why This Matters**

- Local dev works: developers run `/plan-feature`, which resolves directly from `scripts/workflows/plan-feature.js` (bypasses the build step).
- Consumer installations fail: consumers run `python leafcutter-ai/scripts/build.py --target-dir .` (deployment), which copies .js files only from `templates/workflows-js/`. Since plan-feature.js is absent from that directory, `/plan-feature` is not deployed. When a consumer user invokes `/plan-feature`, it fails with a missing-file error.

**Source of Truth**

The repository's workflow deployment pattern establishes `templates/workflows-js/` as the canonical source. Five workflow files already follow this pattern:
- build-epic.js
- build-ticket.js
- create-ticket.js
- finalize-feature.js
- quick-fix.js

plan-feature.js must join this pattern.

**Scope & Gates**

- Deployment is already gated on `config.workflows.enabled=true` (default false) and Claude Code >= 2.1.154. **These gates are correct and out of scope.**
- Do not modify build_phases.py:260 (build_workflow_scripts function signature or logic).
- Do not add new features to plan-feature.js; move it as-is, preserving all logic and side effects.

**Parallelism Constraint**

TICKET-03 (EPIC-AcPipelineDeployGaps/03) also modifies scripts/build_phases.py (ac-scanner skill deployment). Do not run TICKET-02 and TICKET-03 in the same parallel batch. Merge TICKET-02 first, then rebase TICKET-03.

## Acceptance Criteria

```gherkin
Feature: plan-feature.js deployment to consumer installs

  Scenario: Source file in canonical deployment location
    Given the plan-feature.js source file exists in scripts/workflows/plan-feature.js
    When the fix is applied
    Then plan-feature.js is also present in templates/workflows-js/
    And the file content is byte-identical to the source
    And no build step or integration test fails due to plan-feature.js

  Scenario: Build system discovers the deployed artifact
    Given a consumer's target project is being deployed via build.py --target-dir
    And config.workflows.enabled is set to true
    And Claude Code version >= 2.1.154
    When build_workflow_scripts() is invoked
    Then plan-feature.js is copied from templates/workflows-js/ to .claude/workflows/
    And the file appears in the final deployment manifest
    And no SHA-256 mismatch or corruption warning occurs

  Scenario: Consumer deployment end-to-end validation
    Given a test environment simulating a consumer install
    And config.workflows.enabled = true
    And Claude Code >= 2.1.154
    When the full build.py deployment completes
    Then /plan-feature command resolves to <consumer_root>/.claude/workflows/plan-feature.js
    And no file-not-found or import-resolution error is raised
    And the command signature matches the source version
```

## Sign-offs

- [x] python-coder — 2026-06-16 20:53
- [x] test-writer — 2026-06-16 09:00
- [x] pr-reviewer — 2026-06-16 21:30
- [x] commit — 2026-06-17 06:05
- [x] pull-request — 2026-06-17 08:07

## Comments

Hardened via /create-ticket. See EPIC-AcPipelineDeployGaps Master_Plan.md for epic context and parallelism constraints.

### 2026-06-16 09:00 — test-writer (status: ok)
feedback-id: fb_2026-06-16_0f983253
completion_manifest:
  test_build_workflow_scripts_includes_plan_feature_written: true
  test_plan_feature_deployed_in_consumer_config_written: true
  both_tests_are_red: true
  no_syntax_errors: true
Wrote two failing test stubs in tests/test_build_phases.py (new file). Both tests are RED (non-zero exit, 2 FAIL). Tests use CLAUDE_CODE_VERSION env var to bypass the version gate and assert plan-feature.js presence in .claude/workflows/. They will turn GREEN once python-coder copies scripts/workflows/plan-feature.js to templates/workflows-js/.

## Test Writer — Completion Report

### Tests Written
| File | Directory | Framework | Status |
|---|---|---|---|
| test_build_phases.py | tests/ | unittest | written |

### Verification Run
- Command: `python -m unittest discover -s tests -t . -p "test_build_phases.py"`
- Result: red (2 failures — expected; plan-feature.js absent from templates/workflows-js/)

### Notes
Both tests are properly red. The AssertionError messages clearly state the fix required.
No new directories were needed (tests/ already exists).

red_baseline:
  - test_name: test_build_workflow_scripts_includes_plan_feature
    file: tests/test_build_phases.py
    error: "AssertionError: False is not true : plan-feature.js was NOT deployed to /tmp/tmphy_euq4x/.claude/workflows/plan-feature.js. Ensure templates/workflows-js/plan-feature.js exists."
  - test_name: test_plan_feature_deployed_in_consumer_config
    file: tests/test_build_phases.py
    error: "AssertionError: False is not true : Consumer deployment: plan-feature.js absent from /tmp/tmpcb0tlb2k/.claude/workflows/plan-feature.js. templates/workflows-js/plan-feature.js must be present for build_workflow_scripts() to deploy it to consumers."

### 2026-06-16 20:53 — python-coder (status: ok)
feedback-id: fb_2026-06-16_dffa2fff
completion_manifest:
  plan_feature_js_copied_to_templates: true
  source_file_intact_as_fallback: true
  build_phases_glob_verified: true
  red_baseline_tests_green: true
Copied scripts/workflows/plan-feature.js to templates/workflows-js/plan-feature.js (14,291 bytes, byte-identical). Confirmed scripts/build_phases.py:348-357 uses templates/workflows-js/ and globs *.js. Both red_baseline tests are now GREEN (2 tests, 0 failures, 0.043s).
red_baseline_results:
  - test_name: test_build_workflow_scripts_includes_plan_feature
    result: green
  - test_name: test_plan_feature_deployed_in_consumer_config
    result: green

### 2026-06-16 21:30 — pr-reviewer (status: ok)
feedback-id: fb_2026-06-16_5acc08a6
completion_manifest:
  change_minimal_and_surgical: true
  file_byte_identical: true
  build_phases_py_unmodified: true
  ticket_explains_gap_and_parallelism: true
  both_tests_green: true
  no_high_confidence_findings: true
Reviewed staged diff (3 files, 638 insertions): templates/workflows-js/plan-feature.js (new, byte-identical to source — SHA-256 a058e64c confirmed), tests/test_build_phases.py (new, 2 tests both GREEN in 0.048s), and ticket sign-off edits. scripts/build_phases.py has zero staged or unstaged changes. Ticket body clearly describes the deployment gap and TICKET-03 parallelism constraint. No high- or medium-confidence findings.

## Escalation

Branch: none
Reason: not escalated: zero medium findings (threshold > 3); all checklist items passed cleanly.

### 2026-06-17 06:05 — commit (status: ok)
feedback-id: fb_2026-06-17_commit_02
completion_manifest:
  staged_files_verified: true
  commit_created: true
  precommit_hooks_passed: true
  conventional_commit_format: true
Committed 3 staged files on branch EPIC-AcPipelineDeployGaps: templates/workflows-js/plan-feature.js (new, 366 lines), tests/test_build_phases.py (new, 213 lines), and ticket sign-offs. Commit message: feat(deploy): add plan-feature.js to templates/workflows-js for consumer installs.

### 2026-06-17 08:07 — pull-request (status: ok)
feedback-id: fb_2026-06-17_pullrequest_02
completion_manifest:
  pr_exists: true
  branch_pushed: true
  pr_url: https://github.com/urlmonitor/leafcutter-ai/pull/88
  pr_state: OPEN
  commits_pushed: true
PR #88 already existed (EPIC-AcPipelineDeployGaps: retire create-ticket.js and document canonical /plan-feature + /build-ac path). Pushed 2 new commits (2339197, 386fe42) to origin/EPIC-AcPipelineDeployGaps. Branch is now up to date with remote. No new PR was needed.

## Implementation Tasks

### python-coder

- [x] **Copy** plan-feature.js from `scripts/workflows/plan-feature.js` to `templates/workflows-js/plan-feature.js` (do NOT move — keep source as fallback for now).
  - Command: `cp scripts/workflows/plan-feature.js templates/workflows-js/plan-feature.js`
  - Verify file size, encoding, and shebang match exactly (if present).
- [x] Confirm scripts/build_phases.py:348 correctly references `templates/workflows-js/` and will pick up the new file via the glob pattern on line 357: `workflows_js_src.glob("*.js")`.
- [x] Run the build locally to confirm zero errors or warnings related to workflows deployment:
  - Command: `python leafcutter-ai/scripts/build.py --target-dir /tmp/test-consumer-install --dry-run` (or equivalent in your environment).
  - Verify plan-feature.js appears in the dry-run file list.
- [x] Do NOT remove scripts/workflows/plan-feature.js until test-writer confirms the tests pass (keep source intact for rollback).

### test-writer

- [x] **Create test_build_workflow_scripts_includes_plan_feature** in `tests/test_build_phases.py`:
  - Mock a target root directory with a valid config (`workflows.enabled=true`, Claude Code >= 2.1.154 mocked).
  - Invoke build_workflow_scripts() directly.
  - Assert: `Path(<output>/.claude/workflows/plan-feature.js).exists()` is True.
  - Assert: file content matches source file byte-for-byte (SHA-256 hash match).
  - Assertion should not use just string comparison; compare file size and hash to catch silent truncations.
- [x] **Create test_plan_feature_deployed_in_consumer_config** in `tests/test_build_phases.py`:
  - Simulate a consumer install by setting up a temporary project directory.
  - Write a minimal skills_config.json with `"workflows": {"enabled": true}`.
  - Run full build.py (or call build_workflow_scripts directly) in that context.
  - Assert: plan-feature.js is in `.claude/workflows/` in the final output.
  - Assert: /plan-feature command can import/resolve the file without errors (basic import check via Node.js `require` or equivalent).
- [x] Add to test_requirements.tests in ticket frontmatter (done above).
- [x] Run existing test suite to ensure no regressions in the build system (e.g., test_build_phases.py if it exists, or the full build test suite).

### pr-reviewer

- [x] Verify the change is minimal and surgical: only adds templates/workflows-js/plan-feature.js, makes no modifications to build_phases.py logic.
- [x] Check that the file move/copy preserves all original content (no truncation, encoding loss, or merge conflicts).
- [x] Confirm the PR description explains the deployment gap and the parallelism constraint with TICKET-03.
- [x] Validate that test changes cover both unit (build_workflow_scripts behavior) and integration (deployment end-to-end) scenarios.

## Agent Contracts

| Agent | Delivers | Depends On | Sign-off Criteria |
|-------|----------|------------|------------------|
| python-coder | plan-feature.js copied to templates/workflows-js/; dry-run build passes | None | File copy verified; build --dry-run shows plan-feature.js in output |
| test-writer | Two new tests in tests/test_build_phases.py, both passing | python-coder phase complete | Tests are RED before code, GREEN after; coverage matches acceptance criteria |
| pr-reviewer | Pre-PR review report; no high-confidence issues | test-writer phase complete | All findings resolved or explicitly deferred |
| commit | Commit message and staged files recorded | pr-reviewer sign-off; all code changes complete | Commit created; precommit hooks pass |
| pull-request | PR opened to origin; merged if no blockers | commit sign-off | PR created; CI checks pass |

## Risk & Safety

- **Touches money?** No.
- **Touches data?** No.
- **Reversibility?** High — file copy is reversible; no schema or API changes.
- **Parallel safety:** Do not run in same batch as TICKET-03 (both touch scripts/build_phases.py, though different functions). Merge TICKET-02 first.
- **Deployment gating:** Existing gates (config.workflows.enabled, Claude Code >= 2.1.154) are correct; do not weaken.

## Open Questions

None. Scope and acceptance criteria are fully defined.
