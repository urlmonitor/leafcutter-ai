---
title: "Add default_artifact_checklist to test-runner"
status: todo
components:
  - build_pipeline
created: 2026-05-28
depends_on:
  - 01_signoff_skill_manifest_section.md
priority: high
requires_diagram: false
requires_adr: false
agents:
  documentation-expert: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# 02_04: Add default_artifact_checklist to test-runner

## Goal
Add `default_artifact_checklist` YAML frontmatter to `templates/agents/test-runner.md` so the agent always confirms these items in its `completion_manifest:` block on sign-off.

## Context
The test-runner agent (priority 9, role: quality) executes the test suite after implementation. Its checklist should confirm the suite ran, all tests passed, and a structured failure report was generated if applicable.

Source of truth: `config/agent_registry.json` entry with `"id": "test-runner"`.

## Checklist Items
```yaml
default_artifact_checklist:
  - test_suite_executed
  - all_tests_passing
  - failure_report_structured
```

## Acceptance Criteria
```gherkin
Given templates/agents/test-runner.md is read
When the frontmatter is parsed
Then a default_artifact_checklist key is present as a YAML list
And it contains exactly: test_suite_executed, all_tests_passing, failure_report_structured
```

## Sign-offs

- [ ] documentation-expert
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Implementation Tasks

### documentation-expert
- [ ] Edit `templates/agents/test-runner.md` frontmatter: add `default_artifact_checklist: [test_suite_executed, all_tests_passing, failure_report_structured]`
- [ ] Add instruction paragraph in body referencing signoff §2b completion_manifest requirement

## Comments
