---
title: "Deploy plan-feature.js to consumer installs via templates/workflows-js"
status: todo
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
  python-coder: needed
  test-writer: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
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

- [ ] python-coder
- [ ] test-writer
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

Hardened via /create-ticket. See EPIC-AcPipelineDeployGaps Master_Plan.md for epic context and parallelism constraints.

## Implementation Tasks

### python-coder

- [ ] **Copy** plan-feature.js from `scripts/workflows/plan-feature.js` to `templates/workflows-js/plan-feature.js` (do NOT move — keep source as fallback for now).
  - Command: `cp scripts/workflows/plan-feature.js templates/workflows-js/plan-feature.js`
  - Verify file size, encoding, and shebang match exactly (if present).
- [ ] Confirm scripts/build_phases.py:348 correctly references `templates/workflows-js/` and will pick up the new file via the glob pattern on line 357: `workflows_js_src.glob("*.js")`.
- [ ] Run the build locally to confirm zero errors or warnings related to workflows deployment:
  - Command: `python leafcutter-ai/scripts/build.py --target-dir /tmp/test-consumer-install --dry-run` (or equivalent in your environment).
  - Verify plan-feature.js appears in the dry-run file list.
- [ ] Do NOT remove scripts/workflows/plan-feature.js until test-writer confirms the tests pass (keep source intact for rollback).

### test-writer

- [ ] **Create test_build_workflow_scripts_includes_plan_feature** in `tests/test_build_phases.py`:
  - Mock a target root directory with a valid config (`workflows.enabled=true`, Claude Code >= 2.1.154 mocked).
  - Invoke build_workflow_scripts() directly.
  - Assert: `Path(<output>/.claude/workflows/plan-feature.js).exists()` is True.
  - Assert: file content matches source file byte-for-byte (SHA-256 hash match).
  - Assertion should not use just string comparison; compare file size and hash to catch silent truncations.
- [ ] **Create test_plan_feature_deployed_in_consumer_config** in `tests/test_build_phases.py`:
  - Simulate a consumer install by setting up a temporary project directory.
  - Write a minimal skills_config.json with `"workflows": {"enabled": true}`.
  - Run full build.py (or call build_workflow_scripts directly) in that context.
  - Assert: plan-feature.js is in `.claude/workflows/` in the final output.
  - Assert: /plan-feature command can import/resolve the file without errors (basic import check via Node.js `require` or equivalent).
- [ ] Add to test_requirements.tests in ticket frontmatter (done above).
- [ ] Run existing test suite to ensure no regressions in the build system (e.g., test_build_phases.py if it exists, or the full build test suite).

### pr-reviewer

- [ ] Verify the change is minimal and surgical: only adds templates/workflows-js/plan-feature.js, makes no modifications to build_phases.py logic.
- [ ] Check that the file move/copy preserves all original content (no truncation, encoding loss, or merge conflicts).
- [ ] Confirm the PR description explains the deployment gap and the parallelism constraint with TICKET-03.
- [ ] Validate that test changes cover both unit (build_workflow_scripts behavior) and integration (deployment end-to-end) scenarios.

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
